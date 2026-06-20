"""章节版本工具 — Phase 3 写工具的安全网。

list_chapter_versions 是只读的;
restore_chapter_version 是 dangerous(写),env 开关关时不暴露。
"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import chapter_version_service


@tool(category="versions")
@friendly_errors
def list_chapter_versions(chapter_id: int) -> list[dict]:
    """列出章节的历史版本快照,最多保留最近 5 条,按创建时间倒序。

    每条版本带 reason(ai_overwrite / manual / restore)、word_count、preview
    (前 80 字)、created_at。要看完整正文用 get_chapter_version。
    用户说"刚改坏了,看下之前的版本"时调这个。
    """
    with with_db() as db:
        items = chapter_version_service.list_versions(db, chapter_id)
        return [it.model_dump(mode="json") for it in items]


@tool(category="versions")
@friendly_errors
def get_chapter_version(version_id: int) -> dict:
    """读取单个历史版本的完整正文。先用 list_chapter_versions 拿 version_id。"""
    with with_db() as db:
        return chapter_version_service.get_version(db, version_id).model_dump(mode="json")


@tool(category="versions", dangerous=True)
@friendly_errors
def restore_chapter_version(version_id: int) -> dict:
    """把章节回滚到指定历史版本。

    回滚前会自动把"当前内容"再快照一份(reason='restore'),所以即便选错了版本
    再回滚一次也不会丢数据。

    返回还原后的章节详情(含新的 word_count)。
    """
    with with_db() as db:
        chapter = chapter_version_service.restore(db, version_id)
        # restore 返回 ORM Chapter,这里转成与 get_chapter 一致的 dict
        from app.schemas.chapter import ChapterDetail

        return ChapterDetail.model_validate(chapter).model_dump(mode="json")
