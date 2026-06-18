from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.project import Project
from app.models.relation import CharacterRelation
from app.schemas.relation import RelationCreate, RelationRead, RelationUpdate


class RelationNotFoundError(Exception):
    pass


class InvalidRelationError(Exception):
    pass


def _validate_endpoints(db: Session, project_id: int, from_id: int, to_id: int) -> None:
    if from_id == to_id:
        raise InvalidRelationError("自己不能与自己建立关系")
    stmt = select(Character.id).where(
        Character.id.in_([from_id, to_id]), Character.project_id == project_id
    )
    rows = {row[0] for row in db.execute(stmt).all()}
    if from_id not in rows or to_id not in rows:
        raise InvalidRelationError("from_id / to_id 必须属于当前工程的人物")


def list_relations(db: Session, project_id: int) -> list[RelationRead]:
    stmt = (
        select(CharacterRelation)
        .where(CharacterRelation.project_id == project_id)
        .order_by(CharacterRelation.created_at)
    )
    rows = db.execute(stmt).scalars().all()
    return [RelationRead.model_validate(r) for r in rows]


def create_relation(
    db: Session, project_id: int, payload: RelationCreate
) -> RelationRead:
    if db.get(Project, project_id) is None:
        raise InvalidRelationError("工程不存在")
    _validate_endpoints(db, project_id, payload.from_id, payload.to_id)

    r = CharacterRelation(
        project_id=project_id,
        from_id=payload.from_id,
        to_id=payload.to_id,
        type=payload.type,
        description=payload.description,
        chapter_id=payload.chapter_id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return RelationRead.model_validate(r)


def update_relation(db: Session, relation_id: int, payload: RelationUpdate) -> RelationRead:
    r = db.get(CharacterRelation, relation_id)
    if r is None:
        raise RelationNotFoundError(relation_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return RelationRead.model_validate(r)


def delete_relation(db: Session, relation_id: int) -> None:
    r = db.get(CharacterRelation, relation_id)
    if r is None:
        raise RelationNotFoundError(relation_id)
    db.delete(r)
    db.commit()


def find_existing(
    db: Session, project_id: int, from_id: int, to_id: int, type_: str
) -> CharacterRelation | None:
    stmt = select(CharacterRelation).where(
        CharacterRelation.project_id == project_id,
        CharacterRelation.from_id == from_id,
        CharacterRelation.to_id == to_id,
        CharacterRelation.type == type_,
    )
    return db.execute(stmt).scalars().first()
