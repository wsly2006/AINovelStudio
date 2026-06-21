from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.platform_profile import (
    PlatformProfileCreate,
    PlatformProfileRead,
    PlatformProfileUpdate,
)
from app.services import platform_profile_service
from app.services.platform_profile_service import (
    PlatformProfileCodeConflictError,
    PlatformProfileNotFoundError,
    PlatformProfilePresetReadonlyError,
)

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("", response_model=list[PlatformProfileRead])
def list_platforms(db: Session = Depends(get_db)) -> list[PlatformProfileRead]:
    return platform_profile_service.list_profiles(db)


@router.get("/{profile_id}", response_model=PlatformProfileRead)
def get_platform(profile_id: int, db: Session = Depends(get_db)) -> PlatformProfileRead:
    try:
        return platform_profile_service.get_profile(db, profile_id)
    except PlatformProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail="平台 profile 不存在") from e


@router.post("", response_model=PlatformProfileRead, status_code=status.HTTP_201_CREATED)
def create_platform(
    payload: PlatformProfileCreate, db: Session = Depends(get_db)
) -> PlatformProfileRead:
    try:
        return platform_profile_service.create_profile(db, payload)
    except PlatformProfileCodeConflictError as e:
        raise HTTPException(status_code=400, detail=f"code 已存在: {e}") from e


@router.patch("/{profile_id}", response_model=PlatformProfileRead)
def update_platform(
    profile_id: int, payload: PlatformProfileUpdate, db: Session = Depends(get_db)
) -> PlatformProfileRead:
    try:
        return platform_profile_service.update_profile(db, profile_id, payload)
    except PlatformProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail="平台 profile 不存在") from e


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_platform(profile_id: int, db: Session = Depends(get_db)) -> None:
    try:
        platform_profile_service.delete_profile(db, profile_id)
    except PlatformProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail="平台 profile 不存在") from e
    except PlatformProfilePresetReadonlyError as e:
        raise HTTPException(status_code=400, detail=f"预制平台不可删除: {e}") from e
