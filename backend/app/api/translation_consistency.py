"""翻译一致性报告 API。"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import translation_consistency_service as svc
from app.services.translation_consistency_service import (
    ProjectNotFoundForConsistencyError,
)

router = APIRouter(prefix="/api/projects", tags=["translation-consistency"])


@router.get("/{project_id}/translation-consistency")
def check_consistency(
    project_id: int,
    target_lang: str = Query(default="en-US", min_length=2, max_length=8),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return svc.check_project(db, project_id, target_lang=target_lang)
    except ProjectNotFoundForConsistencyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在"
        ) from e
