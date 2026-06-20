"""任务清单工具(寻师/复仇/夺物等)。"""

from __future__ import annotations

from typing import Literal

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import task_service

TaskStatus = Literal["pending", "in_progress", "done", "abandoned"]


@tool(category="tasks")
@friendly_errors
def list_tasks(
    project_id: int,
    status: TaskStatus | None = None,
) -> list[dict]:
    """列出工程的任务清单。可按状态过滤。

    每个任务带 title / description / priority(1-5) / assignee_ids /
    started_chapter_id / finished_chapter_id。
    返回顺序:先按 status 权重(in_progress > pending > done > abandoned),
    再按优先级降序。
    """
    with with_db() as db:
        items = task_service.list_tasks(db, project_id, status=status)
        return [it.model_dump(mode="json") for it in items]


@tool(category="tasks")
@friendly_errors
def list_active_tasks_for_characters(
    project_id: int,
    character_ids: list[int],
) -> list[dict]:
    """给定人物的进行中/待办任务,按优先级排序。

    "这章主角该干什么"的标准答案 — 拿主角的 character_id 调一下,
    Claude 就能从未完成的目标里挑一个推进剧情。
    比 list_tasks 更精确(过滤了无关任务),也比 get_writing_context 轻量
    (只要任务数据,不要全套上下文)。
    """
    with with_db() as db:
        from app.schemas.task import TaskRead

        rows = task_service.list_active_for_characters(db, project_id, character_ids)
        return [TaskRead.model_validate(t).model_dump(mode="json") for t in rows]
