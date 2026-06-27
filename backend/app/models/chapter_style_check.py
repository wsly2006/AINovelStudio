"""章节 AI 文风检查历史。

每次检查写一条,issues 用 JSON 存,留作历史对比;不淘汰、不限上限。
"""

from datetime import datetime

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
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChapterStyleCheck(Base):
    __tablename__ = "chapter_style_checks"
    __table_args__ = (
        Index(
            "ix_chapter_style_checks_chapter_created",
            "chapter_id",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )

    # 命中段落列表,每条:{kind, quote, why, suggestion}
    issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # 客观统计信号(本地计算,不依赖 LLM):句长方差 / 词汇丰富度 / 标点分布 ...
    # 给作者**知情参考**,不做阈值闭环
    signals: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # 整体观感(可选,一两句话总结)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
