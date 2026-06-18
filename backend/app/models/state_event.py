"""人物状态事件:tier_up / location_change / item_acquired 等。

事件溯源:Character 表只缓存 current_tier / current_location,真相由事件回放。
查询任意章节点的状态:从工程开始到该章节为止,顺序回放所有事件。
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# 支持的事件类型
EVENT_KINDS = (
    "tier_up",
    "tier_down",
    "location_change",
    "item_acquired",
    "item_lost",
    "injury",
    "other",
)


class CharacterStateEvent(Base):
    __tablename__ = "character_state_events"
    __table_args__ = (
        Index("ix_state_events_project_id", "project_id"),
        Index("ix_state_events_character_id", "character_id"),
        Index("ix_state_events_chapter_id", "chapter_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )

    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # payload 各字段含义见 EVENT_KINDS 注释,统一存 JSON 灵活
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    order_in_chapter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
