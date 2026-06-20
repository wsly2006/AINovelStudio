"""工程级只读工具。"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import project_service


@tool(category="projects")
@friendly_errors
def list_projects() -> list[dict]:
    """列出所有小说工程。

    返回每个工程的基本信息(id, name, genre, channel, tags, chapter_count,
    word_count, last_edited_at...),按最近编辑时间倒序。

    通常作为对话的第一步:用户提到"那本仙侠""第三本"时,先调这个找 id。
    """
    with with_db() as db:
        items = project_service.list_projects(db)
        return [it.model_dump(mode="json") for it in items]


@tool(category="projects")
@friendly_errors
def get_project(project_id: int) -> dict:
    """读取单个工程的详细信息(含简介、世界观大纲、设置、统计字段)。"""
    with with_db() as db:
        return project_service.get_project(db, project_id).model_dump(mode="json")
