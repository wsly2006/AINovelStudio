"""物品 AI 抽取:逐章扫描章节正文,合并入库到 items 表。

结构和 world_extract_service 平行,只是目标表换成 items,prompt
也独立一份(不必让 AI 同时辨认地点 / 组织 / 物品 / 概念,聚焦更准)。
"""

import json
import re
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.models.chapter import Chapter
from app.models.item import Item
from app.models.project import Project
from app.services import prompt_service

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(raw: str) -> dict:
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
    return {"items": []}


def _existing_brief(items: list[Item]) -> str:
    if not items:
        return "(暂无)"
    return "\n".join(
        f"- {it.name}" + (f" (别名:{ '、'.join(it.aliases) })" if it.aliases else "")
        for it in items
    )


def _build_messages(db, chapter: Chapter, existing: list[Item]) -> list[dict]:
    return prompt_service.render(
        db,
        "extract.items",
        {
            "existing_items": _existing_brief(existing),
            "chapter_label": f"第 {chapter.order_index} 章《{chapter.title}》",
            "chapter_content": chapter.content or "",
        },
    )


def _find_by_name_or_alias(items: list[Item], name: str) -> Item | None:
    for it in items:
        if it.name == name or name in (it.aliases or []):
            return it
    return None


def _merge_extracted(
    db: Session, project_id: int, existing: list[Item], extracted: dict, chapter_id: int | None
) -> Item | None:
    name = (extracted.get("name") or "").strip()
    if not name:
        return None

    found = _find_by_name_or_alias(existing, name)
    if found:
        # 合并别名
        new_aliases = set(found.aliases or [])
        new_aliases.update(extracted.get("aliases") or [])
        new_aliases.discard(found.name)
        found.aliases = sorted(new_aliases)

        for field in ("summary", "description"):
            new_val = (extracted.get(field) or "").strip()
            if not new_val:
                continue
            cur = getattr(found, field) or ""
            if not cur:
                setattr(found, field, new_val)
            elif new_val not in cur:
                setattr(found, field, cur + "\n\n" + new_val)

        new_tags = set(found.tags or [])
        new_tags.update(extracted.get("tags") or [])
        found.tags = sorted(new_tags)

        db.commit()
        db.refresh(found)
        return found

    it = Item(
        project_id=project_id,
        name=name,
        aliases=sorted(set(extracted.get("aliases") or [])),
        summary=extracted.get("summary"),
        description=extracted.get("description"),
        tags=sorted(set(extracted.get("tags") or [])),
        first_seen_chapter_id=chapter_id,
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


async def extract_items(
    db: Session,
    project_id: int,
    mode: str,
    chapter_ids: list[int] | None = None,
) -> AsyncGenerator[dict, None]:
    project = db.get(Project, project_id)
    if project is None:
        yield {"event": "error", "data": {"message": "工程不存在"}}
        return

    # 指定了章节时强制走 merge:replace 全量删除会和「只扫本章」语义冲突
    effective_mode = "merge" if chapter_ids else mode
    if effective_mode == "replace":
        for it in list(project.items):
            db.delete(it)
        db.commit()

    stmt = select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.order_index)
    if chapter_ids:
        stmt = stmt.where(Chapter.id.in_(chapter_ids))
    chapters = list(db.execute(stmt).scalars().all())
    total = len(chapters)
    if total == 0:
        yield {"event": "done", "data": {"total": 0, "extracted": 0}}
        return

    yield {"event": "start", "data": {"total": total}}

    extracted_count = 0
    for idx, chapter in enumerate(chapters, start=1):
        if not (chapter.content or "").strip():
            yield {
                "event": "progress",
                "data": {
                    "index": idx, "total": total, "title": chapter.title,
                    "found": 0, "skipped": True,
                },
            }
            continue

        existing = list(project.items)
        messages = _build_messages(db, chapter, existing)
        try:
            raw = await ai_client.complete(
                db, messages, scene="extract.items", max_tokens=2000, project_id=project_id
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"第 {chapter.order_index} 章物品抽取失败: {e}"},
            }
            return

        parsed = _parse_json(raw)
        rows = parsed.get("items") or []
        for row in rows:
            try:
                _merge_extracted(db, project_id, existing, row, chapter.id)
                extracted_count += 1
            except Exception:
                continue

        db.refresh(project)

        yield {
            "event": "progress",
            "data": {
                "index": idx, "total": total, "title": chapter.title,
                "found": len(rows),
            },
        }

    yield {"event": "done", "data": {"total": total, "extracted": extracted_count}}
