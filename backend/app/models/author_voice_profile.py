"""作者声音档案。

一个项目一份(project_id 唯一)。
quirks: 离散的语癖短语 ["他总把'当然'挂在嘴边", ...],拼 prompt 时一条一行;
style_notes: 跨段落的风格自由描述,直接整段插入 system prompt。

设计选择:不做"作者级跨项目复用",留到真有第二个项目想共享时再说;
当前阶段加一层"作者 → 项目"间接性是过度抽象。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuthorVoiceProfile(Base):
    __tablename__ = "author_voice_profiles"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_author_voice_profiles_project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    quirks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    style_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
