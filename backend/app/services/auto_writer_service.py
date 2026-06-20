"""自动连写编排器:批量从指定章节开始,生成 → 索引 → 对账 → 评分 → 决策。

复用现有 ai_task_manager 协议,前端通过 GET /api/ai-tasks/{id}/stream 订阅。

事件协议:
    start         : {project_id, total, start_chapter_id, mode, score_threshold}
    chapter_start : {chapter_index, total, chapter_id, order_index, title, attempt}
    generating    : {chapter_id, chars}                 流式期间每 1500 字一次,够看进度即可
    generated     : {chapter_id, word_count}
    indexing      : {chapter_id}
    indexed       : {chapter_id, events_count}
    aligning      : {chapter_id}
    aligned       : {chapter_id, covered, partial, missing}
    scoring       : {chapter_id}
    scored        : {chapter_id, overall, writing, plot, characters, feedback}
    chapter_done  : {chapter_id, decision: 'pass'|'retry'|'stop', reason}
    done          : {processed, stopped_reason?}
    error / cancelled : 由 ai_task_manager.finish 写入
"""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from sqlalchemy import func, select

from app.ai.client import AIError, AINotConfiguredError
from app.database import SessionLocal
from app.models.chapter import Chapter
from app.models.plot_event import PlotEvent
from app.services import (
    ai_task_manager,
    analysis_service,
    chapter_ai_service,
    chapter_beats_alignment_service,
    chapter_score_service,
    chapter_service,
    chapter_version_service,
)

logger = logging.getLogger(__name__)

Mode = Literal["strict", "auto_fix", "all_through"]

# 流式生成期间多久(按字符)往 SSE 推一次进度
PROGRESS_CHARS = 1500


def _build_carry_instruction(
    prev_missing_beats: list[str],
    prev_partial_beats: list[str],
    extra: str | None,
) -> str | None:
    """把上一章遗留的拍 + 用户原始 instruction 拼成下一章的 extra_instruction。"""
    parts: list[str] = []
    if prev_missing_beats:
        parts.append(
            "上一章这些节拍未兑现,本章请考虑补足或承接:\n- "
            + "\n- ".join(prev_missing_beats)
        )
    if prev_partial_beats:
        parts.append(
            "上一章这些节拍只完成了一半,本章可顺势推进:\n- "
            + "\n- ".join(prev_partial_beats)
        )
    if extra and extra.strip():
        parts.append(extra.strip())
    return "\n\n".join(parts) if parts else None


async def _generate_chapter(
    db,
    task_id: str,
    chapter: Chapter,
    *,
    target_word_count: int,
    extra_instruction: str | None,
    character_ids: list[int],
    world_entity_ids: list[int],
    item_ids: list[int],
) -> str:
    """流式跑完一章,把 delta 累加成完整文本并落库。返回最终正文。"""
    text_parts: list[str] = []
    last_progress = 0
    async for delta in chapter_ai_service.stream_generate(
        db,
        chapter.id,
        target_word_count=target_word_count,
        extra_instruction=extra_instruction,
        character_ids=character_ids,
        world_entity_ids=world_entity_ids,
        item_ids=item_ids,
    ):
        text_parts.append(delta)
        total_len = sum(len(p) for p in text_parts)
        if total_len - last_progress >= PROGRESS_CHARS:
            last_progress = total_len
            await ai_task_manager.append_event(
                task_id,
                "generating",
                {"chapter_id": chapter.id, "chars": total_len},
            )

    full_text = "".join(text_parts).strip()
    if not full_text:
        raise AIError("AI 返回空内容")
    # 折叠段落空行,与抽屉里 onAccept 行为一致
    full_text = full_text.replace("\r\n", "\n")
    while "\n\n" in full_text:
        full_text = full_text.replace("\n\n", "\n")
    chapter_service.save_content(db, chapter.id, full_text)
    return full_text


async def _index_chapter(db, chapter: Chapter) -> int:
    """单章重抽事件;沿用 analysis_service.extract_plot 的 chapter_ids 单元素调用。"""
    extracted = 0
    async for evt in analysis_service.extract_plot(
        db, chapter.project_id, chapter_ids=[chapter.id]
    ):
        kind = evt.get("event")
        data = evt.get("data") or {}
        if kind == "done":
            extracted = int(data.get("extracted") or 0)
        elif kind == "error":
            raise AIError(str(data.get("message") or "情节抽取失败"))
    return extracted


def _missing_partial_beat_titles(chapter: Chapter, alignment_items: list[dict]) -> tuple[list[str], list[str]]:
    """根据对账结果挑出 missing / partial 的节拍标题,作为下一章的 carry instruction。"""
    beats = chapter.beats or []
    missing: list[str] = []
    partial: list[str] = []
    for it in alignment_items or []:
        idx = it.get("beat_index")
        st = it.get("status")
        if not isinstance(idx, int) or idx < 0 or idx >= len(beats):
            continue
        title = (beats[idx].get("title") or "").strip()
        if not title:
            continue
        if st == "missing":
            missing.append(title)
        elif st == "partial":
            partial.append(title)
    return missing, partial


def _decide_next(
    *,
    mode: Mode,
    score_overall: int | None,
    missing_beats: int,
    score_threshold: int,
    attempt: int,
) -> tuple[str, str]:
    """根据本章质量决定 pass / retry / stop。返回 (decision, reason)。"""
    quality_bad = (
        score_overall is not None and score_overall < score_threshold
    ) or missing_beats > 0

    if not quality_bad:
        return "pass", "通过"

    # 第一次失败可重试 1 次,attempt 已经 >=2 表示重试也不达标
    if attempt < 2:
        return "retry", (
            f"评分 {score_overall} < {score_threshold}"
            if (score_overall is not None and score_overall < score_threshold)
            else f"{missing_beats} 个节拍未兑现"
        )

    # 第二次仍不达标:严格档停,自纠档继续(但记录),全推档当然继续
    if mode == "strict":
        return "stop", "重试后仍未达到质量阈值"
    return "pass", "重试后仍未达标但按当前模式继续"


async def run_auto_writer(
    task_id: str,
    *,
    project_id: int,
    chapter_ids_in_order: list[int],
    target_word_count: int,
    base_extra_instruction: str | None,
    character_ids: list[int],
    world_entity_ids: list[int],
    item_ids: list[int],
    mode: Mode,
    score_threshold: int,
) -> None:
    """编排主体。所有事件走 ai_task_manager,自己捕获所有异常。"""
    db = SessionLocal()
    processed = 0
    stopped_reason: str | None = None
    try:
        await ai_task_manager.append_event(
            task_id,
            "start",
            {
                "project_id": project_id,
                "total": len(chapter_ids_in_order),
                "start_chapter_id": chapter_ids_in_order[0] if chapter_ids_in_order else None,
                "mode": mode,
                "score_threshold": score_threshold,
            },
        )

        # 上一章遗留下来的节拍标题,会拼进下一章的 extra_instruction
        carry_missing: list[str] = []
        carry_partial: list[str] = []

        for ci, chapter_id in enumerate(chapter_ids_in_order, start=1):
            chapter = db.get(Chapter, chapter_id)
            if chapter is None:
                # 章节被删了,跳过
                continue

            # 这一章可能被重试一次,attempt=1 是首次,attempt=2 是重试
            attempt = 1
            while True:
                await ai_task_manager.append_event(
                    task_id,
                    "chapter_start",
                    {
                        "chapter_index": ci,
                        "total": len(chapter_ids_in_order),
                        "chapter_id": chapter.id,
                        "order_index": chapter.order_index,
                        "title": chapter.title,
                        "attempt": attempt,
                    },
                )

                # 1) 快照(覆盖前兜底,与手动 AI 写作一致)
                try:
                    chapter_version_service.snapshot(
                        db, chapter.id, reason="ai_overwrite", label="auto-write"
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning("auto-writer snapshot failed: %s", e)

                # 2) 生成正文
                effective_instruction = _build_carry_instruction(
                    carry_missing, carry_partial, base_extra_instruction
                )
                try:
                    await _generate_chapter(
                        db,
                        task_id,
                        chapter,
                        target_word_count=target_word_count,
                        extra_instruction=effective_instruction,
                        character_ids=character_ids,
                        world_entity_ids=world_entity_ids,
                        item_ids=item_ids,
                    )
                except (AIError, AINotConfiguredError) as e:
                    raise
                db.refresh(chapter)
                await ai_task_manager.append_event(
                    task_id,
                    "generated",
                    {"chapter_id": chapter.id, "word_count": chapter.word_count or 0},
                )

                # 3) 索引(单章抽事件)
                await ai_task_manager.append_event(
                    task_id, "indexing", {"chapter_id": chapter.id}
                )
                try:
                    extracted_count = await _index_chapter(db, chapter)
                except (AIError, AINotConfiguredError) as e:
                    # 索引失败不必整体 stop,降级跳过对账 / 评分
                    logger.warning("auto-writer index failed: %s", e)
                    extracted_count = 0
                # 即使 _index_chapter 抛异常,也让 events_count 反映真实事件数
                events_count = int(
                    db.execute(
                        select(func.count(PlotEvent.id)).where(
                            PlotEvent.chapter_id == chapter.id
                        )
                    ).scalar()
                    or 0
                )
                await ai_task_manager.append_event(
                    task_id,
                    "indexed",
                    {"chapter_id": chapter.id, "events_count": events_count},
                )

                # 4) 对账(如果章节有节拍才有意义)
                covered = partial = missing = 0
                alignment_items: list[dict] = []
                if chapter.beats:
                    await ai_task_manager.append_event(
                        task_id, "aligning", {"chapter_id": chapter.id}
                    )
                    try:
                        align_resp = await chapter_beats_alignment_service.align(
                            db, chapter.id
                        )
                        covered = align_resp.covered
                        partial = align_resp.partial
                        missing = align_resp.missing
                        alignment_items = [it.model_dump() for it in align_resp.items]
                    except (AIError, AINotConfiguredError) as e:
                        logger.warning("auto-writer align failed: %s", e)
                    await ai_task_manager.append_event(
                        task_id,
                        "aligned",
                        {
                            "chapter_id": chapter.id,
                            "covered": covered,
                            "partial": partial,
                            "missing": missing,
                        },
                    )

                # 5) 评分
                overall = None
                score_dump: dict | None = None
                await ai_task_manager.append_event(
                    task_id, "scoring", {"chapter_id": chapter.id}
                )
                try:
                    score_item = await chapter_score_service.score_chapter(db, chapter.id)
                    overall = score_item.overall
                    score_dump = {
                        "writing": score_item.writing,
                        "plot": score_item.plot,
                        "characters": score_item.characters,
                        "overall": score_item.overall,
                        "feedback": score_item.feedback or "",
                    }
                except (AIError, AINotConfiguredError, chapter_score_service.ChapterScoreParseError) as e:
                    logger.warning("auto-writer score failed: %s", e)
                await ai_task_manager.append_event(
                    task_id,
                    "scored",
                    {"chapter_id": chapter.id, **(score_dump or {})},
                )

                # 6) 决策
                decision, reason = _decide_next(
                    mode=mode,
                    score_overall=overall,
                    missing_beats=missing,
                    score_threshold=score_threshold,
                    attempt=attempt,
                )
                await ai_task_manager.append_event(
                    task_id,
                    "chapter_done",
                    {
                        "chapter_id": chapter.id,
                        "decision": decision,
                        "reason": reason,
                        "attempt": attempt,
                    },
                )

                if decision == "retry":
                    attempt += 1
                    continue
                if decision == "stop":
                    stopped_reason = f"第 {chapter.order_index} 章 {reason}"
                    processed += 1
                    # 携带遗留节拍跳出循环
                    carry_missing, carry_partial = _missing_partial_beat_titles(
                        chapter, alignment_items
                    )
                    break

                # pass:更新下一章的 carry,跳出 retry 循环到下一章
                carry_missing, carry_partial = _missing_partial_beat_titles(
                    chapter, alignment_items
                )
                processed += 1
                break

            if stopped_reason is not None:
                break

        await ai_task_manager.append_event(
            task_id,
            "result",
            {
                "processed": processed,
                "stopped_reason": stopped_reason,
                "total": len(chapter_ids_in_order),
            },
        )
        await ai_task_manager.finish(task_id, "done")
    except asyncio.CancelledError:
        await ai_task_manager.finish(task_id, "cancelled")
        raise
    except (AINotConfiguredError, AIError) as e:
        await ai_task_manager.finish(task_id, "error", str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("auto-writer crashed")
        await ai_task_manager.finish(task_id, "error", str(e))
    finally:
        db.close()


async def start_background(
    *,
    project_id: int,
    start_chapter_id: int,
    count: int,
    target_word_count: int,
    extra_instruction: str | None,
    character_ids: list[int],
    world_entity_ids: list[int],
    item_ids: list[int],
    mode: Mode,
    score_threshold: int,
) -> tuple[str, list[int]]:
    """同步收集要处理的章节 id 序列 → 注册任务 → 启动后台协程。

    返回 (task_id, chapter_ids_in_order)。chapter_ids 给前端用来在 UI 上预先标出待处理章节。
    """
    db = SessionLocal()
    try:
        anchor = db.get(Chapter, start_chapter_id)
        if anchor is None or anchor.project_id != project_id:
            raise ValueError("起始章节不存在或不属于该工程")
        stmt = (
            select(Chapter.id)
            .where(
                Chapter.project_id == project_id,
                Chapter.order_index >= anchor.order_index,
            )
            .order_by(Chapter.order_index)
            .limit(max(1, count))
        )
        chapter_ids = list(db.execute(stmt).scalars().all())
    finally:
        db.close()

    if not chapter_ids:
        raise ValueError("没有可写的章节")

    task = await ai_task_manager.register(project_id=project_id)
    coro = run_auto_writer(
        task.id,
        project_id=project_id,
        chapter_ids_in_order=chapter_ids,
        target_word_count=target_word_count,
        base_extra_instruction=extra_instruction,
        character_ids=character_ids,
        world_entity_ids=world_entity_ids,
        item_ids=item_ids,
        mode=mode,
        score_threshold=score_threshold,
    )
    task.handle = asyncio.create_task(coro)
    return task.id, chapter_ids


__all__ = ["run_auto_writer", "start_background", "Mode"]
