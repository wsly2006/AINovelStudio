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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.project import Project


# 状态:open=待处理 / resolved=已修 / dismissed=忽略
ISSUE_STATUSES = ("open", "resolved", "dismissed")


class ConsistencyIssue(Base):
    """情节一致性问题:一次扫描产生一组,run_id 串起来。

    扫完不删旧 issue —— 状态由用户改:已修 / 忽略 / 悬而未决。
    长篇写到后期能查「这本书还欠哪些坑」。
    """

    __tablename__ = "consistency_issues"
    __table_args__ = (
        Index("ix_consistency_issues_project_id", "project_id"),
        Index("ix_consistency_issues_run_id", "run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # 同一次扫描共享的 UUID。不用 FK,run 本身没单独的表。
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_event_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    related_character_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="consistency_issues")
