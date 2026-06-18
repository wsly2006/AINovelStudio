"""人物状态事件服务 + 快照计算。

事件按 (chapter.order_index, order_in_chapter, event.id) 排序回放。
快照仅包含字段会变化的部分,人物的静态档案(name/profile)不在内。

事件 payload 约定:
  tier_up / tier_down: {"to_index": int, "from_index": int|None, "note": str|None}
  location_change:    {"to_id": int|None, "from_id": int|None, "note": str|None}
  item_acquired:      {"item_id": int, "note": str|None}  // 物品来自 world_entities (kind=item)
  item_lost:          {"item_id": int, "note": str|None}
  injury:             {"description": str, "severity": "light"|"medium"|"heavy"}
  other:              {"note": str}  // 自由文本,不参与状态计算
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.character import Character
from app.models.project import Project
from app.models.state_event import CharacterStateEvent
from app.schemas.state_event import (
    CharacterSnapshot,
    StateEventCreate,
    StateEventRead,
    StateEventUpdate,
)


class StateEventNotFoundError(Exception):
    pass


class InvalidStateEventError(Exception):
    pass


def _validate_chapter(db: Session, project_id: int, chapter_id: int) -> Chapter:
    chap = db.get(Chapter, chapter_id)
    if chap is None or chap.project_id != project_id:
        raise InvalidStateEventError("chapter_id 不属于当前工程")
    return chap


def _validate_character(db: Session, project_id: int, character_id: int) -> Character:
    c = db.get(Character, character_id)
    if c is None or c.project_id != project_id:
        raise InvalidStateEventError("character_id 不属于当前工程")
    return c


def list_events(
    db: Session,
    project_id: int,
    *,
    character_id: int | None = None,
    chapter_id: int | None = None,
) -> list[StateEventRead]:
    stmt = (
        select(CharacterStateEvent, Chapter.order_index.label("co"))
        .join(Chapter, Chapter.id == CharacterStateEvent.chapter_id)
        .where(CharacterStateEvent.project_id == project_id)
    )
    if character_id is not None:
        stmt = stmt.where(CharacterStateEvent.character_id == character_id)
    if chapter_id is not None:
        stmt = stmt.where(CharacterStateEvent.chapter_id == chapter_id)
    stmt = stmt.order_by(
        Chapter.order_index,
        CharacterStateEvent.order_in_chapter,
        CharacterStateEvent.id,
    )
    rows = db.execute(stmt).all()
    return [StateEventRead.model_validate(ev) for ev, _ in rows]


def create_event(
    db: Session,
    project_id: int,
    character_id: int,
    payload: StateEventCreate,
) -> StateEventRead:
    if db.get(Project, project_id) is None:
        raise InvalidStateEventError("工程不存在")
    _validate_character(db, project_id, character_id)
    _validate_chapter(db, project_id, payload.chapter_id)

    ev = CharacterStateEvent(
        project_id=project_id,
        character_id=character_id,
        chapter_id=payload.chapter_id,
        kind=payload.kind,
        payload=payload.payload or {},
        order_in_chapter=payload.order_in_chapter,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)

    # 顺手刷新人物缓存(若该事件是当前最新一条)
    _maybe_update_character_cache(db, character_id)
    return StateEventRead.model_validate(ev)


def update_event(
    db: Session, event_id: int, payload: StateEventUpdate
) -> StateEventRead:
    ev = db.get(CharacterStateEvent, event_id)
    if ev is None:
        raise StateEventNotFoundError(event_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ev, k, v)
    db.commit()
    db.refresh(ev)
    _maybe_update_character_cache(db, ev.character_id)
    return StateEventRead.model_validate(ev)


def delete_event(db: Session, event_id: int) -> None:
    ev = db.get(CharacterStateEvent, event_id)
    if ev is None:
        raise StateEventNotFoundError(event_id)
    cid = ev.character_id
    db.delete(ev)
    db.commit()
    _maybe_update_character_cache(db, cid)


# ============ 快照计算 ============


def compute_snapshot(
    db: Session,
    character_id: int,
    *,
    as_of_chapter_id: int | None = None,
) -> CharacterSnapshot:
    """从所有事件回放出某时间点的人物状态。

    as_of_chapter_id=None → 回放全部事件,得到当前状态。
    否则只回放到该章节(包含本章节)为止。
    """
    c = db.get(Character, character_id)
    if c is None:
        raise InvalidStateEventError(f"人物不存在: {character_id}")

    boundary_order = None
    if as_of_chapter_id is not None:
        chap = db.get(Chapter, as_of_chapter_id)
        if chap is None:
            raise InvalidStateEventError(f"章节不存在: {as_of_chapter_id}")
        boundary_order = chap.order_index

    stmt = (
        select(CharacterStateEvent, Chapter.order_index.label("co"))
        .join(Chapter, Chapter.id == CharacterStateEvent.chapter_id)
        .where(CharacterStateEvent.character_id == character_id)
        .order_by(
            Chapter.order_index,
            CharacterStateEvent.order_in_chapter,
            CharacterStateEvent.id,
        )
    )
    rows = db.execute(stmt).all()

    # 初始状态:取人物表的"初始字段"——这里我们假设手动填的 ladder/tier/location
    # 是"故事开始前"的状态。事件记录变化,从此基线推进。
    tier_index: int | None = c.current_tier_index
    location_id: int | None = c.current_location_id
    items: list[int] = []
    injuries: list[str] = []
    notes: list[str] = []

    # 但!如果有事件,说明用户显式记录了变化,Character 上的字段可能本身已经是
    # "某个事件"之后的快照。为避免重复计数,我们改成:不取 Character 表当基线,
    # 直接从空状态回放,只把第一条 tier 事件的 from_index 作为初始境界(若有的话)。
    tier_index = None
    location_id = None
    items = []
    injuries = []

    for ev, co in rows:
        if boundary_order is not None and co > boundary_order:
            break
        kind = ev.kind
        p = ev.payload or {}
        if kind in ("tier_up", "tier_down"):
            if tier_index is None and p.get("from_index") is not None:
                tier_index = int(p["from_index"])
            if p.get("to_index") is not None:
                tier_index = int(p["to_index"])
        elif kind == "location_change":
            location_id = p.get("to_id")
        elif kind == "item_acquired":
            iid = p.get("item_id")
            if iid is not None and iid not in items:
                items.append(int(iid))
        elif kind == "item_lost":
            iid = p.get("item_id")
            if iid is not None and iid in items:
                items.remove(int(iid))
        elif kind == "injury":
            desc = p.get("description") or ""
            if desc:
                injuries.append(desc)
        elif kind == "other":
            note = p.get("note") or ""
            if note:
                notes.append(note)

    # 兜底:若没有任何事件,取人物表上的字段作为"初始状态"
    if not rows:
        tier_index = c.current_tier_index
        location_id = c.current_location_id

    return CharacterSnapshot(
        character_id=character_id,
        as_of_chapter_id=as_of_chapter_id,
        as_of_chapter_order=boundary_order,
        tier_index=tier_index,
        location_id=location_id,
        item_ids=items,
        injuries=injuries,
        notes=notes,
    )


def compute_snapshot_before_chapter(
    db: Session, character_id: int, current_chapter: Chapter | None
) -> CharacterSnapshot:
    """取"本章开始前"的快照:只回放 order_index < current 的事件。

    若 current_chapter 为 None 或没有更早章节,返回空状态(或人物基线)。
    """
    if current_chapter is None:
        return compute_snapshot(db, character_id, as_of_chapter_id=None)

    prev_stmt = (
        select(Chapter)
        .where(
            Chapter.project_id == current_chapter.project_id,
            Chapter.order_index < current_chapter.order_index,
        )
        .order_by(Chapter.order_index.desc())
        .limit(1)
    )
    prev = db.execute(prev_stmt).scalars().first()
    if prev is None:
        # 没有前章,取人物基线
        c = db.get(Character, character_id)
        return CharacterSnapshot(
            character_id=character_id,
            as_of_chapter_id=None,
            as_of_chapter_order=None,
            tier_index=c.current_tier_index if c else None,
            location_id=c.current_location_id if c else None,
            item_ids=[],
            injuries=[],
        )
    return compute_snapshot(db, character_id, as_of_chapter_id=prev.id)


def _maybe_update_character_cache(db: Session, character_id: int) -> None:
    """事件变更后,把人物表上的 current_tier / current_location 同步到最新快照。

    这一步是缓存,不是真相;真相在事件表。
    """
    snap = compute_snapshot(db, character_id, as_of_chapter_id=None)
    c = db.get(Character, character_id)
    if c is None:
        return
    if snap.tier_index is not None:
        c.current_tier_index = snap.tier_index
    if snap.location_id is not None:
        c.current_location_id = snap.location_id
    db.commit()
