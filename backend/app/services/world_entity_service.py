from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.world_entity import WorldEntity
from app.schemas.world_entity import (
    WorldEntityCreate,
    WorldEntityRead,
    WorldEntityUpdate,
)


class WorldEntityNotFoundError(Exception):
    pass


class WorldEntityNameConflictError(Exception):
    pass


class ProjectNotFoundForWorldError(Exception):
    pass


def list_entities(
    db: Session, project_id: int, kind: str | None = None
) -> list[WorldEntityRead]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForWorldError(project_id)
    stmt = (
        select(WorldEntity)
        .where(WorldEntity.project_id == project_id)
        .order_by(WorldEntity.kind, WorldEntity.name)
    )
    if kind:
        stmt = stmt.where(WorldEntity.kind == kind)
    rows = db.execute(stmt).scalars().all()
    return [WorldEntityRead.model_validate(e) for e in rows]


def get_entity(db: Session, entity_id: int) -> WorldEntityRead:
    e = db.get(WorldEntity, entity_id)
    if e is None:
        raise WorldEntityNotFoundError(entity_id)
    return WorldEntityRead.model_validate(e)


def create_entity(
    db: Session, project_id: int, payload: WorldEntityCreate
) -> WorldEntityRead:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForWorldError(project_id)

    e = WorldEntity(
        project_id=project_id,
        kind=payload.kind,
        name=payload.name,
        aliases=payload.aliases,
        summary=payload.summary,
        description=payload.description,
        tags=payload.tags,
    )
    db.add(e)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise WorldEntityNameConflictError(payload.name) from exc
    db.refresh(e)
    return WorldEntityRead.model_validate(e)


def update_entity(
    db: Session, entity_id: int, payload: WorldEntityUpdate
) -> WorldEntityRead:
    e = db.get(WorldEntity, entity_id)
    if e is None:
        raise WorldEntityNotFoundError(entity_id)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(e, k, v)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise WorldEntityNameConflictError(data.get("name", "")) from exc
    db.refresh(e)
    return WorldEntityRead.model_validate(e)


def delete_entity(db: Session, entity_id: int) -> None:
    e = db.get(WorldEntity, entity_id)
    if e is None:
        raise WorldEntityNotFoundError(entity_id)
    db.delete(e)
    db.commit()


def find_by_kind_name_or_alias(
    db: Session, project_id: int, kind: str, name: str
) -> WorldEntity | None:
    """同 project + 同 kind 下,主名或别名命中即视为同一条目。"""
    stmt = select(WorldEntity).where(
        WorldEntity.project_id == project_id, WorldEntity.kind == kind
    )
    for e in db.execute(stmt).scalars().all():
        if e.name == name:
            return e
        if name in (e.aliases or []):
            return e
    return None


def merge_extracted_entity(
    db: Session,
    project_id: int,
    kind: str,
    extracted: dict,
    chapter_id: int | None,
) -> WorldEntity:
    name = (extracted.get("name") or "").strip()
    if not name:
        raise ValueError("extracted entity missing name")

    existing = find_by_kind_name_or_alias(db, project_id, kind, name)
    if existing:
        new_aliases = set(existing.aliases or [])
        new_aliases.update(extracted.get("aliases") or [])
        new_aliases.discard(existing.name)
        existing.aliases = sorted(new_aliases)

        for field in ("summary", "description"):
            new_val = (extracted.get(field) or "").strip()
            if not new_val:
                continue
            cur = getattr(existing, field) or ""
            if not cur:
                setattr(existing, field, new_val)
            elif new_val not in cur:
                setattr(existing, field, cur + "\n\n" + new_val)

        new_tags = set(existing.tags or [])
        new_tags.update(extracted.get("tags") or [])
        existing.tags = sorted(new_tags)

        db.commit()
        db.refresh(existing)
        return existing

    e = WorldEntity(
        project_id=project_id,
        kind=kind,
        name=name,
        aliases=sorted(set(extracted.get("aliases") or [])),
        summary=extracted.get("summary"),
        description=extracted.get("description"),
        tags=sorted(set(extracted.get("tags") or [])),
        first_seen_chapter_id=chapter_id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e
