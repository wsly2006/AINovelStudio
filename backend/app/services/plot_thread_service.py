from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plot_thread import PlotThread
from app.models.project import Project
from app.schemas.plot_thread import (
    PlotThreadCreate,
    PlotThreadRead,
    PlotThreadUpdate,
)


class PlotThreadNotFoundError(Exception):
    pass


class InvalidPlotThreadError(Exception):
    pass


def list_threads(db: Session, project_id: int) -> list[PlotThreadRead]:
    if db.get(Project, project_id) is None:
        raise InvalidPlotThreadError("工程不存在")
    stmt = (
        select(PlotThread)
        .where(PlotThread.project_id == project_id)
        .order_by(PlotThread.order_index, PlotThread.id)
    )
    rows = db.execute(stmt).scalars().all()
    return [PlotThreadRead.model_validate(t) for t in rows]


def get_thread(db: Session, thread_id: int) -> PlotThread:
    t = db.get(PlotThread, thread_id)
    if t is None:
        raise PlotThreadNotFoundError(thread_id)
    return t


def create_thread(
    db: Session, project_id: int, payload: PlotThreadCreate
) -> PlotThreadRead:
    if db.get(Project, project_id) is None:
        raise InvalidPlotThreadError("工程不存在")

    # 没显式给 order_index 时(默认 0),挂到末尾
    order_index = payload.order_index
    if order_index == 0:
        stmt = select(PlotThread.order_index).where(PlotThread.project_id == project_id)
        existing = db.execute(stmt).scalars().all()
        order_index = (max(existing) + 1) if existing else 1

    t = PlotThread(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        planned_arc=payload.planned_arc,
        status=payload.status,
        importance=payload.importance,
        order_index=order_index,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return PlotThreadRead.model_validate(t)


def update_thread(
    db: Session, thread_id: int, payload: PlotThreadUpdate
) -> PlotThreadRead:
    t = get_thread(db, thread_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return PlotThreadRead.model_validate(t)


def delete_thread(db: Session, thread_id: int) -> None:
    t = get_thread(db, thread_id)
    db.delete(t)
    db.commit()


def list_active_threads_for_prompt(db: Session, project_id: int) -> list[PlotThread]:
    """注入 prompt 时只取 planning + active 的主线;已收 / 废弃的不喂回去。"""
    stmt = (
        select(PlotThread)
        .where(
            PlotThread.project_id == project_id,
            PlotThread.status.in_(("planning", "active")),
        )
        .order_by(PlotThread.order_index, PlotThread.id)
    )
    return list(db.execute(stmt).scalars().all())


def list_events_for_thread(db: Session, thread_id: int) -> list[dict]:
    """这条主线在哪几章发生过什么事件,按章节顺序铺开。"""
    from app.models.chapter import Chapter
    from app.models.plot_event import PlotEvent

    t = db.get(PlotThread, thread_id)
    if t is None:
        raise PlotThreadNotFoundError(thread_id)

    stmt = (
        select(PlotEvent, Chapter.order_index, Chapter.title)
        .join(Chapter, Chapter.id == PlotEvent.chapter_id)
        .where(PlotEvent.thread_id == thread_id)
        .order_by(Chapter.order_index, PlotEvent.order_in_chapter, PlotEvent.id)
    )
    rows = db.execute(stmt).all()
    out = []
    for ev, order_index, ch_title in rows:
        out.append({
            "id": ev.id,
            "chapter_id": ev.chapter_id,
            "chapter_order_index": order_index,
            "chapter_title": ch_title,
            "title": ev.title,
            "description": ev.description,
            "importance": ev.importance,
            "order_in_chapter": ev.order_in_chapter,
        })
    return out
