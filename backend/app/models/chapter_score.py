"""章节 AI 评分历史。

每次评分写一条,留着看分数变化曲线;不淘汰、不限上限。
"""

from datetime import datetime

from sqlalchemy import (
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


class ChapterScore(Base):
    __tablename__ = "chapter_scores"
    __table_args__ = (
        # 列表 / 曲线查询都按 (chapter_id, created_at) 索引
        Index("ix_chapter_scores_chapter_created", "chapter_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )

    # 4 维度:文笔 / 情节 / 人物 / 综合,每项 1-10
    writing: Mapped[int] = mapped_column(Integer, nullable=False)
    plot: Mapped[int] = mapped_column(Integer, nullable=False)
    characters: Mapped[int] = mapped_column(Integer, nullable=False)
    overall: Mapped[int] = mapped_column(Integer, nullable=False)
    # 文字反馈,200~400 字左右
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # 评分时调用的模型,展示用
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # 评分时章节字数,做一个轻量上下文
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
