"""情节事件工具。"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import plot_service


@tool(category="plot")
@friendly_errors
def list_plot_events(
    project_id: int,
    chapter_id: int | None = None,
) -> list[dict]:
    """列出工程的情节事件,默认全工程返回,按章节顺序。

    chapter_id 可选 — 传了就只返回该章节的事件,这是改写章节前的标准操作:
    先看清楚原本发生了什么,再决定怎么改不破坏关键情节。

    每个事件包含 title / description / character_ids(参与人物) /
    importance(1-5,重要度)/ thread_id(主线绑定)。比读整章正文密度高 10 倍。
    """
    with with_db() as db:
        items = plot_service.list_events(db, project_id)
        if chapter_id is not None:
            items = [it for it in items if it.chapter_id == chapter_id]
        return [it.model_dump(mode="json") for it in items]
