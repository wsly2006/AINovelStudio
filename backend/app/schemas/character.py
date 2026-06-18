from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CharacterBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list)
    role: str | None = Field(default=None, max_length=40)
    profile: str | None = Field(default=None, max_length=4000)
    appearance: str | None = Field(default=None, max_length=2000)
    personality: str | None = Field(default=None, max_length=2000)
    background: str | None = Field(default=None, max_length=4000)
    avatar_color: str | None = Field(default=None, max_length=16)

    # 进阶体系字段(Phase 6)
    ladder_id: int | None = None
    current_tier_index: int | None = Field(default=None, ge=0)
    current_location_id: int | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        return v

    @field_validator("aliases")
    @classmethod
    def _clean_aliases(cls, v: list[str]) -> list[str]:
        return [a.strip() for a in v if a and a.strip()]


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    aliases: list[str] | None = None
    role: str | None = Field(default=None, max_length=40)
    profile: str | None = Field(default=None, max_length=4000)
    appearance: str | None = Field(default=None, max_length=2000)
    personality: str | None = Field(default=None, max_length=2000)
    background: str | None = Field(default=None, max_length=4000)
    avatar_color: str | None = Field(default=None, max_length=16)
    ladder_id: int | None = None
    current_tier_index: int | None = Field(default=None, ge=0)
    current_location_id: int | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        return v


class CharacterRead(CharacterBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    first_seen_chapter_id: int | None
    created_at: datetime
    updated_at: datetime


class CharacterExtractRequest(BaseModel):
    """触发 AI 抽取。chapter_ids 为 None 时,扫描该工程全部章节。"""

    chapter_ids: list[int] | None = None
    mode: str = Field(default="merge", pattern="^(merge|replace)$")
