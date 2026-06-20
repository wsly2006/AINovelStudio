"""章节工具:列表 / 详情 / 更新。"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.schemas.chapter import ChapterUpdate
from app.services import chapter_service, chapter_version_service


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
