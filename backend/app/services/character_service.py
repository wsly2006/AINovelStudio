from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.project import Project
from app.schemas.character import (
    CharacterCreate,
    CharacterRead,
    CharacterUpdate,
)


class CharacterNotFoundError(Exception):
    pass


class CharacterNameConflictError(Exception):
    pass


class ProjectNotFoundForCharacterError(Exception):
    pass


def list_characters(db: Session, project_id: int) -> list[CharacterRead]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForCharacterError(project_id)
    stmt = (
        select(Character)
        .where(Character.project_id == project_id)
        .order_by(Character.created_at)
    )
    rows = db.execute(stmt).scalars().all()
    return [CharacterRead.model_validate(c) for c in rows]


def get_character(db: Session, character_id: int) -> CharacterRead:
    c = db.get(Character, character_id)
    if c is None:
        raise CharacterNotFoundError(character_id)
    return CharacterRead.model_validate(c)


def create_character(
    db: Session, project_id: int, payload: CharacterCreate
) -> CharacterRead:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForCharacterError(project_id)

    c = Character(
        project_id=project_id,
        name=payload.name,
        aliases=payload.aliases,
        role=payload.role,
        profile=payload.profile,
        appearance=payload.appearance,
        personality=payload.personality,
        background=payload.background,
        avatar_color=payload.avatar_color,
        ladder_id=payload.ladder_id,
        current_tier_index=payload.current_tier_index,
        current_location_id=payload.current_location_id,
    )
    db.add(c)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise CharacterNameConflictError(payload.name) from e
    db.refresh(c)
    return CharacterRead.model_validate(c)


def update_character(
    db: Session, character_id: int, payload: CharacterUpdate
) -> CharacterRead:
    c = db.get(Character, character_id)
    if c is None:
        raise CharacterNotFoundError(character_id)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(c, k, v)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise CharacterNameConflictError(data.get("name", "")) from e
    db.refresh(c)
    return CharacterRead.model_validate(c)


def delete_character(db: Session, character_id: int) -> None:
    c = db.get(Character, character_id)
    if c is None:
        raise CharacterNotFoundError(character_id)
    db.delete(c)
    db.commit()


def find_by_name_or_alias(db: Session, project_id: int, name: str) -> Character | None:
    """供 AI 抽取的 merge 模式使用:同名或别名命中即视作同一人。"""
    stmt = select(Character).where(Character.project_id == project_id)
    for c in db.execute(stmt).scalars().all():
        if c.name == name:
            return c
        if name in (c.aliases or []):
            return c
    return None


def merge_extracted_character(
    db: Session,
    project_id: int,
    extracted: dict,
    chapter_id: int | None,
) -> Character:
    """把 AI 抽取的一份人物数据合并入库。返回最终实体。"""
    name = (extracted.get("name") or "").strip()
    if not name:
        raise ValueError("extracted character missing name")

    existing = find_by_name_or_alias(db, project_id, name)
    if existing:
        # 合并别名
        new_aliases = set(existing.aliases or [])
        new_aliases.update(extracted.get("aliases") or [])
        new_aliases.discard(existing.name)
        existing.aliases = sorted(new_aliases)

        # 字段:已有内容则在末尾追加,新值不为空时
        for field in ("profile", "appearance", "personality", "background"):
            new_val = (extracted.get(field) or "").strip()
            if not new_val:
                continue
            cur = getattr(existing, field) or ""
            if not cur:
                setattr(existing, field, new_val)
            elif new_val not in cur:
                setattr(existing, field, cur + "\n\n" + new_val)

        if not existing.role and extracted.get("role"):
            existing.role = extracted["role"]
        db.commit()
        db.refresh(existing)
        return existing

    c = Character(
        project_id=project_id,
        name=name,
        aliases=sorted(set(extracted.get("aliases") or [])),
        role=extracted.get("role"),
        profile=extracted.get("profile"),
        appearance=extracted.get("appearance"),
        personality=extracted.get("personality"),
        background=extracted.get("background"),
        first_seen_chapter_id=chapter_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
