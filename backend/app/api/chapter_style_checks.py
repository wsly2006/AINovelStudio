from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.chapter_style_check import ChapterStyleCheckItem
from app.services import chapter_style_check_service
from app.services.chapter_service import ChapterNotFoundError
from app.services.chapter_style_check_service import (
    ChapterStyleCheckNotFoundError,
    ChapterStyleCheckParseError,
)

router = APIRouter(
    prefix="/api/chapters/{chapter_id}/style-checks",
    tags=["chapter-style-checks"],
)


@router.get("", response_model=list[ChapterStyleCheckItem])
def list_checks(
    chapter_id: int, db: Session = Depends(get_db)
) -> list[ChapterStyleCheckItem]:
    try:
        return chapter_style_check_service.list_checks(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e


@router.post(
    "",
    response_model=ChapterStyleCheckItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_check(
    chapter_id: int, db: Session = Depends(get_db)
) -> ChapterStyleCheckItem:
    try:
        return await chapter_style_check_service.style_check_chapter(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    except AINotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 未配置:请先在「模型设置」里填好 API Key",
        ) from e
    except ChapterStyleCheckParseError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 输出解析失败,请重试:{e}",
        ) from e
    except AIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 调用失败:{e}",
        ) from e


@router.delete("/{check_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_check(
    chapter_id: int, check_id: int, db: Session = Depends(get_db)
) -> None:
    # 先校验所属再删,跟评分 / 版本删除同款保护
    try:
        rows = chapter_style_check_service.list_checks(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    if not any(r.id == check_id for r in rows):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在或与章节不匹配",
        )
    try:
        chapter_style_check_service.delete_check(db, check_id)
    except ChapterStyleCheckNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在") from e
