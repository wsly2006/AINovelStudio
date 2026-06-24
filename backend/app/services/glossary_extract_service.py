"""翻译术语表 AI 候选抽取:逐章扫章节正文,识别值得入翻译术语表的中文专有名词。

设计要点:
- 输出严格 JSON,只识别中文 source,不让 AI 提议译法 —— target 留给 M3 在更全的
  上下文里统一翻
- 纯 merge:同一 (project_id, source, target_lang) 已存在直接跳过(无论 locked
  与否)。要重新评估译法是 M3 的事,M2 不动现有条目
- entry_type 输出走白名单兜底:模型乱写一律落 'other'
"""

import json
import re
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.translation_glossary import TranslationGlossary
from app.schemas.translation_glossary import ENTRY_TYPES
from app.services import prompt_service

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
# 注入 prompt 的已有术语条数上限 —— 防止超长项目把 token 撑爆
_EXISTING_BRIEF_LIMIT = 200


def _parse_json(raw: str) -> dict:
    text = (raw or "").strip()
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
    return {"entries": []}


def _existing_brief(rows: list[TranslationGlossary]) -> str:
    if not rows:
        return "(暂无)"
    # 取最近的一截避免 prompt 过长
    sample = rows[-_EXISTING_BRIEF_LIMIT:]
    return "\n".join(f"- {r.source}" for r in sample)


def _build_messages(
    db: Session, chapter: Chapter, existing: list[TranslationGlossary]
) -> list[dict]:
    return prompt_service.render(
        db,
        "extract.glossary",
        {
            "existing_glossary": _existing_brief(existing),
            "chapter_label": f"第 {chapter.order_index} 章《{chapter.title}》",
            "chapter_content": chapter.content or "",
        },
    )


def _coerce_entry(raw: dict) -> tuple[str, str] | None:
    """把 AI 输出的一项拍平成 (source, entry_type),坏数据返 None。"""
    if not isinstance(raw, dict):
        return None
    source = (raw.get("source") or "").strip()
    if not source:
        return None
    etype = (raw.get("entry_type") or "other").strip().lower()
    if etype not in ENTRY_TYPES:
        etype = "other"
    return source, etype


async def extract_glossary(
    db: Session,
    project_id: int,
    target_lang: str = "en-US",
    chapter_ids: list[int] | None = None,
) -> AsyncGenerator[dict, None]:
    project = db.get(Project, project_id)
    if project is None:
        yield {"event": "error", "data": {"message": "工程不存在"}}
        return

    stmt = (
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.order_index)
    )
    if chapter_ids:
        stmt = stmt.where(Chapter.id.in_(chapter_ids))
    chapters = list(db.execute(stmt).scalars().all())
    total = len(chapters)
    if total == 0:
        yield {
            "event": "done",
            "data": {"total": 0, "extracted": 0, "skipped": 0},
        }
        return

    yield {
        "event": "start",
        "data": {"total": total, "target_lang": target_lang},
    }

    extracted_count = 0
    skipped_count = 0

    def _load_existing() -> list[TranslationGlossary]:
        s = (
            select(TranslationGlossary)
            .where(
                TranslationGlossary.project_id == project_id,
                TranslationGlossary.target_lang == target_lang,
            )
            .order_by(TranslationGlossary.id)
        )
        return list(db.execute(s).scalars().all())

    for idx, chapter in enumerate(chapters, start=1):
        if not (chapter.content or "").strip():
            yield {
                "event": "progress",
                "data": {
                    "index": idx,
                    "total": total,
                    "title": chapter.title,
                    "added": 0,
                    "skipped": 0,
                    "empty": True,
                },
            }
            continue

        existing = _load_existing()
        existing_sources = {r.source for r in existing}
        messages = _build_messages(db, chapter, existing)

        try:
            raw = await ai_client.complete(
                db,
                messages,
                scene="extract.glossary",
                max_tokens=1500,
                project_id=project_id,
            )
        except Exception as e:
            yield {
                "event": "error",
                "data": {
                    "message": f"第 {chapter.order_index} 章术语抽取失败: {e}"
                },
            }
            return

        parsed = _parse_json(raw)
        rows = parsed.get("entries") or []

        added_in_chapter = 0
        skipped_in_chapter = 0
        # 同一章 AI 自己重复返同一词,只入第一条
        seen_in_batch: set[str] = set()
        for row in rows:
            coerced = _coerce_entry(row)
            if coerced is None:
                continue
            source, etype = coerced
            if source in existing_sources or source in seen_in_batch:
                skipped_in_chapter += 1
                continue
            seen_in_batch.add(source)
            entry = TranslationGlossary(
                project_id=project_id,
                source=source,
                target="",
                target_lang=target_lang,
                entry_type=etype,
                locked=False,
            )
            db.add(entry)
            try:
                db.commit()
            except IntegrityError:
                # 极少概率竞争(并发抽取),回滚算 skip
                db.rollback()
                skipped_in_chapter += 1
                continue
            added_in_chapter += 1

        extracted_count += added_in_chapter
        skipped_count += skipped_in_chapter

        yield {
            "event": "progress",
            "data": {
                "index": idx,
                "total": total,
                "title": chapter.title,
                "added": added_in_chapter,
                "skipped": skipped_in_chapter,
            },
        }

    yield {
        "event": "done",
        "data": {
            "total": total,
            "extracted": extracted_count,
            "skipped": skipped_count,
        },
    }
