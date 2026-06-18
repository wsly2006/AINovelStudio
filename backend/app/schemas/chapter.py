from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChapterStatus = Literal["draft", "writing", "done"]


class ChapterCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    summary: str | None = Field(default=None, max_length=4000)

    @field_validator("title", mode="before")
    @classmethod
    def _strip(cls, v) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("summary")
    @classmethod
    def _strip_summary(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    status: ChapterStatus | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, v) -> str | None:
        if v is None:
            return None
        return str(v).strip()


class ChapterListItem(BaseModel):
    """列表用 schema,不含 content。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    order_index: int
    summary: str | None
    status: ChapterStatus
    word_count: int
    created_at: datetime
    updated_at: datetime


class ChapterDetail(ChapterListItem):
    """详情,含 content,Phase 3 编辑器使用。"""

    content: str


class ChapterReorder(BaseModel):
    chapter_ids: list[int] = Field(min_length=1)


class ChapterContentUpdate(BaseModel):
    content: str = Field(default="", max_length=2_000_000)


class ChapterContentSaved(BaseModel):
    """PUT content 的返回:仅元信息,避免回传同一份正文。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    word_count: int
    updated_at: datetime
