from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chapter import (
    ChapterContentSaved,
    ChapterContentUpdate,
    ChapterCreate,
    ChapterDetail,
    ChapterListItem,
    ChapterReorder,
    ChapterUpdate,
)
from app.services import chapter_service
from app.services.chapter_service import (
    ChapterNotFoundError,
    ProjectNotFoundForChapterError,
    ReorderMismatchError,
)

# 工程下的章节集合
project_router = APIRouter(prefix="/api/projects/{project_id}/chapters", tags=["chapters"])
# 单个章节
chapter_router = APIRouter(prefix="/api/chapters", tags=["chapters"])


@project_router.get("", response_model=list[ChapterListItem])
def list_chapters(project_id: int, db: Session = Depends(get_db)) -> list[ChapterListItem]:
    try:
        return chapter_service.list_chapters(db, project_id)
    except ProjectNotFoundForChapterError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e


@project_router.post("", response_model=ChapterDetail, status_code=status.HTTP_201_CREATED)
def create_chapter(
    project_id: int, payload: ChapterCreate, db: Session = Depends(get_db)
) -> ChapterDetail:
    try:
        return chapter_service.create_chapter(db, project_id, payload)
    except ProjectNotFoundForChapterError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e


@project_router.post("/reorder", response_model=list[ChapterListItem])
def reorder_chapters(
    project_id: int, payload: ChapterReorder, db: Session = Depends(get_db)
) -> list[ChapterListItem]:
    try:
        return chapter_service.reorder_chapters(db, project_id, payload.chapter_ids)
    except ProjectNotFoundForChapterError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e
    except ReorderMismatchError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@chapter_router.get("/{chapter_id}", response_model=ChapterDetail)
def get_chapter(chapter_id: int, db: Session = Depends(get_db)) -> ChapterDetail:
    try:
        return chapter_service.get_chapter(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e


@chapter_router.patch("/{chapter_id}", response_model=ChapterDetail)
def update_chapter(
    chapter_id: int, payload: ChapterUpdate, db: Session = Depends(get_db)
) -> ChapterDetail:
    try:
        return chapter_service.update_chapter(db, chapter_id, payload)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e


@chapter_router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chapter(chapter_id: int, db: Session = Depends(get_db)) -> None:
    try:
        chapter_service.delete_chapter(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e


@chapter_router.put("/{chapter_id}/content", response_model=ChapterContentSaved)
def save_chapter_content(
    chapter_id: int, payload: ChapterContentUpdate, db: Session = Depends(get_db)
) -> ChapterContentSaved:
    try:
        c = chapter_service.save_content(db, chapter_id, payload.content)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    return ChapterContentSaved.model_validate(c)
