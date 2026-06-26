"""AI 助手:会话 / 消息 / 流式发送接口。"""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.ai.client import AIError, AINotConfiguredError
from app.database import get_db
from app.schemas.ai_assistant import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
    PreviewMessageBody,
    SendMessageBody,
)
from app.services import ai_assistant_service
from app.services.ai_assistant_service import (
    ConversationNotFoundError,
    ProjectNotFoundError,
)

router = APIRouter(prefix="/api", tags=["ai-assistant"])


@router.get(
    "/projects/{project_id}/ai/conversations",
    response_model=list[ConversationOut],
)
def list_conversations(
    project_id: int, db: Session = Depends(get_db)
) -> list[ConversationOut]:
    try:
        return ai_assistant_service.list_conversations(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在"
        ) from e


@router.post(
    "/projects/{project_id}/ai/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    project_id: int,
    body: ConversationCreate,
    db: Session = Depends(get_db),
) -> ConversationOut:
    try:
        return ai_assistant_service.create_conversation(
            db, project_id, title=body.title, chapter_id=body.chapter_id
        )
    except ProjectNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在"
        ) from e


@router.patch(
    "/ai/conversations/{conversation_id}", response_model=ConversationOut
)
def update_conversation(
    conversation_id: int,
    body: ConversationUpdate,
    db: Session = Depends(get_db),
) -> ConversationOut:
    try:
        return ai_assistant_service.update_conversation(
            db, conversation_id, title=body.title, chapter_id=body.chapter_id
        )
    except ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在"
        ) from e


@router.delete(
    "/ai/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: int, db: Session = Depends(get_db)
) -> None:
    try:
        ai_assistant_service.delete_conversation(db, conversation_id)
    except ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在"
        ) from e


@router.get(
    "/ai/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
def list_messages(
    conversation_id: int, db: Session = Depends(get_db)
) -> list[MessageOut]:
    try:
        return ai_assistant_service.list_messages(db, conversation_id)
    except ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在"
        ) from e


@router.post("/ai/conversations/{conversation_id}/preview-prompt")
def preview_prompt(
    conversation_id: int,
    body: PreviewMessageBody,
    db: Session = Depends(get_db),
) -> dict:
    """预览本轮真实发出去的 messages,不写库不调 LLM。"""
    try:
        messages = ai_assistant_service.assemble_messages(
            db,
            conversation_id,
            user_message=body.content,
            chapter_id=body.chapter_id,
            selection_text=body.selection_text,
            include_chapter_content=body.include_chapter_content,
            character_ids=body.character_ids,
            world_entity_ids=body.world_entity_ids,
            item_ids=body.item_ids,
        )
    except ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在"
        ) from e
    return {"messages": messages}


def _sse_from_stream(
    stream_factory,
    *,
    conversation_id: int,
) -> AsyncGenerator[dict, None]:
    """把文本增量包成 SSE 事件,流末尾返回 assistant 消息 id 给前端 join。

    stream_factory(db) → AsyncGenerator[str, None]:在生成器内部起独立 session,
    LLM 调用期间不持有路由依赖链上的 session。
    """

    async def gen():
        from app.database import SessionLocal

        with SessionLocal() as db:
            try:
                async for delta in stream_factory(db):
                    yield {
                        "event": "delta",
                        "data": json.dumps({"text": delta}, ensure_ascii=False),
                    }
                # 流式正常结束:取出最后一条 assistant 消息(刚刚 service 落库的)
                messages = ai_assistant_service.list_messages(db, conversation_id)
                last_assistant = next(
                    (m for m in reversed(messages) if m.role == "assistant"), None
                )
                payload = {
                    "message_id": last_assistant.id if last_assistant else None,
                }
                yield {
                    "event": "done",
                    "data": json.dumps(payload, ensure_ascii=False),
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

    return gen()


@router.post("/ai/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: int,
    body: SendMessageBody,
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    try:
        # 先校验存在,不存在直接 404,而不是把 AIError 包成 SSE error
        ai_assistant_service._conversation_or_raise(db, conversation_id)
    except ConversationNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="对话不存在"
        ) from e

    def factory(stream_db):
        return ai_assistant_service.stream_reply(
            stream_db,
            conversation_id,
            user_content=body.content,
            chapter_id=body.chapter_id,
            selection_text=body.selection_text,
            include_chapter_content=body.include_chapter_content,
            character_ids=body.character_ids,
            world_entity_ids=body.world_entity_ids,
            item_ids=body.item_ids,
        )

    return EventSourceResponse(
        _sse_from_stream(factory, conversation_id=conversation_id)
    )
