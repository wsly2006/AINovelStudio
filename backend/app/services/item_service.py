from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.project import Project
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate


class ItemNotFoundError(Exception):
    pass


class ItemNameConflictError(Exception):
    pass


class ProjectNotFoundForItemError(Exception):
    pass


def list_items(db: Session, project_id: int) -> list[ItemRead]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForItemError(project_id)
    stmt = (
        select(Item).where(Item.project_id == project_id).order_by(Item.name)
    )
    rows = db.execute(stmt).scalars().all()
    return [ItemRead.model_validate(e) for e in rows]


def get_item(db: Session, item_id: int) -> ItemRead:
    e = db.get(Item, item_id)
    if e is None:
        raise ItemNotFoundError(item_id)
    return ItemRead.model_validate(e)


def create_item(db: Session, project_id: int, payload: ItemCreate) -> ItemRead:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForItemError(project_id)

    e = Item(
        project_id=project_id,
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
        raise ItemNameConflictError(payload.name) from exc
    db.refresh(e)
    return ItemRead.model_validate(e)


def update_item(db: Session, item_id: int, payload: ItemUpdate) -> ItemRead:
    e = db.get(Item, item_id)
    if e is None:
        raise ItemNotFoundError(item_id)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(e, k, v)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ItemNameConflictError(data.get("name", "")) from exc
    db.refresh(e)
    return ItemRead.model_validate(e)


def delete_item(db: Session, item_id: int) -> None:
    e = db.get(Item, item_id)
    if e is None:
        raise ItemNotFoundError(item_id)
    db.delete(e)
    db.commit()
