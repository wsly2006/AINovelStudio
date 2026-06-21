"""大纲模式 API。

- POST /api/projects/{id}/outline/batch-suggest:让 AI 批量草拟连续 N 章大纲(不落库)
- POST /api/projects/{id}/outline/batch-create:把草稿数组追加到工程末尾(status='outlined')
- POST /api/chapters/{id}/outline-alignment:章节正文 vs 大纲对账(供内容 tab 调用)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.chapter import (
    OutlineAlignmentResult,
    OutlineBatchCreateRequest,
    OutlineBatchCreateResponse,
    OutlineBatchSuggestRequest,
    OutlineBatchSuggestResponse,
)
from app.services import outline_service
from app.services.chapter_service import ChapterNotFoundError

# 工程层:批量草拟 + 批量落库
project_router = APIRouter(prefix="/api/projects/{project_id}/outline", tags=["outline"])
# 章节层:对账
chapter_router = APIRouter(prefix="/api/chapters", tags=["outline"])


@project_router.post("/batch-suggest", response_model=OutlineBatchSuggestResponse)
async def batch_suggest_outlines(
    project_id: int,
    payload: OutlineBatchSuggestRequest,
    db: Session = Depends(get_db),
) -> OutlineBatchSuggestResponse:
    try:
        drafts = await outline_service.batch_suggest(
            db,
            project_id,
            count=payload.count,
            start_order_index=payload.start_order_index,
            extra_instruction=payload.extra_instruction,
            target_word_count=payload.target_word_count,
        )
    except outline_service.ProjectNotFoundForOutlineError as e:
        raise HTTPException(status_code=404, detail="工程不存在") from e
    except AINotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (AIError, outline_service.OutlineParseError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return OutlineBatchSuggestResponse(drafts=drafts)


@project_router.post(
    "/batch-create",
    response_model=OutlineBatchCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def batch_create_outlines(
    project_id: int,
    payload: OutlineBatchCreateRequest,
    db: Session = Depends(get_db),
) -> OutlineBatchCreateResponse:
    try:
        chapters = outline_service.batch_create(db, project_id, payload.drafts)
    except outline_service.ProjectNotFoundForOutlineError as e:
        raise HTTPException(status_code=404, detail="工程不存在") from e
    return OutlineBatchCreateResponse(chapters=chapters)


@chapter_router.post(
    "/{chapter_id}/outline-alignment",
    response_model=OutlineAlignmentResult,
)
async def check_outline_alignment(
    chapter_id: int,
    db: Session = Depends(get_db),
) -> OutlineAlignmentResult:
    try:
        return await outline_service.check_outline_alignment(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=404, detail="章节不存在") from e
    except AINotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (AIError, outline_service.OutlineParseError) as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
