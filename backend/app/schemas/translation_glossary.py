from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 与 model 的 ENTRY_TYPES 对齐;Pydantic 校验入参用
ENTRY_TYPES = ("person", "place", "org", "term", "skill", "item", "other")
SUPPORTED_LANGS = ("en-US", "es-ES", "id-ID", "ja-JP", "ko-KR", "vi-VN")


def _strip_or_raise(v: str, name: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError(f"{name} 不能为空")
    return v


class GlossaryBase(BaseModel):
    source: str = Field(min_length=1, max_length=200)
    target: str = Field(default="", max_length=200)
    target_lang: str = Field(default="en-US", min_length=2, max_length=8)
    entry_type: str = Field(default="other")
    notes: str | None = Field(default=None, max_length=2000)
    locked: bool = False

    @field_validator("source")
    @classmethod
    def _strip_source(cls, v: str) -> str:
        return _strip_or_raise(v, "source")

    @field_validator("target")
    @classmethod
    def _strip_target(cls, v: str) -> str:
        # target 允许为空(seed 时还没填),只去空白
        return v.strip()

    @field_validator("entry_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in ENTRY_TYPES:
            raise ValueError(f"entry_type 必须是 {ENTRY_TYPES} 之一")
        return v


class GlossaryCreate(GlossaryBase):
    pass


class GlossaryUpdate(BaseModel):
    source: str | None = Field(default=None, min_length=1, max_length=200)
    target: str | None = Field(default=None, max_length=200)
    target_lang: str | None = Field(default=None, min_length=2, max_length=8)
    entry_type: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    locked: bool | None = None

    @field_validator("source")
    @classmethod
    def _strip_source(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _strip_or_raise(v, "source")

    @field_validator("target")
    @classmethod
    def _strip_target(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip()

    @field_validator("entry_type")
    @classmethod
    def _check_type(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if v not in ENTRY_TYPES:
            raise ValueError(f"entry_type 必须是 {ENTRY_TYPES} 之一")
        return v


class GlossaryRead(GlossaryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime


class GlossarySeedRequest(BaseModel):
    target_lang: str = Field(default="en-US", min_length=2, max_length=8)
    # overwrite=False 时已存在的 source 会跳过;True 会用同名条目覆盖 target/notes
    # 但 locked=True 的行始终不动
    overwrite: bool = False


class GlossarySeedResult(BaseModel):
    created: int
    skipped: int
    updated: int
