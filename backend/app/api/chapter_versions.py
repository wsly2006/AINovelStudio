from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chapter import ChapterDetail
from app.schemas.chapter_version import (
    ChapterVersionCreate,
    ChapterVersionDetail,
    ChapterVersionListItem,
)
from app.services import chapter_version_service
from app.services.chapter_service import ChapterNotFoundError
from app.services.chapter_version_service import ChapterVersionNotFoundError

router = APIRouter(prefix="/api/chapters/{chapter_id}/versions", tags=["chapter-versions"])


@router.get("", response_model=list[ChapterVersionListItem])
def list_versions(
    chapter_id: int, db: Session = Depends(get_db)
) -> list[ChapterVersionListItem]:
    try:
        return chapter_version_service.list_versions(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e


@router.post(
    "",
    response_model=ChapterVersionListItem,
    status_code=status.HTTP_201_CREATED,
)
def create_manual_version(
    chapter_id: int,
    payload: ChapterVersionCreate,
    db: Session = Depends(get_db),
) -> ChapterVersionListItem:
    """手动快照当前章节内容。"""
    try:
        v = chapter_version_service.snapshot(
            db, chapter_id, reason="manual", label=payload.label
        )
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    item = ChapterVersionListItem.model_validate(v)
    # 列表用的预览字段:这里手动填,跟 list_versions 保持一致
    item.preview = chapter_version_service._build_preview(v.content)
    return item


@router.post(
    "/ai-snapshot",
    response_model=ChapterVersionListItem,
    status_code=status.HTTP_201_CREATED,
)
def create_ai_snapshot(
    chapter_id: int, db: Session = Depends(get_db)
) -> ChapterVersionListItem:
    """AI 覆盖前的自动快照。前端在 replace/append/insert 之前调用一次。"""
    try:
        v = chapter_version_service.snapshot(
            db, chapter_id, reason="ai_overwrite", label=None
        )
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    item = ChapterVersionListItem.model_validate(v)
    item.preview = chapter_version_service._build_preview(v.content)
    return item


@router.get("/{version_id}", response_model=ChapterVersionDetail)
def get_version(
    chapter_id: int, version_id: int, db: Session = Depends(get_db)
) -> ChapterVersionDetail:
    try:
        v = chapter_version_service.get_version(db, version_id)
    except ChapterVersionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本不存在") from e
    if v.chapter_id != chapter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本与章节不匹配")
    return v


@router.post("/{version_id}/restore", response_model=ChapterDetail)
def restore_version(
    chapter_id: int, version_id: int, db: Session = Depends(get_db)
) -> ChapterDetail:
    try:
        c = chapter_version_service.restore(db, version_id)
    except ChapterVersionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本不存在") from e
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    if c.id != chapter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本与章节不匹配")
    return ChapterDetail.model_validate(c)


@router.delete("/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_version(
    chapter_id: int, version_id: int, db: Session = Depends(get_db)
) -> None:
    # 必须先校验所属章节,再删除,否则跨章节误删请求会先把行干掉再报 404
    try:
        v = chapter_version_service.get_version(db, version_id)
    except ChapterVersionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本不存在") from e
    if v.chapter_id != chapter_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="版本与章节不匹配")
    chapter_version_service.delete_version(db, version_id)
