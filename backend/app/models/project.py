from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.chapter import Chapter
    from app.models.character import Character
    from app.models.item import Item
    from app.models.ladder import Ladder
    from app.models.plot_event import PlotEvent
    from app.models.plot_thread import PlotThread
    from app.models.relation import CharacterRelation
    from app.models.task import Task
    from app.models.world_entity import WorldEntity


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("name", name="uq_projects_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 总纲:长篇大纲,包含结局走向。注入每次生成 / 续写 / 改写的 prompt,
    # 让 AI 写每一章时都知道整本书该往哪走。和 description(短简介)不同。
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 频道:male / female / danmei / yuri / general,决定写作视角与读者预期
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # 标签:正交于 genre 的多选标签,如 末世 / 穿越 / 重生 / 系统 / 异能
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cover_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    progression_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 每章目标字数:新建工程时填,「生成本章」抽屉默认值用它,缺省按 4000 字。
    words_per_chapter: Mapped[int] = mapped_column(Integer, nullable=False, default=4000)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    chapters: Mapped[list["Chapter"]] = relationship(
        "Chapter",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Chapter.order_index",
    )

    characters: Mapped[list["Character"]] = relationship(
        "Character",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Character.created_at",
    )

    relations: Mapped[list["CharacterRelation"]] = relationship(
        "CharacterRelation",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CharacterRelation.created_at",
    )

    plot_events: Mapped[list["PlotEvent"]] = relationship(
        "PlotEvent",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    plot_threads: Mapped[list["PlotThread"]] = relationship(
        "PlotThread",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlotThread.order_index, PlotThread.id",
    )

    world_entities: Mapped[list["WorldEntity"]] = relationship(
        "WorldEntity",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WorldEntity.kind, WorldEntity.name",
    )

    items: Mapped[list["Item"]] = relationship(
        "Item",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Item.name",
    )

    ladders: Mapped[list["Ladder"]] = relationship(
        "Ladder",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Ladder.created_at",
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Task.created_at",
    )
