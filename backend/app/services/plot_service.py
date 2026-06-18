from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.plot_event import PlotEvent
from app.models.project import Project
from app.schemas.plot_event import PlotEventCreate, PlotEventRead, PlotEventUpdate


class PlotEventNotFoundError(Exception):
    pass


class InvalidPlotEventError(Exception):
    pass


def list_events(db: Session, project_id: int) -> list[PlotEventRead]:
    """按 (chapter.order_index, event.order_in_chapter) 排序。"""
    stmt = (
        select(PlotEvent, Chapter.order_index)
        .join(Chapter, Chapter.id == PlotEvent.chapter_id)
        .where(PlotEvent.project_id == project_id)
        .order_by(Chapter.order_index, PlotEvent.order_in_chapter, PlotEvent.id)
    )
    rows = db.execute(stmt).all()
    return [PlotEventRead.model_validate(e) for e, _ in rows]


def create_event(db: Session, project_id: int, payload: PlotEventCreate) -> PlotEventRead:
    if db.get(Project, project_id) is None:
        raise InvalidPlotEventError("工程不存在")
    chapter = db.get(Chapter, payload.chapter_id)
    if chapter is None or chapter.project_id != project_id:
        raise InvalidPlotEventError("chapter_id 不属于当前工程")

    e = PlotEvent(
        project_id=project_id,
        chapter_id=payload.chapter_id,
        title=payload.title,
        description=payload.description,
        character_ids=payload.character_ids,
        importance=payload.importance,
        order_in_chapter=payload.order_in_chapter,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return PlotEventRead.model_validate(e)


def update_event(db: Session, event_id: int, payload: PlotEventUpdate) -> PlotEventRead:
    e = db.get(PlotEvent, event_id)
    if e is None:
        raise PlotEventNotFoundError(event_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(e, k, v)
    db.commit()
    db.refresh(e)
    return PlotEventRead.model_validate(e)


def delete_event(db: Session, event_id: int) -> None:
    e = db.get(PlotEvent, event_id)
    if e is None:
        raise PlotEventNotFoundError(event_id)
    db.delete(e)
    db.commit()
