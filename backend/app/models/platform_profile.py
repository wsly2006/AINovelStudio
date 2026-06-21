"""平台 Profile 模型。

一个 profile 描述某个发布平台（KDP / Webnovel / 起点 ...）需要哪些
导出格式、哪些元数据字段、章节策略与编码偏好。

数据来源：
- 系统预制（is_preset=True）由启动时 seed，不允许删除；
- 用户自建（is_preset=False）走 API CRUD。
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlatformProfile(Base):
    __tablename__ = "platform_profiles"
    __table_args__ = (UniqueConstraint("code", name="uq_platform_profiles_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 平台短码,全局唯一: kdp / webnovel / royalroad / wattpad / qidian / fanqie / jjwxc / generic
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # 地区分组,用于 UI 区分国内/海外: global / cn / other
    region: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    # 系统预制不可删,改也只能改 notes 这类非结构字段
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 该平台支持的导出格式列表,首项视为推荐: ["epub", "docx"]
    formats: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # whole_book / per_chapter / both
    chapter_strategy: Mapped[str] = mapped_column(String(20), nullable=False, default="whole_book")
    # 元数据声明 schema: list[ {key,label,required,type,max_len,max_count,hint} ]
    # 仅作 UI 校验提示,不约束 Project 表结构
    metadata_schema: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # txt 默认编码,gb18030 / utf-8 / null(非 txt 平台留空)
    encoding: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 平台注意事项,markdown
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
