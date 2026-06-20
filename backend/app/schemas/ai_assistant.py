"""AI 助手会话 / 消息 schema。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant", "system"]


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    chapter_id: int | None = None


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    chapter_id: int | None = None


class ConversationOut(BaseModel):
    id: int
    project_id: int
    chapter_id: int | None
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: MessageRole
    content: str
    chapter_id: int | None
    selection_text: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SendMessageBody(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    # 本次消息绑定的章节(可空 → 工程级提问)
    chapter_id: int | None = None
    # 编辑器选区文本(可空)
    selection_text: str | None = Field(default=None, max_length=20_000)
    # 是否注入「当前章节正文」(默认 True;长章节用户可关掉省 token)
    include_chapter_content: bool = True
    # 用户额外勾选的人物 / 世界观 / 物品 id
    character_ids: list[int] = Field(default_factory=list)
    world_entity_ids: list[int] = Field(default_factory=list)
    item_ids: list[int] = Field(default_factory=list)


class PreviewMessageBody(SendMessageBody):
    """复用 SendMessageBody,只为语义清晰。"""
