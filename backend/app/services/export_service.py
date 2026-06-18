"""工程导出 / 导入服务。

JSON 格式包含完整结构(含人物 / 关系 / 情节),用于备份与迁移;
Markdown 格式仅含工程信息 + 章节正文,用于阅读 / 分享。
"""

from datetime import UTC, datetime
from io import StringIO

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.character import Character
from app.models.ladder import Ladder
from app.models.plot_event import PlotEvent
from app.models.project import Project
from app.models.relation import CharacterRelation
from app.models.state_event import CharacterStateEvent
from app.models.task import Task
from app.models.world_entity import WorldEntity

EXPORT_FORMAT_VERSION = 1


class ProjectNotFoundForExportError(Exception):
    pass


class InvalidImportError(Exception):
    pass


def export_to_dict(db: Session, project_id: int) -> dict:
    p = db.get(Project, project_id)
    if p is None:
        raise ProjectNotFoundForExportError(project_id)

    return {
        "format": "ai_novel_writer.export",
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "project": {
            "name": p.name,
            "description": p.description,
            "channel": p.channel,
            "genre": p.genre,
            "tags": list(p.tags or []),
            "cover_color": p.cover_color,
            "progression_enabled": p.progression_enabled,
            "words_per_chapter": p.words_per_chapter,
        },
        "ladders": [
            {
                "id": l_.id,
                "name": l_.name,
                "description": l_.description,
                "tiers": l_.tiers or [],
            }
            for l_ in p.ladders
        ],
        "chapters": [
            {
                "id": c.id,
                "order_index": c.order_index,
                "title": c.title,
                "content": c.content or "",
                "summary": c.summary,
                "status": c.status,
            }
            for c in sorted(p.chapters, key=lambda x: x.order_index)
        ],
        "characters": [
            {
                "id": c.id,
                "name": c.name,
                "aliases": c.aliases or [],
                "role": c.role,
                "profile": c.profile,
                "appearance": c.appearance,
                "personality": c.personality,
                "background": c.background,
                "avatar_color": c.avatar_color,
                "first_seen_chapter_id": c.first_seen_chapter_id,
                "ladder_id": c.ladder_id,
                "current_tier_index": c.current_tier_index,
                "current_location_id": c.current_location_id,
            }
            for c in p.characters
        ],
        "relations": [
            {
                "from_id": r.from_id,
                "to_id": r.to_id,
                "type": r.type,
                "description": r.description,
                "chapter_id": r.chapter_id,
            }
            for r in p.relations
        ],
        "plot_events": [
            {
                "chapter_id": e.chapter_id,
                "title": e.title,
                "description": e.description,
                "character_ids": e.character_ids or [],
                "importance": e.importance,
                "order_in_chapter": e.order_in_chapter,
            }
            for e in p.plot_events
        ],
        "world_entities": [
            {
                "kind": w.kind,
                "name": w.name,
                "aliases": w.aliases or [],
                "summary": w.summary,
                "description": w.description,
                "tags": w.tags or [],
                "first_seen_chapter_id": w.first_seen_chapter_id,
            }
            for w in p.world_entities
        ],
        "items": [
            {
                "name": it.name,
                "aliases": it.aliases or [],
                "summary": it.summary,
                "description": it.description,
                "tags": it.tags or [],
                "first_seen_chapter_id": it.first_seen_chapter_id,
            }
            for it in p.items
        ],
        "state_events": [
            {
                "character_id": ev.character_id,
                "chapter_id": ev.chapter_id,
                "kind": ev.kind,
                "payload": ev.payload or {},
                "order_in_chapter": ev.order_in_chapter,
            }
            for ev in (
                # 反查时不依赖 relationship,直接 SQL
                db.query(CharacterStateEvent)
                .filter(CharacterStateEvent.project_id == p.id)
                .order_by(
                    CharacterStateEvent.character_id,
                    CharacterStateEvent.chapter_id,
                    CharacterStateEvent.order_in_chapter,
                )
                .all()
            )
        ],
        "tasks": [
            {
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "assignee_ids": t.assignee_ids or [],
                "started_chapter_id": t.started_chapter_id,
                "finished_chapter_id": t.finished_chapter_id,
            }
            for t in p.tasks
        ],
    }


def export_to_markdown(db: Session, project_id: int) -> str:
    p = db.get(Project, project_id)
    if p is None:
        raise ProjectNotFoundForExportError(project_id)

    buf = StringIO()
    buf.write(f"# {p.name}\n\n")
    if p.genre:
        buf.write(f"**类型**:{p.genre}  \n")
    if p.description:
        buf.write(f"**简介**:{p.description}  \n")
    buf.write("\n---\n\n")

    for chapter in sorted(p.chapters, key=lambda x: x.order_index):
        sub = (chapter.title or "").strip()
        heading = f"第 {chapter.order_index} 章"
        if sub:
            heading += f" {sub}"
        buf.write(f"## {heading}\n\n")
        if chapter.summary:
            buf.write(f"> {chapter.summary}\n\n")
        if chapter.content:
            buf.write(chapter.content.rstrip())
            buf.write("\n\n")
    return buf.getvalue()


def import_from_dict(db: Session, data: dict, *, name_override: str | None = None) -> Project:
    """从导出 dict 还原一个新工程,旧 id 在过程中重映射到新 id。"""
    if not isinstance(data, dict) or data.get("format") != "ai_novel_writer.export":
        raise InvalidImportError("文件格式不匹配,需要 ai_novel_writer.export 导出文件")

    proj_data = data.get("project") or {}
    name = (name_override or proj_data.get("name") or "导入工程").strip()
    if not name:
        raise InvalidImportError("工程名为空")

    # 重名时自动加后缀
    base_name = name
    suffix = 1
    while db.query(Project).filter(Project.name == name).first() is not None:
        suffix += 1
        name = f"{base_name} ({suffix})"

    project = Project(
        name=name,
        description=proj_data.get("description"),
        channel=proj_data.get("channel"),
        genre=proj_data.get("genre"),
        tags=list(proj_data.get("tags") or []),
        cover_color=proj_data.get("cover_color"),
        progression_enabled=bool(proj_data.get("progression_enabled", False)),
        words_per_chapter=int(proj_data.get("words_per_chapter") or 4000),
    )
    db.add(project)
    db.flush()  # 拿到 project.id

    # 阶梯:旧 id → 新 id 映射(人物会引用)
    ladder_id_map: dict[int, int] = {}
    for ld in data.get("ladders") or []:
        old_id = ld.get("id")
        ladder = Ladder(
            project_id=project.id,
            name=(ld.get("name") or "未命名")[:60],
            description=ld.get("description"),
            tiers=ld.get("tiers") or [],
        )
        db.add(ladder)
        db.flush()
        if old_id is not None:
            ladder_id_map[int(old_id)] = ladder.id

    # 章节:旧 id → 新 id 映射
    chapter_id_map: dict[int, int] = {}
    chapters = data.get("chapters") or []
    for c in sorted(chapters, key=lambda x: x.get("order_index", 0)):
        old_id = c.get("id")
        chap = Chapter(
            project_id=project.id,
            title=(c.get("title") or "未命名").strip()[:200],
            order_index=int(c.get("order_index") or 0),
            content=c.get("content") or "",
            summary=c.get("summary"),
            status=c.get("status") or "draft",
            word_count=len("".join((c.get("content") or "").split())),
        )
        db.add(chap)
        db.flush()
        if old_id is not None:
            chapter_id_map[int(old_id)] = chap.id

    # 世界观条目:先建,因为人物的 current_location_id 会引用
    world_id_map: dict[int, int] = {}
    for w in data.get("world_entities") or []:
        kind = (w.get("kind") or "").strip()
        wname = (w.get("name") or "").strip()
        if not kind or not wname:
            continue
        # 历史导出文件可能包含 kind="item" 的旧数据,忽略,真正的物品在
        # 下面的 items 块里;新版导出 world_entities 已不再含物品
        if kind == "item":
            continue
        old_id = w.get("id")
        first_seen_old = w.get("first_seen_chapter_id")
        entity = WorldEntity(
            project_id=project.id,
            kind=kind[:20],
            name=wname[:120],
            aliases=w.get("aliases") or [],
            summary=w.get("summary"),
            description=w.get("description"),
            tags=w.get("tags") or [],
            first_seen_chapter_id=chapter_id_map.get(first_seen_old) if first_seen_old else None,
        )
        db.add(entity)
        db.flush()
        if old_id is not None:
            world_id_map[int(old_id)] = entity.id

    # 物品(从 items 块导入,旧版导出文件这里可能为空)
    from app.models.item import Item

    for it in data.get("items") or []:
        iname = (it.get("name") or "").strip()
        if not iname:
            continue
        first_seen_old = it.get("first_seen_chapter_id")
        item = Item(
            project_id=project.id,
            name=iname[:120],
            aliases=it.get("aliases") or [],
            summary=it.get("summary"),
            description=it.get("description"),
            tags=it.get("tags") or [],
            first_seen_chapter_id=chapter_id_map.get(first_seen_old) if first_seen_old else None,
        )
        db.add(item)
        db.flush()

    # 人物:同样建映射
    character_id_map: dict[int, int] = {}
    for ch in data.get("characters") or []:
        old_id = ch.get("id")
        first_seen_old = ch.get("first_seen_chapter_id")
        old_ladder_id = ch.get("ladder_id")
        old_loc_id = ch.get("current_location_id")
        character = Character(
            project_id=project.id,
            name=(ch.get("name") or "未命名").strip()[:120],
            aliases=ch.get("aliases") or [],
            role=ch.get("role"),
            profile=ch.get("profile"),
            appearance=ch.get("appearance"),
            personality=ch.get("personality"),
            background=ch.get("background"),
            avatar_color=ch.get("avatar_color"),
            first_seen_chapter_id=chapter_id_map.get(first_seen_old) if first_seen_old else None,
            ladder_id=ladder_id_map.get(old_ladder_id) if old_ladder_id else None,
            current_tier_index=ch.get("current_tier_index"),
            current_location_id=world_id_map.get(old_loc_id) if old_loc_id else None,
        )
        db.add(character)
        db.flush()
        if old_id is not None:
            character_id_map[int(old_id)] = character.id

    # 关系:两端必须都能映射上
    for r in data.get("relations") or []:
        new_from = character_id_map.get(int(r.get("from_id") or 0))
        new_to = character_id_map.get(int(r.get("to_id") or 0))
        if not new_from or not new_to or new_from == new_to:
            continue
        rel = CharacterRelation(
            project_id=project.id,
            from_id=new_from,
            to_id=new_to,
            type=(r.get("type") or "未指定")[:40],
            description=r.get("description"),
            chapter_id=chapter_id_map.get(r.get("chapter_id")) if r.get("chapter_id") else None,
        )
        db.add(rel)

    # 情节事件:chapter_id 必须能映射
    for ev in data.get("plot_events") or []:
        new_chap = chapter_id_map.get(int(ev.get("chapter_id") or 0))
        if not new_chap:
            continue
        new_char_ids = [
            character_id_map[int(cid)]
            for cid in (ev.get("character_ids") or [])
            if int(cid) in character_id_map
        ]
        plot = PlotEvent(
            project_id=project.id,
            chapter_id=new_chap,
            title=(ev.get("title") or "未命名")[:200],
            description=ev.get("description"),
            character_ids=new_char_ids,
            importance=max(1, min(5, int(ev.get("importance") or 3))),
            order_in_chapter=int(ev.get("order_in_chapter") or 0),
        )
        db.add(plot)

    # 人物状态事件:character_id 与 chapter_id 都需映射;payload 内的 item_id /
    # location_id / to_id / from_id 也要按 world_id_map 重映射
    for ev in data.get("state_events") or []:
        new_chap = chapter_id_map.get(int(ev.get("chapter_id") or 0))
        new_char = character_id_map.get(int(ev.get("character_id") or 0))
        if not new_chap or not new_char:
            continue
        payload = dict(ev.get("payload") or {})
        for key in ("item_id", "to_id", "from_id"):
            if key in payload and payload[key] is not None:
                old = payload[key]
                payload[key] = world_id_map.get(int(old)) if old else None
        state_ev = CharacterStateEvent(
            project_id=project.id,
            character_id=new_char,
            chapter_id=new_chap,
            kind=(ev.get("kind") or "other")[:30],
            payload=payload,
            order_in_chapter=int(ev.get("order_in_chapter") or 0),
        )
        db.add(state_ev)

    # 任务:assignee_ids 重映射 character;chapter id 重映射
    for t in data.get("tasks") or []:
        new_assignees = [
            character_id_map[int(cid)]
            for cid in (t.get("assignee_ids") or [])
            if int(cid) in character_id_map
        ]
        started = t.get("started_chapter_id")
        finished = t.get("finished_chapter_id")
        task = Task(
            project_id=project.id,
            title=(t.get("title") or "未命名")[:200],
            description=t.get("description"),
            status=(t.get("status") or "pending")[:20],
            priority=max(1, min(5, int(t.get("priority") or 2))),
            assignee_ids=new_assignees,
            started_chapter_id=chapter_id_map.get(started) if started else None,
            finished_chapter_id=chapter_id_map.get(finished) if finished else None,
        )
        db.add(task)

    db.commit()
    db.refresh(project)
    return project
