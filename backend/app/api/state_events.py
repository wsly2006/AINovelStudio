from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.state_event import (
    CharacterSnapshot,
    StateEventCreate,
    StateEventRead,
    StateEventUpdate,
)
from app.services import state_event_service
from app.services.state_event_service import (
    InvalidStateEventError,
    StateEventNotFoundError,
)

# 工程下集合(按人物筛选可选)
project_router = APIRouter(prefix="/api/projects/{project_id}/state-events", tags=["state-events"])
# 单个事件
event_router = APIRouter(prefix="/api/state-events", tags=["state-events"])
# 人物维度集合(创建)
character_router = APIRouter(
    prefix="/api/characters/{character_id}/state-events", tags=["state-events"]
)
# 人物快照
snapshot_router = APIRouter(prefix="/api/characters/{character_id}/snapshot", tags=["state-events"])


@project_router.get("", response_model=list[StateEventRead])
def list_events(
    project_id: int,
    character_id: int | None = None,
    chapter_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[StateEventRead]:
    return state_event_service.list_events(
        db, project_id, character_id=character_id, chapter_id=chapter_id
    )


@character_router.post(
    "", response_model=StateEventRead, status_code=status.HTTP_201_CREATED
)
def create_event(
    character_id: int,
    payload: StateEventCreate,
    db: Session = Depends(get_db),
) -> StateEventRead:
    # 通过 character 反查 project_id,避免双 path 参数
    from app.models.character import Character

    c = db.get(Character, character_id)
    if c is None:
        raise HTTPException(status_code=404, detail="人物不存在")
    try:
        return state_event_service.create_event(db, c.project_id, character_id, payload)
    except InvalidStateEventError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@event_router.patch("/{event_id}", response_model=StateEventRead)
def update_event(
    event_id: int, payload: StateEventUpdate, db: Session = Depends(get_db)
) -> StateEventRead:
    try:
        return state_event_service.update_event(db, event_id, payload)
    except StateEventNotFoundError as e:
        raise HTTPException(status_code=404, detail="事件不存在") from e


@event_router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> None:
    try:
        state_event_service.delete_event(db, event_id)
    except StateEventNotFoundError as e:
        raise HTTPException(status_code=404, detail="事件不存在") from e


@snapshot_router.get("", response_model=CharacterSnapshot)
def get_snapshot(
    character_id: int,
    as_of_chapter_id: int | None = None,
    db: Session = Depends(get_db),
) -> CharacterSnapshot:
    try:
        return state_event_service.compute_snapshot(
            db, character_id, as_of_chapter_id=as_of_chapter_id
        )
    except InvalidStateEventError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
