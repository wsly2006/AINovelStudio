"""人物关系工具。"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.services import relation_service


@tool(category="relations")
@friendly_errors
def list_relations(
    project_id: int,
    character_id: int | None = None,
) -> list[dict]:
    """列出工程的人物关系。

    每条关系: from_id → type(师徒 / 兄弟 / 仇人 / ...)→ to_id,
    可能带 description 和 chapter_id(关系建立的章节)。

    character_id 可选 — 传了就只返回涉及该人物的关系(双向),
    这是写对话场景前的标准查询:对话语气取决于关系定位。
    """
    with with_db() as db:
        items = relation_service.list_relations(db, project_id)
        if character_id is not None:
            items = [
                it for it in items
                if it.from_id == character_id or it.to_id == character_id
            ]
        return [it.model_dump(mode="json") for it in items]
