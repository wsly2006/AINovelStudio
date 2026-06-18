from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_characters_project_name"),
        Index("ix_characters_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    first_seen_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )

    # --- 进阶体系(Phase 6) ---
    # ladder_id 指向 ladders 表;ladder 删除时清空,不影响人物
    ladder_id: Mapped[int | None] = mapped_column(
        ForeignKey("ladders.id", ondelete="SET NULL"), nullable=True
    )
    # 当前层级索引(0 起),由事件推导 + 缓存。手动编辑也允许
    current_tier_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 当前所在地点,指向 world_entities (kind=location)
    current_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("world_entities.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="characters")
