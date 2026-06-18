from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RelationBase(BaseModel):
    from_id: int
    to_id: int
    type: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    chapter_id: int | None = None

    @field_validator("type")
    @classmethod
    def _strip_type(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("type 不能为空")
        return v


class RelationCreate(RelationBase):
    pass


class RelationUpdate(BaseModel):
    type: str | None = Field(default=None, min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=2000)
    chapter_id: int | None = None


class RelationRead(RelationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
