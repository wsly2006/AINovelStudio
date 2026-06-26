import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.character import (
    CharacterCreate,
    CharacterExtractRequest,
    CharacterRead,
    CharacterUpdate,
)
from app.services import character_extract_service, character_service
from app.services.character_service import (
    CharacterNameConflictError,
    CharacterNotFoundError,
    ProjectNotFoundForCharacterError,
)

# 工程下集合
project_router = APIRouter(prefix="/api/projects/{project_id}/characters", tags=["characters"])
# 单个
character_router = APIRouter(prefix="/api/characters", tags=["characters"])


@project_router.get("", response_model=list[CharacterRead])
def list_characters(project_id: int, db: Session = Depends(get_db)) -> list[CharacterRead]:
    try:
        return character_service.list_characters(db, project_id)
    except ProjectNotFoundForCharacterError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e


@project_router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
def create_character(
    project_id: int, payload: CharacterCreate, db: Session = Depends(get_db)
) -> CharacterRead:
    try:
        return character_service.create_character(db, project_id, payload)
    except ProjectNotFoundForCharacterError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e
    except CharacterNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"人物名已存在: {e}"
        ) from e


@project_router.post("/extract")
async def extract_characters(
    project_id: int,
    body: CharacterExtractRequest,
) -> EventSourceResponse:
    # SSE 期间逐章 AI 抽取,session 在 generator 内自己起,不占路由依赖链上的连接。
    async def gen():
        from app.database import SessionLocal

        with SessionLocal() as db:
            try:
                async for evt in character_extract_service.extract_characters(
                    db, project_id, body.chapter_ids, body.mode
                ):
                    yield {
                        "event": evt["event"],
                        "data": json.dumps(evt["data"], ensure_ascii=False),
                    }
            except AINotConfiguredError as e:
                yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}
            except AIError as e:
                yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(gen())


@character_router.get("/{character_id}", response_model=CharacterRead)
def get_character(character_id: int, db: Session = Depends(get_db)) -> CharacterRead:
    try:
        return character_service.get_character(db, character_id)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人物不存在") from e


@character_router.patch("/{character_id}", response_model=CharacterRead)
def update_character(
    character_id: int, payload: CharacterUpdate, db: Session = Depends(get_db)
) -> CharacterRead:
    try:
        return character_service.update_character(db, character_id, payload)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人物不存在") from e
    except CharacterNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"人物名已存在: {e}"
        ) from e


@character_router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(character_id: int, db: Session = Depends(get_db)) -> None:
    try:
        character_service.delete_character(db, character_id)
    except CharacterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="人物不存在") from e
