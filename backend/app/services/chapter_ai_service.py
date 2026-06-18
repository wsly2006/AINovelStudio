"""章节 AI 服务:组装上下文 + 调用 LiteLLM。"""

from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import prompts
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.item import Item
from app.models.ladder import Ladder
from app.models.plot_event import PlotEvent
from app.models.world_entity import WorldEntity
from app.services import plot_thread_service, state_event_service, task_service
from app.services.chapter_service import ChapterNotFoundError

# 反向注入时,最近事件取多少个(按章节顺序倒数)
RECENT_EVENTS_LIMIT = 12


def _build_snapshots_for_prompt(
    db: Session, project_id: int, characters: list[Character], current_chapter: Chapter
) -> dict[int, dict]:
    """为每个参与人物计算"本章开始前"的快照,并把 id 翻译成可读标签。"""
    if not characters:
        return {}

    # 预加载所有用到的 ladder / world entity
    ladder_ids = {c.ladder_id for c in characters if c.ladder_id}
    ladders_map: dict[int, Ladder] = {}
    if ladder_ids:
        rows = db.execute(select(Ladder).where(Ladder.id.in_(ladder_ids))).scalars().all()
        ladders_map = {l_.id: l_ for l_ in rows}

    # 一次性把 project 内的 world_entities 全拉出来,后续按 id 查
    world_rows = (
        db.execute(select(WorldEntity).where(WorldEntity.project_id == project_id))
        .scalars()
        .all()
    )
    world_map: dict[int, WorldEntity] = {w.id: w for w in world_rows}

    # 物品已经从 world_entities 拆到独立的 items 表
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

        # 境界
        if snap.tier_index is not None and c.ladder_id and c.ladder_id in ladders_map:
            tiers = ladders_map[c.ladder_id].tiers or []
            if 0 <= snap.tier_index < len(tiers):
                info["tier_label"] = tiers[snap.tier_index]
            else:
                info["tier_label"] = f"第 {snap.tier_index + 1} 阶"

        # 地点
        if snap.location_id and snap.location_id in world_map:
            info["location_name"] = world_map[snap.location_id].name

        # 持物
        if snap.item_ids:
            names = [item_map[i].name for i in snap.item_ids if i in item_map]
            if names:
                info["item_names"] = names

        if snap.injuries:
            info["injuries"] = snap.injuries

        if info:
            out[c.id] = info
    return out


def _load_chapter_with_siblings(db: Session, chapter_id: int) -> tuple[Chapter, list[Chapter]]:
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)
    stmt = (
        select(Chapter)
        .where(Chapter.project_id == c.project_id)
        .order_by(Chapter.order_index)
    )
    siblings = list(db.execute(stmt).scalars().all())
    return c, siblings


def _load_characters(db: Session, project_id: int, character_ids: list[int] | None) -> list[Character]:
    if not character_ids:
        return []
    stmt = (
        select(Character)
        .where(Character.project_id == project_id, Character.id.in_(character_ids))
        .order_by(Character.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def _load_recent_events(
    db: Session, project_id: int, before_chapter: Chapter | None
) -> list[PlotEvent]:
    """取本章之前章节的事件,按章节顺序后取最后 N 个,再按时间顺序展示。"""
    stmt = (
        select(PlotEvent, Chapter.order_index.label("co"))
        .join(Chapter, Chapter.id == PlotEvent.chapter_id)
        .where(PlotEvent.project_id == project_id)
    )
    if before_chapter is not None:
        stmt = stmt.where(Chapter.order_index < before_chapter.order_index)
    stmt = stmt.order_by(Chapter.order_index, PlotEvent.order_in_chapter, PlotEvent.id)
    rows = db.execute(stmt).all()
    events = [r[0] for r in rows]
    if len(events) > RECENT_EVENTS_LIMIT:
        events = events[-RECENT_EVENTS_LIMIT:]
    return events


def _load_world_entities(
    db: Session, project_id: int, entity_ids: list[int] | None
) -> list[WorldEntity]:
    if not entity_ids:
        return []
    stmt = (
        select(WorldEntity)
        .where(WorldEntity.project_id == project_id, WorldEntity.id.in_(entity_ids))
        .order_by(WorldEntity.kind, WorldEntity.name)
    )
    return list(db.execute(stmt).scalars().all())


def _load_items(
    db: Session, project_id: int, item_ids: list[int] | None
) -> list[Item]:
    if not item_ids:
        return []
    stmt = (
        select(Item)
        .where(Item.project_id == project_id, Item.id.in_(item_ids))
        .order_by(Item.name)
    )
    return list(db.execute(stmt).scalars().all())


async def stream_generate(
    db: Session,
    chapter_id: int,
    *,
    target_word_count: int,
    extra_instruction: str | None,
    character_ids: list[int] | None = None,
    world_entity_ids: list[int] | None = None,
    item_ids: list[int] | None = None,
) -> AsyncGenerator[str, None]:
    chapter, siblings = _load_chapter_with_siblings(db, chapter_id)
    characters = _load_characters(db, chapter.project_id, character_ids)
    recent_events = _load_recent_events(db, chapter.project_id, chapter)
    world_entities = _load_world_entities(db, chapter.project_id, world_entity_ids)
    items = _load_items(db, chapter.project_id, item_ids)
    snapshots = _build_snapshots_for_prompt(db, chapter.project_id, characters, chapter)
    active_tasks = task_service.list_active_for_characters(
        db, chapter.project_id, [c.id for c in characters]
    )
    threads = plot_thread_service.list_active_threads_for_prompt(db, chapter.project_id)
    messages = prompts.build_generate_messages(
        chapter.project,
        chapter,
        siblings,
        target_word_count=target_word_count,
        extra_instruction=extra_instruction,
        characters=characters,
        recent_events=recent_events,
        world_entities=world_entities,
        items=items,
        snapshots_by_id=snapshots,
        active_tasks=active_tasks,
        plot_threads=threads,
        db=db,
    )
    async for delta in ai_client.stream_chat(
        db, messages, scene="chapter.generate", project_id=chapter.project_id
    ):
        yield delta


async def stream_continue(
    db: Session,
    chapter_id: int,
    *,
    cursor_text: str,
    extra_instruction: str | None,
    character_ids: list[int] | None = None,
    world_entity_ids: list[int] | None = None,
    item_ids: list[int] | None = None,
) -> AsyncGenerator[str, None]:
    chapter, siblings = _load_chapter_with_siblings(db, chapter_id)
    characters = _load_characters(db, chapter.project_id, character_ids)
    recent_events = _load_recent_events(db, chapter.project_id, chapter)
    world_entities = _load_world_entities(db, chapter.project_id, world_entity_ids)
    items = _load_items(db, chapter.project_id, item_ids)
    snapshots = _build_snapshots_for_prompt(db, chapter.project_id, characters, chapter)
    active_tasks = task_service.list_active_for_characters(
        db, chapter.project_id, [c.id for c in characters]
    )
    threads = plot_thread_service.list_active_threads_for_prompt(db, chapter.project_id)
    messages = prompts.build_continue_messages(
        chapter.project,
        chapter,
        siblings,
        cursor_text=cursor_text,
        extra_instruction=extra_instruction,
        characters=characters,
        recent_events=recent_events,
        world_entities=world_entities,
        items=items,
        snapshots_by_id=snapshots,
        active_tasks=active_tasks,
        plot_threads=threads,
        db=db,
    )
    async for delta in ai_client.stream_chat(
        db, messages, scene="chapter.continue", project_id=chapter.project_id
    ):
        yield delta


async def stream_rewrite(
    db: Session,
    chapter_id: int,
    *,
    selection: str,
    instruction: str,
    character_ids: list[int] | None = None,
) -> AsyncGenerator[str, None]:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)
    characters = _load_characters(db, chapter.project_id, character_ids)
    threads = plot_thread_service.list_active_threads_for_prompt(db, chapter.project_id)
    messages = prompts.build_rewrite_messages(
        selection=selection,
        instruction=instruction,
        project=chapter.project,
        characters=characters,
        plot_threads=threads,
        db=db,
    )
    async for delta in ai_client.stream_chat(
        db, messages, scene="chapter.rewrite", project_id=chapter.project_id
    ):
        yield delta


async def summarize(db: Session, chapter_id: int) -> str:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)
    messages = prompts.build_summarize_messages(chapter, db=db)
    text = await ai_client.complete(
        db, messages, scene="chapter.summarize", max_tokens=400, project_id=chapter.project_id
    )
    text = text.strip()
    # 顺便回写到 chapter.summary
    chapter.summary = text
    db.commit()
    return text
