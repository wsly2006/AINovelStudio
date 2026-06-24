"""章节版本快照。

只在"重大事件"前后写入,不跟 autosave 走;每章节最多保留 5 条,FIFO 淘汰。
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


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"
    __table_args__ = (
        # 列表查询按 (chapter_id, created_at DESC) 走索引
        Index("ix_chapter_versions_chapter_created", "chapter_id", "created_at"),
        # 翻译后会按 (chapter_id, lang) 拉「该章节的某语种最近版本」
        Index("ix_chapter_versions_chapter_lang_created", "chapter_id", "lang", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False
    )

    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 触发原因:ai_overwrite | manual | restore | translated
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    # 用户手动快照时可填的备注
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # 内容语种;现有数据回填 zh-CN,翻译版本写 en-US 等
    lang: Mapped[str] = mapped_column(
        String(8), nullable=False, default="zh-CN", server_default="zh-CN"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
