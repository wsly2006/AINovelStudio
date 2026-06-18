"""Token 用量统计 schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TokenSummary(BaseModel):
    """指定日期内的总览。"""

    date: str  # YYYY-MM-DD
    call_count: int
    error_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    avg_duration_ms: int


class TokenBucket(BaseModel):
    """按维度(scene / model / hour)分组的小计。"""

    key: str
    call_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TokenCallItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    scene: str
    model: str
    provider: str | None
    stream: bool
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    duration_ms: int
    status: str
    error: str | None
    project_id: int | None


class TokenStatsResponse(BaseModel):
    summary: TokenSummary
    by_scene: list[TokenBucket]
    by_model: list[TokenBucket]
    by_hour: list[TokenBucket]
    recent: list[TokenCallItem]
