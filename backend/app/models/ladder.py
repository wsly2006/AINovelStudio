"""进阶阶梯模型。

每个工程可以挂多套阶梯(修仙/武道/魔功),不同人物可走不同体系。
tiers 用 JSON 列存有序数组,index 即层级,从 0 开始。
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


class Ladder(Base):
    __tablename__ = "ladders"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_ladders_project_name"),
        Index("ix_ladders_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(String(400), nullable=True)
    # 有序的层级名称列表,例如 ["炼气期", "筑基期", "金丹期", ...]
    tiers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="ladders")
