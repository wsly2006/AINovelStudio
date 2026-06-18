from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AISettings(Base):
    """全局 AI 配置(单行单例)。

    本工具是本地单用户场景,api_key 直接以明文存 SQLite。
    若未来要做多用户/远程部署,需改为加密存储或不入库。

    模型分两个角色:写作(provider/model/...)是必填默认;
    审稿(review_*)可选,留空则评分 / 文风检查 / 一致性检查回落用写作模型。
    """

    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # provider 仅作为 UI 分组标识,真正决定调用的还是 model 名
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="env")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="claude-opus-4-7")
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)

    # 审稿模型(可选)。任一字段为 NULL 视为未配置。
    review_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    review_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    review_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
