from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntityKind = Literal["location", "organization", "concept"]


class WorldEntityBase(BaseModel):
    kind: EntityKind
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    summary: str | None = Field(default=None, max_length=400)
    description: str | None = Field(default=None, max_length=8000)
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        return v

    @field_validator("aliases", "tags")
    @classmethod
    def _clean_list(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s and s.strip()]


class WorldEntityCreate(WorldEntityBase):
    pass


class WorldEntityUpdate(BaseModel):
    kind: EntityKind | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    summary: str | None = Field(default=None, max_length=400)
    description: str | None = Field(default=None, max_length=8000)
    tags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        return v


class WorldEntityRead(WorldEntityBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    first_seen_chapter_id: int | None
    created_at: datetime
    updated_at: datetime


class WorldEntityExtractRequest(BaseModel):
    """触发 AI 抽取。kinds 限定要抽哪几类,空表示全抽;
    chapter_ids 为 None 时扫全工程,给定列表时只扫这些章节(用于按本章索引)。"""

    kinds: list[EntityKind] | None = None
    chapter_ids: list[int] | None = None
    mode: str = Field(default="merge", pattern="^(merge|replace)$")
