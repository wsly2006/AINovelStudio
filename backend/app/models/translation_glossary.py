from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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


# 术语类型:对应来源/分类,翻译时不同类型可走不同策略
# person/place/org 通常音译,term/skill 多走对齐 + 注释,item 倾向直译
ENTRY_TYPES = ("person", "place", "org", "term", "skill", "item", "other")


class TranslationGlossary(Base):
    """项目级翻译术语表。给翻译 pipeline 兜底名词一致性。

    一个 (project_id, source, target_lang) 是一条记录:
    同一项目同一中文词,在同一目标语下只有一条译法。
    """

    __tablename__ = "translation_glossary"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "source", "target_lang",
            name="uq_glossary_project_source_lang",
        ),
        Index("ix_glossary_project_lang", "project_id", "target_lang"),
        Index("ix_glossary_project_type", "project_id", "entry_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    source: Mapped[str] = mapped_column(String(200), nullable=False)
    target: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    target_lang: Mapped[str] = mapped_column(String(8), nullable=False, default="en-US")
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False, default="other")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 锁定后不被自动抽取/批量更新覆盖,保护人工校对结果
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project")
