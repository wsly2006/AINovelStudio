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


# kind 取值约定:首版四类,物品已拆到独立 items 表,这里不再包含 item
ENTITY_KINDS = ("location", "organization", "concept")


class WorldEntity(Base):
    """世界观条目:地名 / 组织 / 物品 / 概念。

    单表 + kind 字段,避免 4 张几乎一样的表。
    aliases 走 JSON;tags 同样,留给前端按标签过滤。
    """

    __tablename__ = "world_entities"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "name", name="uq_world_project_kind_name"),
        Index("ix_world_project_id", "project_id"),
        Index("ix_world_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    first_seen_chapter_id: Mapped[int | None] = mapped_column(
        ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="world_entities")
