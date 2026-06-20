"""物品工具(独立于世界观条目)。"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import item_service


@tool(category="items")
@friendly_errors
def list_items(project_id: int) -> list[dict]:
    """列出某个工程的所有物品(法宝、丹药、地图、信物...)。

    跟世界观条目分开管理:物品参与状态溯源(谁在哪一章拿到/丢了),
    所以独立存表。写"主角祭出青锋剑"前先查这个,确认设定一致。
    """
    with with_db() as db:
        items = item_service.list_items(db, project_id)
        return [it.model_dump(mode="json") for it in items]


@tool(category="items")
@friendly_errors
def get_item(item_id: int) -> dict:
    """读取单个物品的完整信息(含别名、详细描述、首次出现章节)。"""
    with with_db() as db:
        return item_service.get_item(db, item_id).model_dump(mode="json")
