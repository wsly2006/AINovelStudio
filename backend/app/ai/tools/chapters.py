"""章节工具:列表 / 详情 / 更新 / 生成正文。"""

from __future__ import annotations

from app.ai.tools.async_util import run_async_blocking
from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.models.chapter import Chapter
from app.schemas.chapter import ChapterUpdate
from app.services import chapter_ai_service, chapter_service, chapter_version_service

# 正文预览截断长度 — 避免把上万字灌回 LLM 上下文
_CONTENT_PREVIEW_LEN = 600


@tool(category="chapters")
@friendly_errors
def list_chapters(project_id: int) -> list[dict]:
    """列出某个工程的所有章节(不含正文)。

    返回 id, title, order_index, summary, status, word_count 等。
    要读章节正文请用 get_chapter。
    """
    with with_db() as db:
        items = chapter_service.list_chapters(db, project_id)
        return [it.model_dump(mode="json") for it in items]


@tool(category="chapters")
@friendly_errors
def get_chapter(chapter_id: int) -> dict:
    """读取单个章节的完整内容,含 content 正文。

    长章节可能数千到上万字,会消耗较多 token。如果只想看摘要,先用
    list_chapters 看 summary 字段。
    """
    with with_db() as db:
        return chapter_service.get_chapter(db, chapter_id).model_dump(mode="json")


@tool(category="chapters", dangerous=True)
@friendly_errors
def update_chapter(
    chapter_id: int,
    title: str | None = None,
    content: str | None = None,
    summary: str | None = None,
    status: str | None = None,
) -> dict:
    """更新单个章节。可同时更新多个字段,只传需要修改的字段即可。

    参数:
    - chapter_id: 章节 id(必填)
    - title: 新标题。传 None 不动,传空串视为清空标题
    - content: 新正文。**会先把当前正文快照到 chapter_versions 再覆盖**,
      最多保留最近 5 条快照,可通过 list_chapter_versions / restore_chapter_version 回滚。
      正文应当是用户已经认可、可以直接落库的最终文本(不是 prompt)
    - summary: 章节摘要
    - status: draft | writing | done

    返回更新后的章节详情。如果你只想改标题,把第一章标题改成"初入凡尘",
    调用方式: update_chapter(chapter_id=1, title="初入凡尘")
    """
    with with_db() as db:
        # 元信息更新走 ChapterUpdate(只对显式传入的字段生效)
        meta_payload: dict = {}
        if title is not None:
            meta_payload["title"] = title
        if summary is not None:
            meta_payload["summary"] = summary
        if status is not None:
            meta_payload["status"] = status

        if meta_payload:
            chapter_service.update_chapter(
                db, chapter_id, ChapterUpdate(**meta_payload)
            )

        # 正文更新 — 写前快照,覆盖式写入
        if content is not None:
            chapter_version_service.snapshot(
                db, chapter_id, reason="ai_overwrite", commit=False
            )
            chapter_service.save_content(db, chapter_id, content)

        # 重新拉取最终状态返回
        return chapter_service.get_chapter(db, chapter_id).model_dump(mode="json")


@tool(category="chapters", dangerous=True)
@friendly_errors
def generate_chapter_content(
    chapter_id: int,
    target_word_count: int | None = None,
    extra_instruction: str | None = None,
    character_ids: list[int] | None = None,
    world_entity_ids: list[int] | None = None,
    item_ids: list[int] | None = None,
    save: bool = False,
) -> dict:
    """基于工程上下文为指定章节生成正文。同步阻塞,跑完才返回。

    走的是和前端「AI 生成」按钮完全一样的服务层 (chapter_ai_service.stream_generate),
    因此会自动带上工程简介 / 大纲 / 前序摘要 / 人物档案 / 本章前状态快照 /
    最近情节 / 世界观 / 进行中任务 / 作者风格 profile。

    参数:
    - chapter_id: 目标章节 id(必填)
    - target_word_count: 目标字数。不传就用 project.words_per_chapter(默认 4000)
    - extra_instruction: 追加到 prompt 的自由指令,如"这一章要引出反派"
    - character_ids / world_entity_ids / item_ids: 本章会出现的元素,粒度可控
    - save: True 时把生成结果直接落库到 chapter.content(写前自动快照旧内容
      到 chapter_versions,最多保留最近 5 条,可回滚)。默认 False —— 只返回
      生成的正文,由调用方决定要不要再用 update_chapter 落库

    返回 {chapter_id, word_count, content_preview, truncated, saved, content?}。
    - content_preview: 正文前 600 字,方便快速人工审阅
    - truncated: 是否被截断
    - content: 仅在 save=False 时带完整正文(可能上万字);save=True 时不返回全文
      避免和数据库冗余

    典型用法:
        # 先看效果,再决定要不要落库
        r = generate_chapter_content(chapter_id=98, target_word_count=3500)
        # 满意的话:update_chapter(chapter_id=98, content=r["content"], status="draft")

        # 或者一步到位
        generate_chapter_content(chapter_id=98, save=True)
    """
    # SQLAlchemy Session 非线程安全 — 生成流程要跑在独立线程的 event loop 里,
    # 所以 session 也必须在那个线程里创建 / 使用 / 关闭。这里只在主线程做参数校验
    # 需要用到的一次性读取,不把 session 传进 _collect
    from app.database import SessionLocal
    from app.services.chapter_service import ChapterNotFoundError

    async def _collect() -> tuple[str, int, bool]:
        db = SessionLocal()
        try:
            chapter_orm = db.get(Chapter, chapter_id)
            if chapter_orm is None:
                raise ChapterNotFoundError(chapter_id)
            resolved = (
                target_word_count or chapter_orm.project.words_per_chapter or 4000
            )
            buf: list[str] = []
            async for delta in chapter_ai_service.stream_generate(
                db,
                chapter_id,
                target_word_count=resolved,
                extra_instruction=extra_instruction,
                character_ids=character_ids,
                world_entity_ids=world_entity_ids,
                item_ids=item_ids,
            ):
                buf.append(delta)
            content = "".join(buf)

            saved = False
            if save and content:
                chapter_version_service.snapshot(
                    db, chapter_id, reason="ai_overwrite", commit=False
                )
                chapter_service.save_content(db, chapter_id, content)
                saved = True
            return content, resolved, saved
        finally:
            db.close()

    content, resolved_word_count, saved = run_async_blocking(_collect())

    preview = content[:_CONTENT_PREVIEW_LEN]
    truncated = len(content) > _CONTENT_PREVIEW_LEN
    if truncated:
        preview += "…"

    out: dict = {
        "chapter_id": chapter_id,
        "target_word_count": resolved_word_count,
        "word_count": len(content),
        "content_preview": preview,
        "truncated": truncated,
        "saved": saved,
    }
    if not saved:
        # 未落库才回传完整正文,让调用方能审后再 update_chapter
        out["content"] = content
    return out
