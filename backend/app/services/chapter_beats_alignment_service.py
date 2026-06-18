"""节拍-事件对账服务。

写完章节正文 + auto-index 抽事件后,这个服务把节拍和实际事件交给 AI 逐拍判断:
covered / partial / missing,把结果落到 chapter.beats_alignment。

对账只跑在「章节有节拍 + 至少有一个事件」的前提下。否则没意义,直接清空对账结果。
"""

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.models.chapter import Chapter
from app.models.plot_event import PlotEvent
from app.schemas.chapter import BeatAlignmentItem, BeatsAlignmentResponse
from app.services import prompt_service
from app.services.chapter_service import ChapterNotFoundError


VALID_STATUSES = ("covered", "partial", "missing")


class BeatsAlignmentParseError(Exception):
    """AI 输出无法解析为对账 JSON"""


def _parse_alignment_json(raw: str) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            raise BeatsAlignmentParseError(f"未找到 JSON 对象: {raw[:200]}")
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise BeatsAlignmentParseError(f"JSON 解析失败: {e}") from e
    items = data.get("items") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def _coerce_int_list(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    out = []
    for x in raw:
        if isinstance(x, bool):
            continue
        if isinstance(x, int):
            out.append(x)
        elif isinstance(x, str) and x.strip().lstrip("-").isdigit():
            out.append(int(x))
    return out


def _build_beats_block(beats: list) -> str:
    lines = []
    for i, b in enumerate(beats):
        title = (b.get("title") or "").strip()
        if not title:
            continue
        detail = (b.get("detail") or "").strip()
        bits = [title]
        if detail:
            bits.append(detail)
        lines.append(f"{i}. " + " — ".join(bits))
    return "\n".join(lines) if lines else "(空)"


def _build_events_block(events: list[PlotEvent]) -> str:
    if not events:
        return "(空)"
    lines = []
    for ev in events:
        bits = [f"id={ev.id}", ev.title]
        if ev.description:
            bits.append(ev.description.strip()[:120])
        lines.append("- " + " | ".join(bits))
    return "\n".join(lines)


def _build_alignment_messages(db, chapter: Chapter, events: list[PlotEvent]) -> list[dict]:
    return prompt_service.render(
        db,
        "chapter.check_beats",
        {
            "chapter_label": f"第 {chapter.order_index} 章《{chapter.title}》",
            "beats_block": _build_beats_block(chapter.beats or []),
            "events_block": _build_events_block(events),
        },
    )


def _zero_response() -> BeatsAlignmentResponse:
    return BeatsAlignmentResponse(items=[], covered=0, partial=0, missing=0)


def clear_alignment(db: Session, chapter: Chapter) -> None:
    """节拍变化时调:对账结果不再可信,直接清空。"""
    if chapter.beats_alignment:
        chapter.beats_alignment = None
        db.commit()


async def align(db: Session, chapter_id: int) -> BeatsAlignmentResponse:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    beats = chapter.beats or []
    valid_beats = [b for b in beats if (b.get("title") or "").strip()]
    if not valid_beats:
        # 没节拍 → 清空旧的对账结果(可能上次还有),返回 0/0/0
        clear_alignment(db, chapter)
        return _zero_response()

    events = list(
        db.execute(
            select(PlotEvent)
            .where(PlotEvent.chapter_id == chapter.id)
            .order_by(PlotEvent.order_in_chapter, PlotEvent.id)
        ).scalars().all()
    )
    if not events:
        # 有节拍没事件 → 全部 missing,直接构造,不调 AI
        items = [
            BeatAlignmentItem(
                beat_index=i,
                status="missing",
                matched_event_ids=[],
                note="本章未抽出任何情节事件,无法兑现节拍",
            )
            for i in range(len(valid_beats))
        ]
        return _persist(db, chapter, items)

    messages = _build_alignment_messages(db, chapter, events)
    raw = await ai_client.complete(
        db,
        messages,
        scene="chapter.check_beats",
        max_tokens=2000,
        project_id=chapter.project_id,
    )
    raw_items = _parse_alignment_json(raw)

    # 索引模型给的回应,处理乱序 / 缺项 / 多项 / 越界
    by_index: dict[int, dict] = {}
    valid_event_ids = {e.id for e in events}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        try:
            idx = int(raw_item.get("beat_index"))
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(valid_beats):
            continue
        if idx in by_index:
            continue  # 取第一次出现的那条
        st = raw_item.get("status")
        if st not in VALID_STATUSES:
            continue
        eids = [e for e in _coerce_int_list(raw_item.get("matched_event_ids")) if e in valid_event_ids]
        note = (raw_item.get("note") or "").strip() or None
        by_index[idx] = {
            "beat_index": idx,
            "status": st,
            "matched_event_ids": eids,
            "note": note[:400] if note else None,
        }

    # 没覆盖到的拍统一标 missing,note 说明 AI 漏判
    items: list[BeatAlignmentItem] = []
    for i in range(len(valid_beats)):
        if i in by_index:
            items.append(BeatAlignmentItem(**by_index[i]))
        else:
            items.append(
                BeatAlignmentItem(
                    beat_index=i,
                    status="missing",
                    matched_event_ids=[],
                    note="AI 未对此拍给出判断,默认按未兑现处理",
                )
            )
    return _persist(db, chapter, items)


def _persist(
    db: Session, chapter: Chapter, items: list[BeatAlignmentItem]
) -> BeatsAlignmentResponse:
    chapter.beats_alignment = [it.model_dump() for it in items]
    db.commit()
    db.refresh(chapter)

    covered = sum(1 for i in items if i.status == "covered")
    partial = sum(1 for i in items if i.status == "partial")
    missing = sum(1 for i in items if i.status == "missing")
    return BeatsAlignmentResponse(
        items=items, covered=covered, partial=partial, missing=missing
    )
