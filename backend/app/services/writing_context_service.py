"""写作上下文聚合服务 — 把分散在多张表里的"反向注入"素材组装成结构化数据。

设计要点:
- 输出**结构化数据**(dict / list),不格式化成中文 prompt 段落
  Claude 拿到 JSON 自己组织表达,自家 LiteLLM 流水线另有 chapter_ai_service 负责拼 prompt
- 与 chapter_ai_service 的反向注入逻辑**并行存在**,不互相依赖
  共用底层 service(state_event_service / task_service)即可,不强行抽公共代码
- 只读,不写库,无副作用
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.character import Character
from app.models.item import Item
from app.models.ladder import Ladder
from app.models.plot_event import PlotEvent
from app.models.project import Project
from app.models.task import Task
from app.models.world_entity import WorldEntity
from app.services import state_event_service, task_service
from app.services.chapter_service import ChapterNotFoundError

# 与 chapter_ai_service 保持一致:最近 12 个事件
RECENT_EVENTS_LIMIT = 12

_PRIORITY_LABELS = {1: "低", 2: "中", 3: "中高", 4: "高", 5: "紧急"}


@dataclass
class WritingContext:
    project: dict
    chapter: dict
    previous_chapters: list[dict] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)
    recent_events: list[dict] = field(default_factory=list)
    world_entities: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    active_tasks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "chapter": self.chapter,
            "previous_chapters": self.previous_chapters,
            "characters": self.characters,
            "recent_events": self.recent_events,
            "world_entities": self.world_entities,
            "items": self.items,
            "active_tasks": self.active_tasks,
        }


def _project_brief(p: Project) -> dict:
    """工程基本盘 — 只挑创作时真正需要的字段。"""
    return {
        "id": p.id,
        "name": p.name,
        "genre": p.genre,
        "channel": p.channel,
        "tags": list(p.tags or []),
        "description": p.description,
        "synopsis": p.synopsis,
    }


def _chapter_brief(c: Chapter) -> dict:
    return {
        "id": c.id,
        "order_index": c.order_index,
        "title": c.title,
        "summary": c.summary,
        "status": c.status,
        "word_count": c.word_count,
        "beats": c.beats,  # JSON list[dict] | None
    }


def _previous_chapter_brief(c: Chapter) -> dict:
    """前序章节 — 摘要为主,正文太长不塞。"""
    out = {
        "id": c.id,
        "order_index": c.order_index,
        "title": c.title,
        "summary": c.summary,
    }
    if not c.summary and c.content:
        # 没摘要的章节给个开头节选(80 字),不返回整章
        preview = c.content.strip().replace("\n", " ")[:80]
        out["preview"] = preview if preview else None
    return out


def _character_brief(
    c: Character,
    snapshot: dict | None,
) -> dict:
    """人物档案 + 本章开始前快照(可空)。"""
    out = {
        "id": c.id,
        "name": c.name,
        "aliases": list(c.aliases or []),
        "role": c.role,
        "profile": c.profile,
        "appearance": c.appearance,
        "personality": c.personality,
        "background": c.background,
    }
    if snapshot:
        out["snapshot_before_chapter"] = snapshot
    return out


def _event_brief(ev: PlotEvent, chap_index: dict[int, Chapter]) -> dict:
    chap = chap_index.get(ev.chapter_id)
    return {
        "id": ev.id,
        "chapter_order": chap.order_index if chap else None,
        "chapter_id": ev.chapter_id,
        "title": ev.title,
        "description": ev.description,
        "importance": ev.importance,
    }


def _world_brief(e: WorldEntity) -> dict:
    return {
        "id": e.id,
        "kind": e.kind,  # location / organization / concept
        "name": e.name,
        "aliases": list(e.aliases or []),
        "summary": e.summary,
        "description": e.description,
    }


def _item_brief(it: Item) -> dict:
    return {
        "id": it.id,
        "name": it.name,
        "aliases": list(it.aliases or []),
        "summary": it.summary,
        "description": it.description,
    }


def _task_brief(t: Task, char_names: dict[int, str]) -> dict:
    assignees = [char_names[c] for c in (t.assignee_ids or []) if c in char_names]
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "priority_label": _PRIORITY_LABELS.get(t.priority, "中"),
        "assignee_ids": list(t.assignee_ids or []),
        "assignee_names": assignees,
        "start_chapter_id": t.start_chapter_id,
        "end_chapter_id": t.end_chapter_id,
    }


def _build_character_snapshots(
    db: Session,
    project_id: int,
    characters: list[Character],
    current_chapter: Chapter,
) -> dict[int, dict]:
    """为每个人物算"本章开始前"快照,把 id 翻成可读名。

    与 chapter_ai_service._build_snapshots_for_prompt 同款逻辑,
    但返回结构化数据而不是字符串。
    """
    if not characters:
        return {}

    ladder_ids = {c.ladder_id for c in characters if c.ladder_id}
    ladders_map: dict[int, Ladder] = {}
    if ladder_ids:
        rows = db.execute(select(Ladder).where(Ladder.id.in_(ladder_ids))).scalars().all()
        ladders_map = {l_.id: l_ for l_ in rows}

    world_rows = (
        db.execute(select(WorldEntity).where(WorldEntity.project_id == project_id))
        .scalars()
        .all()
    )
    world_map: dict[int, WorldEntity] = {w.id: w for w in world_rows}

    item_rows = (
        db.execute(select(Item).where(Item.project_id == project_id))
        .scalars()
        .all()
    )
    item_map: dict[int, Item] = {it.id: it for it in item_rows}

    out: dict[int, dict] = {}
    for c in characters:
        snap = state_event_service.compute_snapshot_before_chapter(db, c.id, current_chapter)
        info: dict = {}

        if snap.tier_index is not None and c.ladder_id and c.ladder_id in ladders_map:
            tiers = ladders_map[c.ladder_id].tiers or []
            if 0 <= snap.tier_index < len(tiers):
                info["tier_label"] = tiers[snap.tier_index]
            else:
                info["tier_label"] = f"第 {snap.tier_index + 1} 阶"

        if snap.location_id and snap.location_id in world_map:
            info["location_name"] = world_map[snap.location_id].name

        if snap.item_ids:
            names = [item_map[i].name for i in snap.item_ids if i in item_map]
            if names:
                info["item_names"] = names

        if snap.injuries:
            info["injuries"] = list(snap.injuries)

        if info:
            out[c.id] = info
    return out


def _load_chapter_with_siblings(
    db: Session, chapter_id: int
) -> tuple[Chapter, list[Chapter]]:
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)
    rows = (
        db.execute(
            select(Chapter)
            .where(Chapter.project_id == c.project_id)
            .order_by(Chapter.order_index)
        )
        .scalars()
        .all()
    )
    return c, list(rows)


def _load_recent_events(
    db: Session, project_id: int, before_chapter: Chapter
) -> list[PlotEvent]:
    rows = (
        db.execute(
            select(PlotEvent, Chapter.order_index.label("co"))
            .join(Chapter, Chapter.id == PlotEvent.chapter_id)
            .where(
                PlotEvent.project_id == project_id,
                Chapter.order_index < before_chapter.order_index,
            )
            .order_by(Chapter.order_index, PlotEvent.order_in_chapter, PlotEvent.id)
        )
        .all()
    )
    events = [r[0] for r in rows]
    if len(events) > RECENT_EVENTS_LIMIT:
        events = events[-RECENT_EVENTS_LIMIT:]
    return events


def _load_subset(db: Session, model, project_id: int, ids: list[int] | None):
    if not ids:
        return []
    return list(
        db.execute(
            select(model).where(model.project_id == project_id, model.id.in_(ids))
        )
        .scalars()
        .all()
    )


def assemble(
    db: Session,
    chapter_id: int,
    *,
    character_ids: list[int] | None = None,
    world_entity_ids: list[int] | None = None,
    item_ids: list[int] | None = None,
) -> WritingContext:
    """组装一份完整的写作上下文。

    入参:
    - chapter_id: 在写哪一章 — 决定"本章开始前"快照的截止点
    - character_ids: 本章会出现的人物 id;为空则不带人物档案
    - world_entity_ids: 相关地点/组织/概念 id;为空则不带
    - item_ids: 相关物品 id;为空则不带

    返回 WritingContext,可 to_dict() 成 JSON。
    """
    chapter, siblings = _load_chapter_with_siblings(db, chapter_id)
    project = chapter.project

    characters = _load_subset(db, Character, project.id, character_ids)
    world_entities = _load_subset(db, WorldEntity, project.id, world_entity_ids)
    items = _load_subset(db, Item, project.id, item_ids)
    recent_events = _load_recent_events(db, project.id, chapter)

    # 字符 id → 名字映射,task 的 assignee 用得上
    char_names = {c.id: c.name for c in characters}
    active_tasks = task_service.list_active_for_characters(
        db, project.id, [c.id for c in characters]
    )

    snapshots = _build_character_snapshots(db, project.id, characters, chapter)
    chap_index = {c.id: c for c in siblings}

    return WritingContext(
        project=_project_brief(project),
        chapter=_chapter_brief(chapter),
        previous_chapters=[
            _previous_chapter_brief(c) for c in siblings if c.order_index < chapter.order_index
        ],
        characters=[
            _character_brief(c, snapshots.get(c.id)) for c in characters
        ],
        recent_events=[_event_brief(ev, chap_index) for ev in recent_events],
        world_entities=[_world_brief(e) for e in world_entities],
        items=[_item_brief(it) for it in items],
        active_tasks=[_task_brief(t, char_names) for t in active_tasks],
    )
