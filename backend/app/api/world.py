import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.world_entity import (
    WorldEntityCreate,
    WorldEntityExtractRequest,
    WorldEntityRead,
    WorldEntityUpdate,
)
from app.services import world_entity_service, world_extract_service
from app.services.world_entity_service import (
    ProjectNotFoundForWorldError,
    WorldEntityNameConflictError,
    WorldEntityNotFoundError,
)

# 工程下集合
project_router = APIRouter(prefix="/api/projects/{project_id}/world", tags=["world"])
# 单个
entity_router = APIRouter(prefix="/api/world", tags=["world"])


@project_router.get("", response_model=list[WorldEntityRead])
def list_entities(
    project_id: int, kind: str | None = None, db: Session = Depends(get_db)
) -> list[WorldEntityRead]:
    try:
        return world_entity_service.list_entities(db, project_id, kind)
    except ProjectNotFoundForWorldError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e


@project_router.post("", response_model=WorldEntityRead, status_code=status.HTTP_201_CREATED)
def create_entity(
    project_id: int, payload: WorldEntityCreate, db: Session = Depends(get_db)
) -> WorldEntityRead:
    try:
        return world_entity_service.create_entity(db, project_id, payload)
    except ProjectNotFoundForWorldError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e
    except WorldEntityNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"同类型下名字已存在: {e}"
        ) from e


@project_router.post("/extract")
async def extract_world(
    project_id: int,
    body: WorldEntityExtractRequest,
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    async def gen():
        try:
            async for evt in world_extract_service.extract_world_entities(
                db, project_id, body.kinds, body.mode
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


@entity_router.get("/{entity_id}", response_model=WorldEntityRead)
def get_entity(entity_id: int, db: Session = Depends(get_db)) -> WorldEntityRead:
    try:
        return world_entity_service.get_entity(db, entity_id)
    except WorldEntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在") from e


@entity_router.patch("/{entity_id}", response_model=WorldEntityRead)
def update_entity(
    entity_id: int, payload: WorldEntityUpdate, db: Session = Depends(get_db)
) -> WorldEntityRead:
    try:
        return world_entity_service.update_entity(db, entity_id, payload)
    except WorldEntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在") from e
    except WorldEntityNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"同类型下名字已存在: {e}"
        ) from e


@entity_router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entity(entity_id: int, db: Session = Depends(get_db)) -> None:
    try:
        world_entity_service.delete_entity(db, entity_id)
    except WorldEntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="条目不存在") from e
