from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VersionReason = Literal["ai_overwrite", "manual", "restore"]


class ChapterVersionListItem(BaseModel):
    """列表用 schema,不含正文,只给摘要。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    word_count: int
    reason: VersionReason
    label: str | None
    created_at: datetime
    # 给前端列表预览用的摘要,服务层填充
    preview: str = ""


class ChapterVersionDetail(BaseModel):
    """详情:含完整 content。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    content: str
    word_count: int
    reason: VersionReason
    label: str | None
    created_at: datetime


class ChapterVersionCreate(BaseModel):
    """手动快照请求体。"""

    label: str | None = Field(default=None, max_length=120)
