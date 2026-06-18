from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.plot_thread import PLOT_THREAD_STATUSES

PlotThreadStatus = Literal["planning", "active", "resolved", "abandoned"]


class PlotThreadBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    planned_arc: str | None = Field(default=None, max_length=8000)
    status: PlotThreadStatus = "planning"
    importance: int = Field(default=3, ge=1, le=5)
    order_index: int = Field(default=0, ge=0)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title 不能为空")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in PLOT_THREAD_STATUSES:
            raise ValueError(f"status 必须是 {PLOT_THREAD_STATUSES} 之一")
        return v


class PlotThreadCreate(PlotThreadBase):
    pass


class PlotThreadUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    planned_arc: str | None = Field(default=None, max_length=8000)
    status: PlotThreadStatus | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    order_index: int | None = Field(default=None, ge=0)


class PlotThreadRead(PlotThreadBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
