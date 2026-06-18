from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.consistency_issue import ISSUE_STATUSES

IssueStatus = Literal["open", "resolved", "dismissed"]


class ConsistencyIssueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    run_id: str
    kind: str
    title: str
    detail: str | None
    related_event_ids: list[int]
    related_character_ids: list[int]
    status: IssueStatus
    created_at: datetime
    updated_at: datetime


class ConsistencyIssueUpdate(BaseModel):
    """目前只支持改 status —— title/detail 由 AI 生成,不让用户随便编辑。"""

    status: IssueStatus

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in ISSUE_STATUSES:
            raise ValueError(f"status 必须是 {ISSUE_STATUSES} 之一")
        return v


class ConsistencyCheckResult(BaseModel):
    """跑一次扫描的返回:本批次新增的 issues + 当前 open 总数。"""

    run_id: str
    issues: list[ConsistencyIssueRead]
    open_count: int = Field(description="跑完后整个工程 status=open 的总数")
