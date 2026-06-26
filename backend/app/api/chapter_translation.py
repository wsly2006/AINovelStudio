"""章节翻译 API:SSE 流式翻译 + 落库。"""

import json

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import SessionLocal
from app.services import chapter_translation_service

router = APIRouter(prefix="/api/chapters", tags=["chapter-translation"])


class TranslateRequest(BaseModel):
    target_lang: str = Field(default="en-US", min_length=2, max_length=8)
    extra_instruction: str | None = Field(default=None, max_length=2000)


@router.post("/{chapter_id}/translate")
async def translate_chapter(
    chapter_id: int,
    body: TranslateRequest,
) -> EventSourceResponse:
    # 不走 Depends(get_db):SSE 期间 LLM 可能跑几十秒到几分钟,
    # 让生成器自己起一条独立 session,避免阻塞路由依赖链上的其他请求。
    async def gen():
        with SessionLocal() as db:
            try:
                async for evt in chapter_translation_service.translate_and_persist(
                    db,
                    chapter_id,
                    body.target_lang,
                    extra_instruction=body.extra_instruction,
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
