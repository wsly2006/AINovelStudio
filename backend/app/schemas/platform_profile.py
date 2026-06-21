from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MetadataField(BaseModel):
    """单个元数据字段的声明,仅作 UI 校验提示。"""

    key: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=80)
    required: bool = False
    # text / textarea / chips / select
    type: str = Field(default="text", max_length=20)
    max_len: int | None = None
    max_count: int | None = None  # 仅 chips/select 用
    hint: str | None = Field(default=None, max_length=200)


class PlatformProfileBase(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=80)
    region: Literal["global", "cn", "other"] = "global"
    formats: list[str] = Field(default_factory=list)
    chapter_strategy: Literal["whole_book", "per_chapter", "both"] = "whole_book"
    metadata_schema: list[MetadataField] = Field(default_factory=list)
    encoding: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("code 不能为空")
        return v

    @field_validator("formats")
    @classmethod
    def _clean_formats(cls, v: list[str]) -> list[str]:
        allowed = {"json", "md", "epub", "docx", "txt", "txt_chapters"}
        out: list[str] = []
        for f in v or []:
            f = (f or "").strip().lower()
            if f and f in allowed and f not in out:
                out.append(f)
        return out


class PlatformProfileCreate(PlatformProfileBase):
    """用户自建仅允许:is_preset 始终为 False。"""


class PlatformProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    region: Literal["global", "cn", "other"] | None = None
    formats: list[str] | None = None
    chapter_strategy: Literal["whole_book", "per_chapter", "both"] | None = None
    metadata_schema: list[MetadataField] | None = None
    encoding: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=4000)


class PlatformProfileRead(PlatformProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_preset: bool
    created_at: datetime
    updated_at: datetime
