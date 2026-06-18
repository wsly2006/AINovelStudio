from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlotEventBase(BaseModel):
    chapter_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    character_ids: list[int] = Field(default_factory=list)
    importance: int = Field(default=3, ge=1, le=5)
    order_in_chapter: int = Field(default=0, ge=0)
    thread_id: int | None = None

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title 不能为空")
        return v


class PlotEventCreate(PlotEventBase):
    pass


class PlotEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    character_ids: list[int] | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    order_in_chapter: int | None = Field(default=None, ge=0)
    thread_id: int | None = None


class PlotEventRead(PlotEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
