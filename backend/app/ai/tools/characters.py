"""人物工具:列表 / 详情 / 更新。"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.schemas.character import CharacterUpdate
from app.services import character_service


@tool(category="characters")
@friendly_errors
def list_characters(project_id: int) -> list[dict]:
    """列出某个工程的所有人物档案。"""
    with with_db() as db:
        items = character_service.list_characters(db, project_id)
        return [it.model_dump(mode="json") for it in items]


@tool(category="characters")
@friendly_errors
def get_character(character_id: int) -> dict:
    """读取单个人物的完整档案(含外貌、性格、背景、当前境界/位置等)。"""
    with with_db() as db:
        return character_service.get_character(db, character_id).model_dump(mode="json")


@tool(category="characters", dangerous=True)
@friendly_errors
def update_character(
    character_id: int,
    name: str | None = None,
    aliases: list[str] | None = None,
    role: str | None = None,
    profile: str | None = None,
    appearance: str | None = None,
    personality: str | None = None,
    background: str | None = None,
) -> dict:
    """更新单个人物档案。只传需要修改的字段。

    人物档案与「事件溯源」状态(境界/位置/持物/伤情)是分开的:
    这里改的是静态档案(姓名/外貌/性格/背景),涉及当前状态变化的应当用
    record_state_event(Phase 5 提供),不要直接覆盖档案。
    """
    payload: dict = {}
    for field, value in [
        ("name", name),
        ("aliases", aliases),
        ("role", role),
        ("profile", profile),
        ("appearance", appearance),
        ("personality", personality),
        ("background", background),
    ]:
        if value is not None:
            payload[field] = value

    if not payload:
        # 没传任何字段,直接返回当前档案,免得调一遍空 update
        with with_db() as db:
            return character_service.get_character(db, character_id).model_dump(mode="json")

    with with_db() as db:
        item = character_service.update_character(
            db, character_id, CharacterUpdate(**payload)
        )
        return item.model_dump(mode="json")
