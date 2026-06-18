"""关系 / 情节 AI 抽取 + 一致性检查。

复用 character_extract_service 的 SSE 风格事件:start/progress/done/error。
"""

import json
import re
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.plot_event import PlotEvent
from app.models.project import Project
from app.models.relation import CharacterRelation
from app.services import plot_service, prompt_service, relation_service

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(raw: str, fallback_key: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_BLOCK.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {fallback_key: []}


def _characters_brief(characters: list[Character]) -> str:
    if not characters:
        return "(暂无)"
    return "\n".join(
        f"- id={c.id} {c.name}" + (f" (别名: {'、'.join(c.aliases)})" if c.aliases else "")
        for c in characters
    )


# ============ 关系抽取 ============


def _build_relation_messages(db, chapter: Chapter, characters: list[Character]) -> list[dict]:
    return prompt_service.render(
        db,
        "extract.relation",
        {
            "characters_brief": _characters_brief(characters),
            "chapter_label": f"第 {chapter.order_index} 章《{chapter.title}》",
            "chapter_content": chapter.content or "",
        },
    )


async def extract_relations(
    db: Session, project_id: int, chapter_ids: list[int] | None = None
) -> AsyncGenerator[dict, None]:
    project = db.get(Project, project_id)
    if project is None:
        yield {"event": "error", "data": {"message": "工程不存在"}}
        return

    characters = list(project.characters)
    if not characters:
        yield {"event": "done", "data": {"total": 0, "extracted": 0, "reason": "no_characters"}}
        return

    stmt = select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.order_index)
    if chapter_ids:
        stmt = stmt.where(Chapter.id.in_(chapter_ids))
    chapters = list(db.execute(stmt).scalars().all())
    if not chapters:
        yield {"event": "done", "data": {"total": 0, "extracted": 0}}
        return

    yield {"event": "start", "data": {"total": len(chapters)}}

    extracted = 0
    for idx, chapter in enumerate(chapters, start=1):
        if not (chapter.content or "").strip():
            yield {
                "event": "progress",
                "data": {"index": idx, "total": len(chapters), "title": chapter.title, "found": 0, "skipped": True},
            }
            continue

        messages = _build_relation_messages(db, chapter, characters)
        try:
            raw = await ai_client.complete(
                db, messages, scene="analysis.relations", max_tokens=1500, project_id=project_id
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"第 {chapter.order_index} 章关系抽取失败: {e}"},
            }
            return

        parsed = _parse_json(raw, "relations")
        items = parsed.get("relations") or []

        char_ids = {c.id for c in characters}
        for item in items:
            try:
                from_id = int(item.get("from_id"))
                to_id = int(item.get("to_id"))
                rel_type = (item.get("type") or "").strip()
                if from_id == to_id or not rel_type:
                    continue
                if from_id not in char_ids or to_id not in char_ids:
                    continue
                # 去重:同向同类型已存在则跳过
                exists = relation_service.find_existing(db, project_id, from_id, to_id, rel_type)
                if exists:
                    continue
                rel = CharacterRelation(
                    project_id=project_id,
                    from_id=from_id,
                    to_id=to_id,
                    type=rel_type,
                    description=(item.get("description") or "").strip() or None,
                    chapter_id=chapter.id,
                )
                db.add(rel)
                extracted += 1
            except (ValueError, TypeError):
                continue
        db.commit()

        yield {
            "event": "progress",
            "data": {
                "index": idx,
                "total": len(chapters),
                "title": chapter.title,
                "found": len(items),
            },
        }

    yield {"event": "done", "data": {"total": len(chapters), "extracted": extracted}}


# ============ 情节抽取 ============


def _threads_brief(threads: list) -> str:
    """供 extract.plot 注入的可用主线列表(只列 active + planning)。
    AI 输出 thread_id 时必须从这里挑;实在不属于任何线就给 null。"""
    if not threads:
        return "(本工程暂无主线;事件 thread_id 一律给 null)"
    lines = []
    for t in threads:
        bits = [f"id={t.id}", t.title]
        if t.description:
            bits.append(t.description.strip()[:80])
        lines.append("- " + " | ".join(bits))
    return "\n".join(lines)


def _build_plot_messages(db, chapter: Chapter, characters: list[Character], threads: list) -> list[dict]:
    return prompt_service.render(
        db,
        "extract.plot",
        {
            "characters_brief": _characters_brief(characters),
            "threads_brief": _threads_brief(threads),
            "chapter_label": f"第 {chapter.order_index} 章《{chapter.title}》",
            "chapter_content": chapter.content or "",
        },
    )


async def extract_plot(
    db: Session, project_id: int, chapter_ids: list[int] | None = None
) -> AsyncGenerator[dict, None]:
    project = db.get(Project, project_id)
    if project is None:
        yield {"event": "error", "data": {"message": "工程不存在"}}
        return

    stmt = select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.order_index)
    if chapter_ids:
        stmt = stmt.where(Chapter.id.in_(chapter_ids))
    chapters = list(db.execute(stmt).scalars().all())
    if not chapters:
        yield {"event": "done", "data": {"total": 0, "extracted": 0}}
        return

    characters = list(project.characters)
    char_ids = {c.id for c in characters}
    # 只把活跃 / 规划中的主线喂给 AI;已收 / 已废弃的不该再被关联
    active_threads = [
        t for t in project.plot_threads if t.status in ("planning", "active")
    ]
    valid_thread_ids = {t.id for t in active_threads}

    # 只清掉本次扫描范围内章节的旧事件,工程级抽取保持原有「全量重抽」语义
    target_chapter_ids = {ch.id for ch in chapters}
    for ev in list(project.plot_events):
        if ev.chapter_id in target_chapter_ids:
            db.delete(ev)
    db.commit()

    yield {"event": "start", "data": {"total": len(chapters)}}

    extracted = 0
    # 本批次抽到关联的主线 id 集合,抽完一次性把 planning 推进到 active
    hit_thread_ids: set[int] = set()
    for idx, chapter in enumerate(chapters, start=1):
        if not (chapter.content or "").strip():
            yield {
                "event": "progress",
                "data": {"index": idx, "total": len(chapters), "title": chapter.title, "found": 0, "skipped": True},
            }
            continue

        messages = _build_plot_messages(db, chapter, characters, active_threads)
        try:
            raw = await ai_client.complete(
                db, messages, scene="analysis.plot", max_tokens=2000, project_id=project_id
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"第 {chapter.order_index} 章情节抽取失败: {e}"},
            }
            return

        parsed = _parse_json(raw, "events")
        items = parsed.get("events") or []
        for order_in_chapter, item in enumerate(items, start=1):
            title = (item.get("title") or "").strip()
            if not title:
                continue
            cids = item.get("character_ids") or []
            cids = [int(x) for x in cids if isinstance(x, (int, str)) and str(x).isdigit()]
            cids = [x for x in cids if x in char_ids]

            # AI 给的 thread_id 必须在白名单里,否则置 null。容忍字符串数字。
            raw_tid = item.get("thread_id")
            tid: int | None = None
            if isinstance(raw_tid, (int, str)) and str(raw_tid).strip().lstrip("-").isdigit():
                candidate = int(raw_tid)
                if candidate in valid_thread_ids:
                    tid = candidate

            ev = PlotEvent(
                project_id=project_id,
                chapter_id=chapter.id,
                title=title[:200],
                description=(item.get("description") or "").strip() or None,
                character_ids=cids,
                importance=max(1, min(5, int(item.get("importance") or 3))),
                order_in_chapter=order_in_chapter,
                thread_id=tid,
            )
            db.add(ev)
            extracted += 1
            if tid is not None:
                hit_thread_ids.add(tid)
        db.commit()

        yield {
            "event": "progress",
            "data": {
                "index": idx,
                "total": len(chapters),
                "title": chapter.title,
                "found": len(items),
            },
        }

    # 状态自动推进:有事件挂上的 planning 线一律转 active。
    # 不动 active(避免误降级)、不动 resolved/abandoned(用户已盖棺)。
    promoted = 0
    if hit_thread_ids:
        for t in active_threads:
            if t.id in hit_thread_ids and t.status == "planning":
                t.status = "active"
                promoted += 1
        if promoted:
            db.commit()

    yield {
        "event": "done",
        "data": {
            "total": len(chapters),
            "extracted": extracted,
            "threads_promoted": promoted,
        },
    }


# ============ 一致性检查 ============


async def check_consistency(db: Session, project_id: int) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        return {"issues": [], "error": "工程不存在"}

    characters = list(project.characters)
    events = plot_service.list_events(db, project_id)

    chars_brief = "\n".join(
        f"id={c.id} {c.name}: {c.profile or ''}" for c in characters
    ) or "(无)"
    events_brief = "\n".join(
        f"- ev{ev.id} 章 {ev.chapter_id} 「{ev.title}」(人物 ids: {ev.character_ids}): {ev.description or ''}"
        for ev in events
    ) or "(无)"

    messages = prompt_service.render(
        db,
        "analysis.check",
        {
            "project_name": project.name,
            "characters_brief": chars_brief,
            "events_brief": events_brief,
        },
    )
    raw = await ai_client.complete(
        db, messages, scene="analysis.check", max_tokens=3000, project_id=project_id
    )
    parsed = _parse_json(raw, "issues")
    return parsed
