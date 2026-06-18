from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EventKind = Literal[
    "tier_up", "tier_down", "location_change",
    "item_acquired", "item_lost", "injury", "other",
]


class StateEventBase(BaseModel):
    chapter_id: int
    kind: EventKind
    payload: dict[str, Any] = Field(default_factory=dict)
    order_in_chapter: int = Field(default=0, ge=0)


class StateEventCreate(StateEventBase):
    pass


class StateEventUpdate(BaseModel):
    chapter_id: int | None = None
    kind: EventKind | None = None
    payload: dict[str, Any] | None = None
    order_in_chapter: int | None = Field(default=None, ge=0)


class StateEventRead(StateEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    character_id: int
    created_at: datetime
    updated_at: datetime


class CharacterSnapshot(BaseModel):
    """快照:某章节及之前所有事件回放出的状态。"""

    character_id: int
    as_of_chapter_id: int | None
    as_of_chapter_order: int | None
    tier_index: int | None
    location_id: int | None
    item_ids: list[int]
    injuries: list[str]
    notes: list[str] = Field(default_factory=list)

    @field_validator("item_ids")
    @classmethod
    def _dedup_items(cls, v: list[int]) -> list[int]:
        seen = set()
        out = []
        for x in v:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out
