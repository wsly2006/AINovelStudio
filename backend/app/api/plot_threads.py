"""主线(PlotThread)API:跨章节情节线管理 + AI 草拟主线。"""

import json
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.models.project import Project
from app.schemas.plot_thread import (
    PlotThreadCreate,
    PlotThreadRead,
    PlotThreadUpdate,
)
from app.services import plot_thread_service, prompt_service
from app.services.plot_thread_service import (
    InvalidPlotThreadError,
    PlotThreadNotFoundError,
)

project_router = APIRouter(
    prefix="/api/projects/{project_id}/threads", tags=["plot-threads"]
)
thread_router = APIRouter(prefix="/api/threads", tags=["plot-threads"])


@project_router.get("", response_model=list[PlotThreadRead])
def list_threads(project_id: int, db: Session = Depends(get_db)) -> list[PlotThreadRead]:
    try:
        return plot_thread_service.list_threads(db, project_id)
    except InvalidPlotThreadError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@project_router.post("", response_model=PlotThreadRead, status_code=status.HTTP_201_CREATED)
def create_thread(
    project_id: int, payload: PlotThreadCreate, db: Session = Depends(get_db)
) -> PlotThreadRead:
    try:
        return plot_thread_service.create_thread(db, project_id, payload)
    except InvalidPlotThreadError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@project_router.post("/suggest", response_model=list[PlotThreadRead])
async def suggest_threads(
    project_id: int, db: Session = Depends(get_db)
) -> list[PlotThreadRead]:
    """AI 基于 description / synopsis / genre 草拟 3-5 条主线。直接落库,返回新建的列表。"""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在")

    if not (project.synopsis or project.description):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先填写工程总纲或简介,AI 才能据此草拟主线",
        )

    meta_lines = [f"书名:《{project.name}》"]
    if project.genre:
        meta_lines.append(f"题材:{project.genre}")
    if project.tags:
        meta_lines.append(f"标签:{ '、'.join(project.tags) }")
    if project.description:
        meta_lines.append(f"简介:{project.description}")
    if project.synopsis:
        meta_lines.append(f"总纲:\n{project.synopsis}")

    messages = prompt_service.render(
        db,
        "project.suggest_threads",
        {"project_meta": "\n".join(meta_lines)},
    )

    try:
        raw = await ai_client.complete(
            db, messages, scene="project.suggest_threads", max_tokens=2000, project_id=project_id
        )
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    parsed = _parse_threads_json(raw)
    threads = parsed.get("threads") or []
    if not threads:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 没有返回任何主线,可能是模型输出格式异常,请重试",
        )

    created: list[PlotThreadRead] = []
    for idx, item in enumerate(threads, start=1):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        importance = item.get("importance")
        try:
            importance = max(1, min(5, int(importance)))
        except (TypeError, ValueError):
            importance = 3
        payload = PlotThreadCreate(
            title=title[:120],
            description=(item.get("description") or "").strip() or None,
            planned_arc=(item.get("planned_arc") or "").strip() or None,
            status="planning",
            importance=importance,
            order_index=idx,
        )
        try:
            created.append(plot_thread_service.create_thread(db, project_id, payload))
        except InvalidPlotThreadError:
            continue
    return created


def _parse_threads_json(text: str) -> dict:
    """容忍模型把 JSON 包在 ```json ... ``` 里的常见情况。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 输出无法解析为 JSON",
        )
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 输出 JSON 解析失败:{e}",
        ) from e


@thread_router.get("/{thread_id}", response_model=PlotThreadRead)
def get_thread(thread_id: int, db: Session = Depends(get_db)) -> PlotThreadRead:
    try:
        t = plot_thread_service.get_thread(db, thread_id)
    except PlotThreadNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主线不存在") from e
    return PlotThreadRead.model_validate(t)


@thread_router.patch("/{thread_id}", response_model=PlotThreadRead)
def update_thread(
    thread_id: int, payload: PlotThreadUpdate, db: Session = Depends(get_db)
) -> PlotThreadRead:
    try:
        return plot_thread_service.update_thread(db, thread_id, payload)
    except PlotThreadNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主线不存在") from e


@thread_router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: int, db: Session = Depends(get_db)) -> None:
    try:
        plot_thread_service.delete_thread(db, thread_id)
    except PlotThreadNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主线不存在") from e
