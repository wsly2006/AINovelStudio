from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.client import AINotConfiguredError, AIError
from app.database import get_db
from app.schemas.chapter_score import ChapterScoreItem
from app.services import chapter_score_service
from app.services.chapter_score_service import (
    ChapterScoreNotFoundError,
    ChapterScoreParseError,
)
from app.services.chapter_service import ChapterNotFoundError

router = APIRouter(prefix="/api/chapters/{chapter_id}/scores", tags=["chapter-scores"])


@router.get("", response_model=list[ChapterScoreItem])
def list_scores(
    chapter_id: int, db: Session = Depends(get_db)
) -> list[ChapterScoreItem]:
    try:
        return chapter_score_service.list_scores(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e


@router.post(
    "",
    response_model=ChapterScoreItem,
    status_code=status.HTTP_201_CREATED,
)
async def create_score(
    chapter_id: int, db: Session = Depends(get_db)
) -> ChapterScoreItem:
    try:
        return await chapter_score_service.score_chapter(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    except AINotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI 未配置:请先在「模型设置」里填好 API Key",
        ) from e
    except ChapterScoreParseError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 输出解析失败,请重试:{e}",
        ) from e
    except AIError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 调用失败:{e}",
        ) from e


@router.delete("/{score_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_score(
    chapter_id: int, score_id: int, db: Session = Depends(get_db)
) -> None:
    # 先校验所属再删,跟版本删除同样的处理
    try:
        rows = chapter_score_service.list_scores(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    if not any(r.id == score_id for r in rows):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评分不存在或与章节不匹配")
    try:
        chapter_score_service.delete_score(db, score_id)
    except ChapterScoreNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评分不存在") from e
