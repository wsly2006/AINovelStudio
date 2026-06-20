"""世界观条目工具:地点 / 组织 / 概念。"""

from __future__ import annotations

from typing import Literal

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import world_entity_service

WorldKind = Literal["location", "organization", "concept"]


@tool(category="world")
@friendly_errors
def list_world_entities(
    project_id: int,
    kind: WorldKind | None = None,
) -> list[dict]:
    """列出某个工程的世界观条目。

    kind 可选,过滤类型:
    - location: 地点(城邦、宗门所在山头、秘境...)
    - organization: 组织(宗门、势力、商会...)
    - concept: 概念(功法体系、特殊设定、历史事件...)

    用户问"这本书有哪些组织"或"主角去过哪些地方"时调这个,
    比直接问 get_writing_context 省 token。
    """
    with with_db() as db:
        items = world_entity_service.list_entities(db, project_id, kind=kind)
        return [it.model_dump(mode="json") for it in items]


@tool(category="world")
@friendly_errors
def get_world_entity(entity_id: int) -> dict:
    """读取单个世界观条目的完整信息(含别名、详细描述、首次出现章节)。"""
    with with_db() as db:
        return world_entity_service.get_entity(db, entity_id).model_dump(mode="json")
