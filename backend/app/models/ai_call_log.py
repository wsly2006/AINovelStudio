"""AI 调用日志(token 统计源表)。

每次调用 LiteLLM(complete / stream_chat)写一条,无论成功失败。
查询场景:按天聚合 / 按 scene 聚合 / 按 model 聚合 / 最近 N 条列表。
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AICallLog(Base):
    __tablename__ = "ai_call_logs"
    __table_args__ = (
        # 列表 / 按天聚合都靠 created_at 走索引
        Index("ix_ai_call_logs_created_at", "created_at"),
        Index("ix_ai_call_logs_scene", "scene"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # 调用场景标签,如 chapter.generate / analysis.relations / settings.test
    scene: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # 是否流式(影响 token 是否准确;有些 provider 流式 usage 拿不到)
    stream: Mapped[bool] = mapped_column(default=False, nullable=False)

    # token 统计;provider 不返回时全为 None
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")  # ok / error
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
