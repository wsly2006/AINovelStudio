"""AI 接口:SSE 流式生成 / 续写 / 改写 + 非流式摘要。"""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.chapter import (
    BeatsAlignmentResponse,
    ChapterBeat,
    SuggestBeatsRequest,
    SuggestBeatsResponse,
)
from app.schemas.project import ProjectCreate
from app.services import (
    ai_task_manager,
    auto_writer_service,
    chapter_ai_service,
    chapter_beats_alignment_service,
    chapter_beats_service,
    project_ai_service,
    project_suggest_service,
)
from app.services.chapter_beats_alignment_service import BeatsAlignmentParseError
from app.services.chapter_beats_service import BeatsParseError
from app.services.chapter_service import ChapterNotFoundError
from app.services.project_service import ProjectNameConflictError

router = APIRouter(prefix="/api", tags=["ai"])


class GenerateBody(BaseModel):
    target_word_count: int = Field(default=3000, ge=200, le=20000)
    extra_instruction: str | None = Field(default=None, max_length=2000)
    character_ids: list[int] = Field(default_factory=list)
    world_entity_ids: list[int] = Field(default_factory=list)
    item_ids: list[int] = Field(default_factory=list)


class ContinueBody(BaseModel):
    cursor_text: str = Field(default="", max_length=200_000)
    extra_instruction: str | None = Field(default=None, max_length=2000)
    character_ids: list[int] = Field(default_factory=list)
    world_entity_ids: list[int] = Field(default_factory=list)
    item_ids: list[int] = Field(default_factory=list)


class RewriteBody(BaseModel):
    selection: str = Field(min_length=1, max_length=20_000)
    instruction: str = Field(min_length=1, max_length=2000)
    character_ids: list[int] = Field(default_factory=list)


class PreviewBody(BaseModel):
    """预览实际发送的 prompt(不调 LLM)。
    mode 决定走哪种组装路径,各模式按需用到下面的字段。"""

    mode: str = Field(pattern="^(generate|continue|rewrite)$")
    target_word_count: int = Field(default=4000, ge=200, le=20000)
    extra_instruction: str | None = Field(default=None, max_length=2000)
    cursor_text: str = Field(default="", max_length=200_000)
    selection: str = Field(default="", max_length=20_000)
    instruction: str = Field(default="", max_length=2000)
    character_ids: list[int] = Field(default_factory=list)
    world_entity_ids: list[int] = Field(default_factory=list)
    item_ids: list[int] = Field(default_factory=list)


@router.get("/ai/info")
def ai_info(db: Session = Depends(get_db)) -> dict:
    """前端用来判断 AI 是否可用 + 当前模型。"""
    from app.ai.runtime import resolve

    cfg = resolve(db)
    return {
        "configured": cfg.configured,
        "model": cfg.model,
        "provider": cfg.provider,
    }


def _sse_from_stream(stream: AsyncGenerator[str, None]) -> AsyncGenerator[dict, None]:
    """把文本增量包装成 SSE 事件。"""

    async def gen():
        try:
            async for delta in stream:
                yield {"event": "delta", "data": json.dumps({"text": delta}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except AINotConfiguredError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}
        except AIError as e:
            yield {"event": "error", "data": json.dumps({"message": str(e)}, ensure_ascii=False)}
        except ChapterNotFoundError:
            yield {
                "event": "error",
                "data": json.dumps({"message": "章节不存在"}, ensure_ascii=False),
            }

    return gen()


@router.post("/chapters/{chapter_id}/ai/generate")
async def ai_generate(
    chapter_id: int, body: GenerateBody, db: Session = Depends(get_db)
) -> EventSourceResponse:
    stream = chapter_ai_service.stream_generate(
        db,
        chapter_id,
        target_word_count=body.target_word_count,
        extra_instruction=body.extra_instruction,
        character_ids=body.character_ids,
        world_entity_ids=body.world_entity_ids,
        item_ids=body.item_ids,
    )
    return EventSourceResponse(_sse_from_stream(stream))


@router.post("/chapters/{chapter_id}/ai/continue")
async def ai_continue(
    chapter_id: int, body: ContinueBody, db: Session = Depends(get_db)
) -> EventSourceResponse:
    stream = chapter_ai_service.stream_continue(
        db,
        chapter_id,
        cursor_text=body.cursor_text,
        extra_instruction=body.extra_instruction,
        character_ids=body.character_ids,
        world_entity_ids=body.world_entity_ids,
        item_ids=body.item_ids,
    )
    return EventSourceResponse(_sse_from_stream(stream))


@router.post("/chapters/{chapter_id}/ai/rewrite")
async def ai_rewrite(
    chapter_id: int, body: RewriteBody, db: Session = Depends(get_db)
) -> EventSourceResponse:
    stream = chapter_ai_service.stream_rewrite(
        db,
        chapter_id,
        selection=body.selection,
        instruction=body.instruction,
        character_ids=body.character_ids,
    )
    return EventSourceResponse(_sse_from_stream(stream))


@router.post("/chapters/{chapter_id}/ai/preview-prompt")
def ai_preview_prompt(
    chapter_id: int,
    body: PreviewBody,
    db: Session = Depends(get_db),
) -> dict:
    """返回某种模式下实际会发送给 LLM 的 messages,用于前端调试 / 信任校验。
    不会调 LLM,不计 token,不写库。"""
    try:
        messages = chapter_ai_service.preview_messages(
            db,
            chapter_id,
            mode=body.mode,
            target_word_count=body.target_word_count,
            extra_instruction=body.extra_instruction,
            cursor_text=body.cursor_text,
            selection=body.selection,
            instruction=body.instruction,
            character_ids=body.character_ids,
            world_entity_ids=body.world_entity_ids,
            item_ids=body.item_ids,
        )
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return {"messages": messages}


@router.post("/chapters/{chapter_id}/ai/summarize")
async def ai_summarize(chapter_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        summary = await chapter_ai_service.summarize(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return {"summary": summary}


@router.post(
    "/chapters/{chapter_id}/ai/suggest-beats",
    response_model=SuggestBeatsResponse,
)
async def ai_suggest_beats(
    chapter_id: int,
    body: SuggestBeatsRequest | None = None,
    db: Session = Depends(get_db),
) -> SuggestBeatsResponse:
    """AI 草拟章节节拍。返回 ChapterBeat 列表,**不直接落库**——由前端编辑后再 PATCH。"""
    body = body or SuggestBeatsRequest()
    try:
        beats: list[ChapterBeat] = await chapter_beats_service.suggest_beats(
            db,
            chapter_id,
            target_word_count=body.target_word_count,
            extra_instruction=body.extra_instruction,
        )
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    except BeatsParseError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return SuggestBeatsResponse(beats=beats)


@router.post(
    "/chapters/{chapter_id}/ai/check-beats",
    response_model=BeatsAlignmentResponse,
)
async def ai_check_beats(
    chapter_id: int, db: Session = Depends(get_db)
) -> BeatsAlignmentResponse:
    """节拍-事件对账:把 chapter.beats 跟实际抽出的事件交给 AI 逐拍判断,
    结果落 chapter.beats_alignment。"""
    try:
        return await chapter_beats_alignment_service.align(db, chapter_id)
    except ChapterNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在") from e
    except BeatsAlignmentParseError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e


class AICreateProjectBody(BaseModel):
    project: ProjectCreate
    target_word_count: int = Field(default=80_000, ge=2_000, le=2_000_000)
    chapter_count: int = Field(default=20, ge=1, le=200)


@router.post("/projects/ai-create")
async def ai_create_project(body: AICreateProjectBody) -> dict:
    """启动后台 AI 大纲生成任务,立刻返回 task_id 与 project_id。

    生成本身在 asyncio task 里持续跑,前端通过 GET /ai-tasks/{id}/stream 订阅,
    断线重连时也能从历史事件回放,不会漏掉进度。
    """
    try:
        task_id, project_id = await project_ai_service.start_background(
            project_payload=body.project,
            target_word_count=body.target_word_count,
            chapter_count=body.chapter_count,
        )
    except ProjectNameConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"工程名已存在: {e}",
        ) from e
    return {"task_id": task_id, "project_id": project_id}


@router.get("/ai-tasks/{task_id}/stream")
async def ai_task_stream(task_id: str) -> EventSourceResponse:
    """订阅一个 AI 任务的事件流。先回放历史,再 tail 直到 done/error/cancelled。"""
    task = await ai_task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或已过期")

    async def gen():
        async for evt in ai_task_manager.stream(task_id):
            yield {
                "event": evt["event"],
                "data": json.dumps(evt["data"], ensure_ascii=False),
            }

    return EventSourceResponse(gen())


@router.delete("/ai-tasks/{task_id}")
async def ai_task_cancel(task_id: str) -> dict:
    task = await ai_task_manager.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在或已过期")
    cancelled = await ai_task_manager.cancel(task_id)
    return {"cancelled": cancelled, "status": task.status}


class SuggestBody(BaseModel):
    """AI 起书名 / 生简介共用入参,所有字段均可选——
    用户在新建工程对话框里填到哪算哪,服务端有什么用什么。"""

    name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    channel: str | None = Field(default=None, max_length=32)
    genre: str | None = Field(default=None, max_length=32)
    tags: list[str] = Field(default_factory=list)


@router.post("/projects/ai-suggest/title")
async def ai_suggest_title(body: SuggestBody, db: Session = Depends(get_db)) -> dict:
    try:
        titles = await project_suggest_service.suggest_titles(
            db,
            name=body.name,
            description=body.description,
            channel=body.channel,
            genre=body.genre,
            tags=body.tags,
        )
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return {"titles": titles}


@router.post("/projects/ai-suggest/description")
async def ai_suggest_description(body: SuggestBody, db: Session = Depends(get_db)) -> dict:
    try:
        description = await project_suggest_service.suggest_description(
            db,
            name=body.name,
            description=body.description,
            channel=body.channel,
            genre=body.genre,
            tags=body.tags,
        )
    except AINotConfiguredError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except AIError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e
    return {"description": description}


class AutoWriteBody(BaseModel):
    """连续自动生成的入参。"""

    start_chapter_id: int
    count: int = Field(default=1, ge=1, le=50)
    target_word_count: int = Field(default=4000, ge=200, le=20000)
    extra_instruction: str | None = Field(default=None, max_length=2000)
    character_ids: list[int] = Field(default_factory=list)
    world_entity_ids: list[int] = Field(default_factory=list)
    item_ids: list[int] = Field(default_factory=list)
    # strict 严格停 / auto_fix 自纠继续 / all_through 全推到底
    mode: str = Field(default="auto_fix", pattern="^(strict|auto_fix|all_through)$")
    score_threshold: int = Field(default=70, ge=0, le=100)


@router.post("/projects/{project_id}/ai/auto-write")
async def ai_auto_write(project_id: int, body: AutoWriteBody) -> dict:
    """启动自动连写后台任务,立刻返回 task_id + 待处理章节 id 列表。"""
    try:
        task_id, chapter_ids = await auto_writer_service.start_background(
            project_id=project_id,
            start_chapter_id=body.start_chapter_id,
            count=body.count,
            target_word_count=body.target_word_count,
            extra_instruction=body.extra_instruction,
            character_ids=body.character_ids,
            world_entity_ids=body.world_entity_ids,
            item_ids=body.item_ids,
            mode=body.mode,
            score_threshold=body.score_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return {"task_id": task_id, "chapter_ids": chapter_ids}
