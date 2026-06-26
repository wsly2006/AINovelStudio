import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate
from app.services import item_extract_service, item_service
from app.services.item_service import (
    ItemNameConflictError,
    ItemNotFoundError,
    ProjectNotFoundForItemError,
)


class ItemExtractRequest(BaseModel):
    mode: str = Field(default="merge", pattern="^(merge|replace)$")
    # 限定要扫的章节;None 表示全工程扫描
    chapter_ids: list[int] | None = None


# 工程下集合
project_router = APIRouter(prefix="/api/projects/{project_id}/items", tags=["items"])
# 单个
item_router = APIRouter(prefix="/api/items", tags=["items"])


@project_router.get("", response_model=list[ItemRead])
def list_items(project_id: int, db: Session = Depends(get_db)) -> list[ItemRead]:
    try:
        return item_service.list_items(db, project_id)
    except ProjectNotFoundForItemError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e


@project_router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    project_id: int, payload: ItemCreate, db: Session = Depends(get_db)
) -> ItemRead:
    try:
        return item_service.create_item(db, project_id, payload)
    except ProjectNotFoundForItemError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e
    except ItemNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"名字已存在: {e}"
        ) from e


@project_router.post("/extract")
async def extract_items(
    project_id: int,
    body: ItemExtractRequest,
) -> EventSourceResponse:
    # SSE 期间逐章 AI 抽取,session 在 generator 内自己起,不占路由依赖链上的连接。
    async def gen():
        from app.database import SessionLocal

        with SessionLocal() as db:
            try:
                async for evt in item_extract_service.extract_items(
                    db, project_id, body.mode, body.chapter_ids
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


@item_router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)) -> ItemRead:
    try:
        return item_service.get_item(db, item_id)
    except ItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在") from e


@item_router.patch("/{item_id}", response_model=ItemRead)
def update_item(
    item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)
) -> ItemRead:
    try:
        return item_service.update_item(db, item_id, payload)
    except ItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在") from e
    except ItemNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"名字已存在: {e}"
        ) from e


@item_router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: Session = Depends(get_db)) -> None:
    try:
        item_service.delete_item(db, item_id)
    except ItemNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在") from e
