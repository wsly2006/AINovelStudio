from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai,
    analysis,
    chapters,
    characters,
    export,
    health,
    items,
    ladders,
    projects,
    prompts,
    state_events,
    stats,
    tasks,
    world,
)
from app.api import (
    settings as settings_api,
)
from app.config import settings
from app.database import init_db
from app.logging_config import setup_logging
from app.services import ai_task_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    # 启动时配日志 + 建表
    setup_logging()
    init_db()
    # 后台跑 AI 任务的清理协程,把已经结束很久的 task 记录从内存中移除
    reaper = asyncio.create_task(ai_task_manager.reaper_loop())
    try:
        yield
    finally:
        reaper.cancel()
        try:
            await reaper
        except (asyncio.CancelledError, Exception):
            pass


app = FastAPI(
    title="AI Novel Writer",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(chapters.project_router)
app.include_router(chapters.chapter_router)
app.include_router(characters.project_router)
app.include_router(characters.character_router)
app.include_router(analysis.relation_project_router)
app.include_router(analysis.relation_router)
app.include_router(analysis.plot_project_router)
app.include_router(analysis.plot_router)
app.include_router(world.project_router)
app.include_router(world.entity_router)
app.include_router(items.project_router)
app.include_router(items.item_router)
app.include_router(ladders.project_router)
app.include_router(ladders.ladder_router)
app.include_router(state_events.project_router)
app.include_router(state_events.character_router)
app.include_router(state_events.event_router)
app.include_router(state_events.snapshot_router)
app.include_router(tasks.project_router)
app.include_router(tasks.task_router)
app.include_router(ai.router)
app.include_router(settings_api.router)
app.include_router(prompts.router)
app.include_router(export.router)
app.include_router(stats.router)
