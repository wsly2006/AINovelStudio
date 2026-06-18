from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ladder import LadderCreate, LadderRead, LadderUpdate
from app.services import ladder_service
from app.services.ladder_service import (
    LadderNameConflictError,
    LadderNotFoundError,
    ProjectNotFoundForLadderError,
)

# 工程下集合
project_router = APIRouter(prefix="/api/projects/{project_id}/ladders", tags=["ladders"])
# 单个
ladder_router = APIRouter(prefix="/api/ladders", tags=["ladders"])


@project_router.get("", response_model=list[LadderRead])
def list_ladders(project_id: int, db: Session = Depends(get_db)) -> list[LadderRead]:
    try:
        return ladder_service.list_ladders(db, project_id)
    except ProjectNotFoundForLadderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e


@project_router.post("", response_model=LadderRead, status_code=status.HTTP_201_CREATED)
def create_ladder(
    project_id: int, payload: LadderCreate, db: Session = Depends(get_db)
) -> LadderRead:
    try:
        return ladder_service.create_ladder(db, project_id, payload)
    except ProjectNotFoundForLadderError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e
    except LadderNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"阶梯名已存在: {e}"
        ) from e


@ladder_router.get("/{ladder_id}", response_model=LadderRead)
def get_ladder(ladder_id: int, db: Session = Depends(get_db)) -> LadderRead:
    try:
        return ladder_service.get_ladder(db, ladder_id)
    except LadderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶梯不存在") from e


@ladder_router.patch("/{ladder_id}", response_model=LadderRead)
def update_ladder(
    ladder_id: int, payload: LadderUpdate, db: Session = Depends(get_db)
) -> LadderRead:
    try:
        return ladder_service.update_ladder(db, ladder_id, payload)
    except LadderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶梯不存在") from e
    except LadderNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"阶梯名已存在: {e}"
        ) from e


@ladder_router.delete("/{ladder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ladder(ladder_id: int, db: Session = Depends(get_db)) -> None:
    try:
        ladder_service.delete_ladder(db, ladder_id)
    except LadderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="阶梯不存在") from e
