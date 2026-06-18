from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services import task_service
from app.services.task_service import InvalidTaskError, TaskNotFoundError

project_router = APIRouter(prefix="/api/projects/{project_id}/tasks", tags=["tasks"])
task_router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@project_router.get("", response_model=list[TaskRead])
def list_tasks(
    project_id: int,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
) -> list[TaskRead]:
    return task_service.list_tasks(db, project_id, status=status_filter)


@project_router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int, payload: TaskCreate, db: Session = Depends(get_db)
) -> TaskRead:
    try:
        return task_service.create_task(db, project_id, payload)
    except InvalidTaskError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@task_router.patch("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)
) -> TaskRead:
    try:
        return task_service.update_task(db, task_id, payload)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail="任务不存在") from e


@task_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> None:
    try:
        task_service.delete_task(db, task_id)
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail="任务不存在") from e
