"""世界观条目 AI 抽取:逐章扫描,按 kind 分别抽取并合并入库。"""

import json
import re
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.world_entity import ENTITY_KINDS, WorldEntity
from app.services import prompt_service, world_entity_service


_KIND_LABELS = {
    "location": "地点(山川 / 城镇 / 宫殿 / 秘境 等)",
    "organization": "组织(门派 / 国家 / 社团 / 家族 等)",
    "concept": "概念(功法 / 体系 / 设定术语 等)",
}

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
    return {"entities": []}


def _existing_brief(entities: list[WorldEntity], kind: str) -> str:
    items = [e for e in entities if e.kind == kind]
    if not items:
        return "(暂无)"
    return "\n".join(
        f"- {e.name}" + (f" (别名:{ '、'.join(e.aliases) })" if e.aliases else "")
        for e in items
    )


def _kind_blocks(existing: list[WorldEntity], kinds: list[str]) -> str:
    blocks = []
    for kind in kinds:
        blocks.append(
            f"### {kind} - {_KIND_LABELS[kind]}\n"
            f"已知:\n{_existing_brief(existing, kind)}"
        )
    return "\n\n".join(blocks)


def _build_messages(db, chapter: Chapter, existing: list[WorldEntity], kinds: list[str]) -> list[dict]:
    return prompt_service.render(
        db,
        "extract.world",
        {
            "kind_blocks": _kind_blocks(existing, kinds),
            "chapter_label": f"第 {chapter.order_index} 章《{chapter.title}》",
            "chapter_content": chapter.content or "",
        },
    )


async def extract_world_entities(
    db: Session,
    project_id: int,
    kinds: list[str] | None,
    mode: str,
    chapter_ids: list[int] | None = None,
) -> AsyncGenerator[dict, None]:
    project = db.get(Project, project_id)
    if project is None:
        yield {"event": "error", "data": {"message": "工程不存在"}}
        return

    target_kinds = [k for k in (kinds or ENTITY_KINDS) if k in ENTITY_KINDS]
    if not target_kinds:
        target_kinds = list(ENTITY_KINDS)

    # 指定了章节时强制走 merge:replace 全量删除会和「只扫本章」语义冲突
    effective_mode = "merge" if chapter_ids else mode
    if effective_mode == "replace":
        for e in list(project.world_entities):
            if e.kind in target_kinds:
                db.delete(e)
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

        existing = list(project.world_entities)
        messages = _build_messages(db, chapter, existing, target_kinds)
        try:
            raw = await ai_client.complete(
                db, messages, scene="extract.world", max_tokens=2500, project_id=project_id
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"第 {chapter.order_index} 章世界观抽取失败: {e}"},
            }
            return

        parsed = _parse_json(raw)
        items = parsed.get("entities") or []
        for item in items:
            kind = (item.get("kind") or "").strip()
            if kind not in target_kinds:
                continue
            try:
                world_entity_service.merge_extracted_entity(
                    db, project_id, kind, item, chapter.id
                )
                extracted_count += 1
            except Exception:
                continue

        db.refresh(project)

        yield {
            "event": "progress",
            "data": {
                "index": idx, "total": total, "title": chapter.title,
                "found": len(items),
            },
        }

    yield {"event": "done", "data": {"total": total, "extracted": extracted_count}}
