from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChapterStyleIssue(BaseModel):
    """单条 AI 味命中:原文片段 + 为什么 + 怎么改。"""

    kind: str
    quote: str
    why: str
    suggestion: str


class ChapterStyleCheckItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    issues: list[ChapterStyleIssue]
    # 客观统计信号 — 旧记录可能没有,默认空 dict
    signals: dict[str, Any] = Field(default_factory=dict)
    summary: str
    model: str | None
    word_count: int
    created_at: datetime
