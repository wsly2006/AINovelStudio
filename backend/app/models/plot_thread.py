from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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


# 主线状态:planning=规划中(还没正式开始)/active=进行中/resolved=已收束/abandoned=已废弃
PLOT_THREAD_STATUSES = ("planning", "active", "resolved", "abandoned")


class PlotThread(Base):
    """主线:跨章节的情节线,声明本书有哪几条故事线在跑、各自要走到哪。

    AI 生成 / 续写 / 改写时,只把 status in (planning, active) 的主线注入 prompt,
    这样 AI 知道还有哪些线没收,该往哪推。
    """

    __tablename__ = "plot_threads"
    __table_args__ = (
        Index("ix_plot_threads_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 起承转合,纯文本自由格式,用户怎么舒服怎么写
    planned_arc: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planning")
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="plot_threads")
