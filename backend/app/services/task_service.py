from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.project import Project
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate


class TaskNotFoundError(Exception):
    pass


class InvalidTaskError(Exception):
    pass


# 状态排序权重(用于列表展示):in_progress 在前
_STATUS_WEIGHT = {"in_progress": 0, "pending": 1, "done": 2, "abandoned": 3}


def _validate_assignees(db: Session, project_id: int, ids: list[int]) -> list[int]:
    if not ids:
        return []
    rows = (
        db.execute(
            select(Character.id).where(
                Character.project_id == project_id, Character.id.in_(ids)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


def list_tasks(db: Session, project_id: int, *, status: str | None = None) -> list[TaskRead]:
    stmt = select(Task).where(Task.project_id == project_id)
    if status:
        stmt = stmt.where(Task.status == status)
    rows = db.execute(stmt).scalars().all()
    rows = sorted(
        rows,
        key=lambda t: (_STATUS_WEIGHT.get(t.status, 9), -t.priority, t.created_at),
    )
    return [TaskRead.model_validate(t) for t in rows]


def create_task(db: Session, project_id: int, payload: TaskCreate) -> TaskRead:
    if db.get(Project, project_id) is None:
        raise InvalidTaskError("工程不存在")

    # 仅保留属于本工程的 assignee_ids
    valid_assignees = _validate_assignees(db, project_id, payload.assignee_ids)

    t = Task(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        assignee_ids=valid_assignees,
        started_chapter_id=payload.started_chapter_id,
        finished_chapter_id=payload.finished_chapter_id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return TaskRead.model_validate(t)


def update_task(db: Session, task_id: int, payload: TaskUpdate) -> TaskRead:
    t = db.get(Task, task_id)
    if t is None:
        raise TaskNotFoundError(task_id)

    data = payload.model_dump(exclude_unset=True)
    if "assignee_ids" in data:
        data["assignee_ids"] = _validate_assignees(db, t.project_id, data["assignee_ids"] or [])
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return TaskRead.model_validate(t)


def delete_task(db: Session, task_id: int) -> None:
    t = db.get(Task, task_id)
    if t is None:
        raise TaskNotFoundError(task_id)
    db.delete(t)
    db.commit()


def list_active_for_characters(
    db: Session, project_id: int, character_ids: list[int]
) -> list[Task]:
    """供 prompt 反向注入用:给定人物的进行中 / 待办任务,按优先级排序。"""
    if not character_ids:
        return []
    stmt = select(Task).where(
        Task.project_id == project_id,
        Task.status.in_(("pending", "in_progress")),
    )
    rows = db.execute(stmt).scalars().all()
    matched = []
    char_set = set(character_ids)
    for t in rows:
        if not t.assignee_ids:
            continue
        if any(cid in char_set for cid in t.assignee_ids):
            matched.append(t)
    return sorted(matched, key=lambda t: (-t.priority, t.created_at))
