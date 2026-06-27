from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.author_voice_profile import (
    AuthorVoiceProfileRead,
    AuthorVoiceProfileUpsert,
)
from app.services import author_voice_service
from app.services.author_voice_service import (
    ProjectNotFoundError,
    VoiceProfileNotFoundError,
)

router = APIRouter(prefix="/api/projects", tags=["author-voice"])


@router.get("/{project_id}/voice-profile", response_model=AuthorVoiceProfileRead | None)
def get_voice_profile(
    project_id: int, db: Session = Depends(get_db)
) -> AuthorVoiceProfileRead | None:
    # 没建过 profile 直接返回 null,不报 404 — 前端只需要 if (resp) 判断
    try:
        return author_voice_service.get_profile(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail="项目不存在") from e


@router.put("/{project_id}/voice-profile", response_model=AuthorVoiceProfileRead)
def upsert_voice_profile(
    project_id: int,
    payload: AuthorVoiceProfileUpsert,
    db: Session = Depends(get_db),
) -> AuthorVoiceProfileRead:
    try:
        return author_voice_service.upsert_profile(db, project_id, payload)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail="项目不存在") from e


@router.delete("/{project_id}/voice-profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice_profile(project_id: int, db: Session = Depends(get_db)) -> None:
    try:
        author_voice_service.delete_profile(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail="项目不存在") from e
    except VoiceProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail="尚未创建 voice profile") from e
