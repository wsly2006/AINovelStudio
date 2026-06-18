from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PromptTemplate(Base):
    """用户对内置提示词的覆盖。

    本表只在用户改动过的 prompt 上有一行;没改的 prompt 不入库,
    直接走 prompt_registry 里的内置默认值。
    一键还原 = 删除对应行。
    """

    __tablename__ = "prompt_templates"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    system_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_template: Mapped[str] = mapped_column(Text, nullable=False, default="")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
