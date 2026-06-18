"""人物 AI 抽取服务:逐章扫描,合并入库。

输出 SSE 进度事件:每完成一章发一次 progress,结束时 done。
不用 stream_chat,因为这里需要等完整 JSON 才能解析。
"""

import json
import re
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.project import Project
from app.services import character_service, prompt_service


def _existing_block(existing: list[Character]) -> str:
    lines = []
    for c in existing:
        aliases = ("、".join(c.aliases or [])) or "无"
        lines.append(f"- {c.name}(别名:{aliases})")
    return "\n".join(lines) if lines else "(暂无)"


def _build_messages(db, chapter: Chapter, existing: list[Character]) -> list[dict]:
    return prompt_service.render(
        db,
        "extract.character",
        {
            "existing_characters": _existing_block(existing),
            "chapter_label": f"第 {chapter.order_index} 章《{chapter.title}》",
            "chapter_content": chapter.content or "",
        },
    )


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json(raw: str) -> dict:
    """容错地从 LLM 输出里抠出 JSON。"""
    text = raw.strip()
    # 去 markdown 代码块
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
    return {"characters": []}


async def extract_characters(
    db: Session,
    project_id: int,
    chapter_ids: list[int] | None,
    mode: str,
) -> AsyncGenerator[dict, None]:
    project = db.get(Project, project_id)
    if project is None:
        yield {"event": "error", "data": {"message": "工程不存在"}}
        return

    if mode == "replace":
        # 清空已有,以便 replace 模式重建
        for c in list(project.characters):
            db.delete(c)
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
                "data": {"index": idx, "total": total, "title": chapter.title, "found": 0, "skipped": True},
            }
            continue

        existing = list(project.characters)
        messages = _build_messages(db, chapter, existing)
        try:
            raw = await ai_client.complete(
                db, messages, scene="extract.character", max_tokens=2000, project_id=project_id
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": {"message": f"第 {chapter.order_index} 章抽取失败: {e}"},
            }
            return

        parsed = _parse_json(raw)
        items = parsed.get("characters") or []
        for item in items:
            try:
                character_service.merge_extracted_character(
                    db, project_id, item, chapter.id
                )
                extracted_count += 1
            except Exception:
                # 单条失败不影响整体
                continue

        # 重新加载 project.characters 用于下一章去重
        db.refresh(project)

        yield {
            "event": "progress",
            "data": {
                "index": idx,
                "total": total,
                "title": chapter.title,
                "found": len(items),
            },
        }

    yield {"event": "done", "data": {"total": total, "extracted": extracted_count}}
