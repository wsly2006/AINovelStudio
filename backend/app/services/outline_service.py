"""大纲模式服务:批量草拟连续章节大纲 + 落库 + 章节-大纲对账。

设计:
- 「大纲」= 章节的 title + summary + beats,无新表
- 批量草拟:一次让 AI 输出 N 章,本服务**不直接落库**;前端预览后确认才调 batch_create
- 批量落库:在末尾追加 N 个 status='outlined' 的空正文章节
- 章节-大纲对账:把章节正文与计划好的 summary + beats 对账,逐项 covered/partial/missing
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import prompts
from app.models.chapter import Chapter
from app.models.project import Project
from app.schemas.chapter import (
    ChapterBeat,
    ChapterListItem,
    OutlineAlignmentResult,
    OutlineBeatAlignment,
    OutlineDraft,
)
from app.services import chapter_service, plot_thread_service


class OutlineParseError(Exception):
    """AI 输出无法解析为大纲 JSON"""


class ProjectNotFoundForOutlineError(Exception):
    """工程不存在"""


class StartChapterNotFoundError(Exception):
    """指定的起始章节不存在"""


def _extract_json(text: str) -> dict[str, Any]:
    if not text:
        raise OutlineParseError("模型返回为空")
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise OutlineParseError(f"未找到 JSON 对象: {text[:200]}")
    try:
        return json.loads(m.group(0))
    except Exception as e:
        raise OutlineParseError(f"JSON 解析失败: {e}") from e


def _coerce_beat(raw: Any) -> ChapterBeat | None:
    """把 AI 输出里的一项转成 ChapterBeat,坏拍丢弃。"""
    if not isinstance(raw, dict):
        return None
    title = (raw.get("title") or "").strip()
    if not title:
        return None
    detail = (raw.get("detail") or "").strip() or None
    threads_raw = raw.get("thread_titles") or []
    if not isinstance(threads_raw, list):
        threads_raw = []
    threads = [str(t).strip() for t in threads_raw if isinstance(t, (str, int))]
    threads = [t for t in threads if t]
    try:
        return ChapterBeat(title=title[:80], detail=detail, thread_titles=threads)
    except Exception:
        return None


def _coerce_draft(raw: Any) -> OutlineDraft | None:
    """单章草稿。title 可空,summary/beats 容错。整章无效时返回 None。"""
    if not isinstance(raw, dict):
        return None
    title = (raw.get("title") or "").strip()[:200]
    summary = (raw.get("summary") or "").strip() or None
    beats_raw = raw.get("beats") or []
    beats: list[ChapterBeat] = []
    if isinstance(beats_raw, list):
        for b in beats_raw:
            beat = _coerce_beat(b)
            if beat is not None:
                beats.append(beat)
    # 完全空的章节(无 title 又无 summary 又无 beats)就丢
    if not title and not summary and not beats:
        return None
    try:
        return OutlineDraft(title=title, summary=summary, beats=beats)
    except Exception:
        return None


async def batch_suggest(
    db: Session,
    project_id: int,
    *,
    count: int,
    start_order_index: int | None = None,
    extra_instruction: str | None = None,
    target_word_count: int = 4000,
) -> list[OutlineDraft]:
    """让 AI 一次性产出连续 N 章大纲。不落库。

    start_order_index 为 None 时表示从「最后一章 + 1」开始,即末尾追加。
    给值时,前序章节为 order_index < start_order_index 的所有章节。
    """
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundForOutlineError(project_id)

    stmt = (
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.order_index)
    )
    all_chapters = list(db.execute(stmt).scalars().all())

    if start_order_index is None:
        # 末尾追加,起始 order_index = 当前章节数 + 1
        effective_start = (all_chapters[-1].order_index + 1) if all_chapters else 1
        previous = all_chapters
    else:
        effective_start = start_order_index
        # 前序 = order_index < start_order_index 的章节
        previous = [c for c in all_chapters if c.order_index < start_order_index]

    threads = plot_thread_service.list_active_threads_for_prompt(db, project_id)

    messages = prompts.build_suggest_outlines_batch_messages(
        project,
        previous,
        count=count,
        start_order_index=effective_start,
        extra_instruction=extra_instruction,
        plot_threads=threads,
        db=db,
    )
    # 单次输出 N 章,token 上限按 N 估算(每章约 600 tokens 中文,留余量)
    max_tokens = max(2000, count * 800)
    raw = await ai_client.complete(
        db,
        messages,
        scene="outline.suggest_batch",
        max_tokens=max_tokens,
        project_id=project_id,
    )

    data = _extract_json(raw)
    items = data.get("chapters") or []
    if not isinstance(items, list):
        raise OutlineParseError("chapters 字段不是数组")

    drafts: list[OutlineDraft] = []
    for item in items:
        d = _coerce_draft(item)
        if d is not None:
            drafts.append(d)
        if len(drafts) >= count:
            break

    if not drafts:
        raise OutlineParseError("AI 没有返回任何有效章节大纲")
    return drafts


def batch_create(
    db: Session,
    project_id: int,
    drafts: list[OutlineDraft],
) -> list[ChapterListItem]:
    """把草稿数组追加到工程末尾,status='outlined'。返回新建章节列表。"""
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundForOutlineError(project_id)
    if not drafts:
        return []

    stmt = select(Chapter.order_index).where(Chapter.project_id == project_id)
    existing = list(db.execute(stmt).scalars().all())
    next_order = (max(existing) + 1) if existing else 1

    created_ids: list[int] = []
    for d in drafts:
        # beats 转成可入 JSON 列的 dict
        beats_payload = (
            [b.model_dump() for b in d.beats] if d.beats else None
        )
        c = Chapter(
            project_id=project_id,
            title=d.title or "",
            order_index=next_order,
            content="",
            summary=d.summary,
            beats=beats_payload,
            status="outlined",
            word_count=0,
        )
        db.add(c)
        next_order += 1
        # commit 后再取 id
    db.commit()

    # 重新查这批新章节(按 order_index 拿最后 N 条)
    n = len(drafts)
    stmt2 = (
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.order_index.desc())
        .limit(n)
    )
    new_rows = list(db.execute(stmt2).scalars().all())
    new_rows.reverse()
    created_ids = [c.id for c in new_rows]

    # 用 chapter_service 的列表归约,保持徽章字段一致
    all_items = chapter_service.list_chapters(db, project_id)
    return [item for item in all_items if item.id in set(created_ids)]


def _coerce_alignment_status(raw: Any) -> str:
    s = (str(raw) if raw is not None else "").strip().lower()
    if s in ("covered", "partial", "missing"):
        return s
    return "missing"


async def check_outline_alignment(
    db: Session,
    chapter_id: int,
) -> OutlineAlignmentResult:
    """章节正文 vs 大纲对账。

    没有正文 / 没有大纲(summary 为空且无 beats)时直接返回 missing,不调 AI。
    """
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise chapter_service.ChapterNotFoundError(chapter_id)

    has_summary = bool((chapter.summary or "").strip())
    has_beats = bool(chapter.beats)
    has_content = bool((chapter.content or "").strip())

    # 大纲为空 → 没什么好对账的,直接返回 missing 提示
    if not has_summary and not has_beats:
        return OutlineAlignmentResult(
            summary_status="missing",
            summary_note="本章未填梗概,也未列节拍,无大纲可对账",
            beats=[],
            overall_note="请先在大纲模式下补充本章梗概或节拍,再回来对账",
            covered=0,
            partial=0,
            missing=1,
        )

    # 正文为空 → 全部 missing,也不调 AI
    if not has_content:
        beat_items: list[OutlineBeatAlignment] = []
        if chapter.beats:
            beat_items = [
                OutlineBeatAlignment(
                    beat_index=i,
                    status="missing",
                    note="正文为空,未兑现",
                )
                for i in range(len(chapter.beats))
            ]
        return OutlineAlignmentResult(
            summary_status="missing" if has_summary else "missing",
            summary_note="正文为空,未兑现梗概" if has_summary else "本章未填梗概",
            beats=beat_items,
            overall_note="本章正文为空,无法对账",
            covered=0,
            partial=0,
            missing=1 + len(beat_items),
        )

    messages = prompts.build_outline_alignment_messages(chapter, db=db)
    raw = await ai_client.complete(
        db,
        messages,
        scene="chapter.outline_alignment",
        max_tokens=2500,
        project_id=chapter.project_id,
    )

    data = _extract_json(raw)
    summary_status = _coerce_alignment_status(data.get("summary_status"))
    summary_note = (data.get("summary_note") or "").strip() or None

    beat_items_out: list[OutlineBeatAlignment] = []
    raw_beats = data.get("beats") or []
    if isinstance(raw_beats, list):
        existing_beats = chapter.beats or []
        for raw_item in raw_beats:
            if not isinstance(raw_item, dict):
                continue
            try:
                idx = int(raw_item.get("beat_index"))
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(existing_beats):
                continue
            beat_items_out.append(
                OutlineBeatAlignment(
                    beat_index=idx,
                    status=_coerce_alignment_status(raw_item.get("status")),
                    note=(raw_item.get("note") or "").strip() or None,
                )
            )

    overall_note = (data.get("overall_note") or "").strip() or None

    # 计数:summary 算 1 项,beats 各算 1 项
    covered = partial = missing = 0
    if has_summary:
        if summary_status == "covered":
            covered += 1
        elif summary_status == "partial":
            partial += 1
        else:
            missing += 1
    for it in beat_items_out:
        if it.status == "covered":
            covered += 1
        elif it.status == "partial":
            partial += 1
        else:
            missing += 1

    return OutlineAlignmentResult(
        summary_status=summary_status,
        summary_note=summary_note,
        beats=beat_items_out,
        overall_note=overall_note,
        covered=covered,
        partial=partial,
        missing=missing,
    )


__all__ = [
    "batch_suggest",
    "batch_create",
    "check_outline_alignment",
    "OutlineParseError",
    "ProjectNotFoundForOutlineError",
    "StartChapterNotFoundError",
]
