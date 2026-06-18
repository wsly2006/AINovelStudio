"""章节 AI 文风检查服务。

调 LiteLLM 让模型挑出读起来"像 AI 写"的段落,返回 JSON 落库。
单条 issue 字段缺失就丢这条,不把整次检查全废掉;
解析失败(根本不是 JSON)才上抛给 API。
"""

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import prompts
from app.ai.runtime import resolve as resolve_ai_runtime
from app.models.chapter import Chapter
from app.models.chapter_style_check import ChapterStyleCheck
from app.schemas.chapter_style_check import ChapterStyleCheckItem
from app.services.chapter_service import ChapterNotFoundError

_VALID_KINDS = {"套语", "排比堆砌", "辞藻冗余", "模板结构", "对话同质", "视角抽离", "其他"}


class ChapterStyleCheckParseError(Exception):
    """AI 输出无法解析为 JSON"""


class ChapterStyleCheckNotFoundError(Exception):
    """检查记录不存在"""


def _extract_json(text: str) -> dict[str, Any]:
    """从模型输出里抠出 JSON 对象,跟评分服务同款兜底。"""
    if not text:
        raise ChapterStyleCheckParseError("模型返回为空")
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ChapterStyleCheckParseError(f"未找到 JSON 对象: {text[:200]}")
    try:
        return json.loads(m.group(0))
    except Exception as e:
        raise ChapterStyleCheckParseError(f"JSON 解析失败: {e}") from e


def _coerce_issue(raw: Any) -> dict[str, str] | None:
    # 模型偶尔会少字段或字段类型奇怪,按 dict 严格筛一遍,缺关键就丢这条
    if not isinstance(raw, dict):
        return None
    quote = str(raw.get("quote") or "").strip()
    if not quote:
        # 找不到原文片段就没法跳转,这条对用户没价值
        return None
    kind = str(raw.get("kind") or "其他").strip()
    if kind not in _VALID_KINDS:
        kind = "其他"
    why = str(raw.get("why") or "").strip()
    suggestion = str(raw.get("suggestion") or "").strip()
    return {
        "kind": kind,
        "quote": quote,
        "why": why,
        "suggestion": suggestion,
    }


async def style_check_chapter(db: Session, chapter_id: int) -> ChapterStyleCheckItem:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    messages = prompts.build_style_check_messages(chapter.project, chapter, db=db)
    raw = await ai_client.complete(
        db,
        messages,
        scene="chapter.style_check",
        max_tokens=2500,
        project_id=chapter.project_id,
    )
    data = _extract_json(raw)

    raw_issues = data.get("issues") or []
    if not isinstance(raw_issues, list):
        raw_issues = []
    issues: list[dict[str, str]] = []
    for it in raw_issues:
        coerced = _coerce_issue(it)
        if coerced is not None:
            issues.append(coerced)
    summary = str(data.get("summary") or "").strip()

    cfg = resolve_ai_runtime(db)
    row = ChapterStyleCheck(
        chapter_id=chapter.id,
        issues=issues,
        summary=summary,
        model=cfg.model,
        word_count=chapter.word_count or 0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ChapterStyleCheckItem.model_validate(row)


def list_checks(db: Session, chapter_id: int) -> list[ChapterStyleCheckItem]:
    if db.get(Chapter, chapter_id) is None:
        raise ChapterNotFoundError(chapter_id)
    stmt = (
        select(ChapterStyleCheck)
        .where(ChapterStyleCheck.chapter_id == chapter_id)
        .order_by(ChapterStyleCheck.created_at.desc(), ChapterStyleCheck.id.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [ChapterStyleCheckItem.model_validate(r) for r in rows]


def delete_check(db: Session, check_id: int) -> ChapterStyleCheck:
    row = db.get(ChapterStyleCheck, check_id)
    if row is None:
        raise ChapterStyleCheckNotFoundError(check_id)
    db.delete(row)
    db.commit()
    return row
