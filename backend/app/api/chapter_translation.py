"""章节翻译 API:SSE 流式翻译 + 落库。"""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.services import chapter_translation_service

router = APIRouter(prefix="/api/chapters", tags=["chapter-translation"])


class TranslateRequest(BaseModel):
    target_lang: str = Field(default="en-US", min_length=2, max_length=8)
    extra_instruction: str | None = Field(default=None, max_length=2000)


@router.post("/{chapter_id}/translate")
async def translate_chapter(
    chapter_id: int,
    body: TranslateRequest,
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    async def gen():
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
