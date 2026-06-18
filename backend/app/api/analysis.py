import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.plot_event import PlotEventCreate, PlotEventRead, PlotEventUpdate
from app.schemas.relation import RelationCreate, RelationRead, RelationUpdate
from app.services import analysis_service, plot_service, relation_service
from app.services.plot_service import InvalidPlotEventError, PlotEventNotFoundError
from app.services.relation_service import InvalidRelationError, RelationNotFoundError


class _ExtractRequest(BaseModel):
    """关系 / 情节抽取的可选 body:留空 = 扫全工程,给定章节 = 只扫这些章节。"""

    chapter_ids: list[int] | None = None

# ============ Relations ============

relation_project_router = APIRouter(
    prefix="/api/projects/{project_id}/relations", tags=["relations"]
)
relation_router = APIRouter(prefix="/api/relations", tags=["relations"])


@relation_project_router.get("", response_model=list[RelationRead])
def list_relations(project_id: int, db: Session = Depends(get_db)) -> list[RelationRead]:
    return relation_service.list_relations(db, project_id)


@relation_project_router.post("", response_model=RelationRead, status_code=status.HTTP_201_CREATED)
def create_relation(
    project_id: int, payload: RelationCreate, db: Session = Depends(get_db)
) -> RelationRead:
    try:
        return relation_service.create_relation(db, project_id, payload)
    except InvalidRelationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@relation_project_router.post("/extract")
async def extract_relations(
    project_id: int,
    body: _ExtractRequest | None = None,
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    chapter_ids = body.chapter_ids if body else None

    async def gen():
        try:
            async for evt in analysis_service.extract_relations(db, project_id, chapter_ids):
                yield {
                    "event": evt["event"],
                    "data": json.dumps(evt["data"], ensure_ascii=False),
                }
        except AINotConfiguredError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}
        except AIError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(gen())


@relation_router.patch("/{relation_id}", response_model=RelationRead)
def update_relation(
    relation_id: int, payload: RelationUpdate, db: Session = Depends(get_db)
) -> RelationRead:
    try:
        return relation_service.update_relation(db, relation_id, payload)
    except RelationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关系不存在") from e


@relation_router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation(relation_id: int, db: Session = Depends(get_db)) -> None:
    try:
        relation_service.delete_relation(db, relation_id)
    except RelationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关系不存在") from e


# ============ Plot ============

plot_project_router = APIRouter(prefix="/api/projects/{project_id}/plot", tags=["plot"])
plot_router = APIRouter(prefix="/api/plot/events", tags=["plot"])


@plot_project_router.get("/events", response_model=list[PlotEventRead])
def list_events(project_id: int, db: Session = Depends(get_db)) -> list[PlotEventRead]:
    return plot_service.list_events(db, project_id)


@plot_project_router.post("/events", response_model=PlotEventRead, status_code=status.HTTP_201_CREATED)
def create_event(
    project_id: int, payload: PlotEventCreate, db: Session = Depends(get_db)
) -> PlotEventRead:
    try:
        return plot_service.create_event(db, project_id, payload)
    except InvalidPlotEventError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@plot_project_router.post("/extract")
async def extract_plot(
    project_id: int,
    body: _ExtractRequest | None = None,
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    chapter_ids = body.chapter_ids if body else None

    async def gen():
        try:
            async for evt in analysis_service.extract_plot(db, project_id, chapter_ids):
                yield {
                    "event": evt["event"],
                    "data": json.dumps(evt["data"], ensure_ascii=False),
                }
        except AINotConfiguredError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}
        except AIError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}

    return EventSourceResponse(gen())


@plot_project_router.post("/check")
async def check_consistency(project_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return await analysis_service.check_consistency(db, project_id)
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


# 单章非流式抽取:AI 生成正文落地后调用,把这一章的 plot_events 全删重抽,
# 避免用户漏点「索引本章」导致后续生成看不到刚发生的事(沉默失败)。
single_chapter_plot_router = APIRouter(prefix="/api/chapters", tags=["plot"])


@single_chapter_plot_router.post("/{chapter_id}/auto-index")
async def auto_index_chapter(
    chapter_id: int, db: Session = Depends(get_db)
) -> dict:
    from app.models.chapter import Chapter

    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

    extracted = 0
    skipped = False
    last_error: str | None = None
    try:
        async for evt in analysis_service.extract_plot(
            db, chapter.project_id, chapter_ids=[chapter_id]
        ):
            kind = evt.get("event")
            data = evt.get("data") or {}
            if kind == "progress" and data.get("skipped"):
                skipped = True
            elif kind == "done":
                extracted = int(data.get("extracted") or 0)
            elif kind == "error":
                last_error = str(data.get("message") or "")
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    if last_error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=last_error)
    return {"extracted": extracted, "skipped": skipped}


@plot_router.patch("/{event_id}", response_model=PlotEventRead)
def update_event(
    event_id: int, payload: PlotEventUpdate, db: Session = Depends(get_db)
) -> PlotEventRead:
    try:
        return plot_service.update_event(db, event_id, payload)
    except PlotEventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="事件不存在") from e


@plot_router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> None:
    try:
        plot_service.delete_event(db, event_id)
    except PlotEventNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="事件不存在") from e
