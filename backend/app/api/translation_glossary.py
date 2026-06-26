import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.translation_glossary import (
    GlossaryCreate,
    GlossaryExtractRequest,
    GlossaryRead,
    GlossarySeedRequest,
    GlossarySeedResult,
    GlossaryUpdate,
)
from app.services import glossary_extract_service
from app.services import translation_glossary_service as svc
from app.services.translation_glossary_service import (
    GlossaryConflictError,
    GlossaryNotFoundError,
    ProjectNotFoundForGlossaryError,
)

# 工程下集合
project_router = APIRouter(
    prefix="/api/projects/{project_id}/glossary", tags=["glossary"]
)
# 单条
entry_router = APIRouter(prefix="/api/glossary", tags=["glossary"])


@project_router.get("", response_model=list[GlossaryRead])
def list_entries(
    project_id: int,
    target_lang: str | None = Query(default=None),
    entry_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[GlossaryRead]:
    try:
        return svc.list_entries(
            db, project_id, target_lang=target_lang, entry_type=entry_type
        )
    except ProjectNotFoundForGlossaryError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在"
        ) from e


@project_router.post(
    "", response_model=GlossaryRead, status_code=status.HTTP_201_CREATED
)
def create_entry(
    project_id: int,
    payload: GlossaryCreate,
    db: Session = Depends(get_db),
) -> GlossaryRead:
    try:
        return svc.create_entry(db, project_id, payload)
    except ProjectNotFoundForGlossaryError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在"
        ) from e
    except GlossaryConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from e


@project_router.post(
    "/seed",
    response_model=GlossarySeedResult,
    status_code=status.HTTP_201_CREATED,
)
def seed_entries(
    project_id: int,
    payload: GlossarySeedRequest,
    db: Session = Depends(get_db),
) -> GlossarySeedResult:
    try:
        return svc.bulk_seed_from_project(
            db,
            project_id,
            target_lang=payload.target_lang,
            overwrite=payload.overwrite,
        )
    except ProjectNotFoundForGlossaryError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在"
        ) from e


@project_router.post("/extract")
async def extract_glossary(
    project_id: int,
    body: GlossaryExtractRequest,
) -> EventSourceResponse:
    # SSE 期间逐章扫 + AI 候选抽取可能跑几十秒,session 在 generator 内自己起,
    # 不占路由依赖链上的连接。
    async def gen():
        from app.database import SessionLocal

        with SessionLocal() as db:
            try:
                async for evt in glossary_extract_service.extract_glossary(
                    db,
                    project_id,
                    target_lang=body.target_lang,
                    chapter_ids=body.chapter_ids,
                ):
                    yield {
                        "event": evt["event"],
                        "data": json.dumps(evt["data"], ensure_ascii=False),
                    }
            except AINotConfiguredError as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": str(e)}, ensure_ascii=False),
                }
            except AIError as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": str(e)}, ensure_ascii=False),
                }

    return EventSourceResponse(gen())


@entry_router.get("/{entry_id}", response_model=GlossaryRead)
def get_entry(entry_id: int, db: Session = Depends(get_db)) -> GlossaryRead:
    try:
        return svc.get_entry(db, entry_id)
    except GlossaryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="术语不存在"
        ) from e


@entry_router.patch("/{entry_id}", response_model=GlossaryRead)
def update_entry(
    entry_id: int,
    payload: GlossaryUpdate,
    db: Session = Depends(get_db),
) -> GlossaryRead:
    try:
        return svc.update_entry(db, entry_id, payload)
    except GlossaryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="术语不存在"
        ) from e
    except GlossaryConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from e


@entry_router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, db: Session = Depends(get_db)) -> None:
    try:
        svc.delete_entry(db, entry_id)
    except GlossaryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="术语不存在"
        ) from e
