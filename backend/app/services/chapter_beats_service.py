"""章节节拍 AI 草拟服务。

让模型基于工程总纲 + 主线 + 前情 + 本章梗概,草拟 3-5 个节拍(beat),
返回 ChapterBeat 列表。本服务**不直接落库**——返回给前端编辑后再 PATCH。
"""

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import prompts
from app.models.chapter import Chapter
from app.schemas.chapter import ChapterBeat
from app.services import plot_thread_service
from app.services.chapter_service import ChapterNotFoundError


class BeatsParseError(Exception):
    """AI 输出无法解析为节拍 JSON"""


def _extract_json(text: str) -> dict[str, Any]:
    if not text:
        raise BeatsParseError("模型返回为空")
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise BeatsParseError(f"未找到 JSON 对象: {text[:200]}")
    try:
        return json.loads(m.group(0))
    except Exception as e:
        raise BeatsParseError(f"JSON 解析失败: {e}") from e


def _coerce_beat(raw: Any) -> ChapterBeat | None:
    """把模型输出里的一项转成 ChapterBeat。校验失败的整项丢弃,不让一个坏拍拖垮整批。"""
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


async def suggest_beats(
    db: Session,
    chapter_id: int,
    *,
    target_word_count: int = 4000,
    extra_instruction: str | None = None,
) -> list[ChapterBeat]:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    stmt = (
        select(Chapter)
        .where(Chapter.project_id == chapter.project_id)
        .order_by(Chapter.order_index)
    )
    siblings = list(db.execute(stmt).scalars().all())
    threads = plot_thread_service.list_active_threads_for_prompt(db, chapter.project_id)

    messages = prompts.build_suggest_beats_messages(
        chapter.project,
        chapter,
        siblings,
        target_word_count=target_word_count,
        extra_instruction=extra_instruction,
        plot_threads=threads,
        db=db,
    )
    raw = await ai_client.complete(
        db,
        messages,
        scene="chapter.suggest_beats",
        max_tokens=2000,
        project_id=chapter.project_id,
    )
    data = _extract_json(raw)
    items = data.get("beats") or []
    if not isinstance(items, list):
        raise BeatsParseError("beats 字段不是数组")

    out: list[ChapterBeat] = []
    for item in items:
        beat = _coerce_beat(item)
        if beat is not None:
            out.append(beat)
    if not out:
        raise BeatsParseError("AI 没有返回任何有效节拍")
    return out
