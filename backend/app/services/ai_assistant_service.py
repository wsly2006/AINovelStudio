"""AI 助手服务:会话 CRUD + 上下文组装 + 流式对话。

设计要点:
- 一个工程多个 conversation,按 updated_at 倒序展示
- 消息追加;assistant 消息在流式开始前先建占位空行,流完以全文回写
- 上下文与 chapter_ai_service 共用 _load_*,长章节正文截断在 prompts 层处理
"""

from collections.abc import AsyncGenerator

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import prompts
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.chapter import Chapter
from app.models.character import Character
from app.models.item import Item
from app.models.project import Project
from app.models.world_entity import WorldEntity
from app.schemas.ai_assistant import ConversationOut, MessageOut
from app.services import plot_thread_service


class ConversationNotFoundError(Exception):
    pass


class ProjectNotFoundError(Exception):
    pass


# 历史回放最多带几对(user/assistant);更早的不进 prompt,但仍存在 DB 里可看
HISTORY_TURNS_LIMIT = 6


def _project_or_raise(db: Session, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise ProjectNotFoundError(project_id)
    return p


def _conversation_or_raise(db: Session, conversation_id: int) -> AIConversation:
    c = db.get(AIConversation, conversation_id)
    if c is None:
        raise ConversationNotFoundError(conversation_id)
    return c


def _message_count(db: Session, conversation_id: int) -> int:
    return int(
        db.execute(
            select(func.count(AIMessage.id)).where(
                AIMessage.conversation_id == conversation_id
            )
        ).scalar_one()
    )


def _to_conv_out(db: Session, conv: AIConversation) -> ConversationOut:
    out = ConversationOut.model_validate(conv)
    out.message_count = _message_count(db, conv.id)
    return out


def list_conversations(db: Session, project_id: int) -> list[ConversationOut]:
    _project_or_raise(db, project_id)
    stmt = (
        select(AIConversation)
        .where(AIConversation.project_id == project_id)
        .order_by(AIConversation.updated_at.desc(), AIConversation.id.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [_to_conv_out(db, c) for c in rows]


def create_conversation(
    db: Session,
    project_id: int,
    *,
    title: str | None = None,
    chapter_id: int | None = None,
) -> ConversationOut:
    _project_or_raise(db, project_id)
    conv = AIConversation(
        project_id=project_id,
        chapter_id=chapter_id,
        title=(title or "新对话").strip()[:120] or "新对话",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _to_conv_out(db, conv)


def update_conversation(
    db: Session,
    conversation_id: int,
    *,
    title: str | None = None,
    chapter_id: int | None = None,
) -> ConversationOut:
    conv = _conversation_or_raise(db, conversation_id)
    if title is not None:
        t = title.strip()[:120]
        conv.title = t or "新对话"
    if chapter_id is not None:
        conv.chapter_id = chapter_id or None
    db.commit()
    db.refresh(conv)
    return _to_conv_out(db, conv)


def delete_conversation(db: Session, conversation_id: int) -> None:
    conv = _conversation_or_raise(db, conversation_id)
    db.delete(conv)
    db.commit()


def list_messages(db: Session, conversation_id: int) -> list[MessageOut]:
    _conversation_or_raise(db, conversation_id)
    stmt = (
        select(AIMessage)
        .where(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.id)
    )
    rows = db.execute(stmt).scalars().all()
    return [MessageOut.model_validate(m) for m in rows]


def _load_history_for_prompt(
    db: Session, conversation_id: int
) -> list[dict]:
    """取最近 N 轮对话(user/assistant 成对),按时间正序输出。"""
    stmt = (
        select(AIMessage)
        .where(
            AIMessage.conversation_id == conversation_id,
            AIMessage.role.in_(("user", "assistant")),
            AIMessage.content != "",
        )
        .order_by(AIMessage.id.desc())
        .limit(HISTORY_TURNS_LIMIT * 2)
    )
    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()
    return [{"role": m.role, "content": m.content} for m in rows]


def _load_chapter(db: Session, chapter_id: int | None) -> Chapter | None:
    if not chapter_id:
        return None
    return db.get(Chapter, chapter_id)


def _load_characters(
    db: Session, project_id: int, ids: list[int] | None
) -> list[Character]:
    if not ids:
        return []
    stmt = (
        select(Character)
        .where(Character.project_id == project_id, Character.id.in_(ids))
        .order_by(Character.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def _load_world(
    db: Session, project_id: int, ids: list[int] | None
) -> list[WorldEntity]:
    if not ids:
        return []
    stmt = (
        select(WorldEntity)
        .where(WorldEntity.project_id == project_id, WorldEntity.id.in_(ids))
        .order_by(WorldEntity.kind, WorldEntity.name)
    )
    return list(db.execute(stmt).scalars().all())


def _load_items(
    db: Session, project_id: int, ids: list[int] | None
) -> list[Item]:
    if not ids:
        return []
    stmt = (
        select(Item)
        .where(Item.project_id == project_id, Item.id.in_(ids))
        .order_by(Item.name)
    )
    return list(db.execute(stmt).scalars().all())


def assemble_messages(
    db: Session,
    conversation_id: int,
    *,
    user_message: str,
    chapter_id: int | None,
    selection_text: str | None,
    include_chapter_content: bool,
    character_ids: list[int],
    world_entity_ids: list[int],
    item_ids: list[int],
    include_history: bool = True,
) -> list[dict]:
    """组装本轮 prompt(含历史)。供发送 + 预览共用。"""
    conv = _conversation_or_raise(db, conversation_id)
    project = _project_or_raise(db, conv.project_id)

    # chapter_id 优先取本轮显式传入,否则回落到会话默认
    effective_chapter_id = chapter_id if chapter_id is not None else conv.chapter_id
    chapter = _load_chapter(db, effective_chapter_id)
    if chapter is not None and chapter.project_id != project.id:
        chapter = None

    characters = _load_characters(db, project.id, character_ids)
    worlds = _load_world(db, project.id, world_entity_ids)
    items = _load_items(db, project.id, item_ids)
    threads = plot_thread_service.list_active_threads_for_prompt(db, project.id)

    history = _load_history_for_prompt(db, conversation_id) if include_history else []

    return prompts.build_assistant_messages(
        project,
        user_message=user_message,
        chapter=chapter,
        include_chapter_content=include_chapter_content,
        characters=characters,
        world_entities=worlds,
        items=items,
        plot_threads=threads,
        selection_text=selection_text,
        history=history,
        db=db,
    )


def append_user_message(
    db: Session,
    conversation_id: int,
    *,
    content: str,
    chapter_id: int | None,
    selection_text: str | None,
) -> AIMessage:
    conv = _conversation_or_raise(db, conversation_id)
    msg = AIMessage(
        conversation_id=conv.id,
        role="user",
        content=content,
        chapter_id=chapter_id,
        selection_text=(selection_text or None),
    )
    db.add(msg)
    # 第一条用户消息时,自动用其前 30 字给会话起标题
    if conv.title in ("", "新对话") and _message_count(db, conv.id) == 0:
        head = content.strip().splitlines()[0] if content.strip() else ""
        conv.title = (head[:30] or "新对话").strip()
    if chapter_id and not conv.chapter_id:
        conv.chapter_id = chapter_id
    db.commit()
    db.refresh(msg)
    return msg


def append_assistant_message(
    db: Session, conversation_id: int, content: str
) -> AIMessage:
    conv = _conversation_or_raise(db, conversation_id)
    msg = AIMessage(
        conversation_id=conv.id,
        role="assistant",
        content=content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


async def stream_reply(
    db: Session,
    conversation_id: int,
    *,
    user_content: str,
    chapter_id: int | None,
    selection_text: str | None,
    include_chapter_content: bool,
    character_ids: list[int],
    world_entity_ids: list[int],
    item_ids: list[int],
) -> AsyncGenerator[str, None]:
    """先存 user 消息,再流式拿 reply,流完落库 assistant 消息。

    SSE 路由层会捕获 AIError / AINotConfiguredError 并转成 error 事件。
    若流中途异常,这里直接抛出,不写 assistant 消息(用户可重发)。
    """
    conv = _conversation_or_raise(db, conversation_id)
    append_user_message(
        db,
        conversation_id,
        content=user_content,
        chapter_id=chapter_id,
        selection_text=selection_text,
    )

    messages = assemble_messages(
        db,
        conversation_id,
        user_message=user_content,
        chapter_id=chapter_id,
        selection_text=selection_text,
        include_chapter_content=include_chapter_content,
        character_ids=character_ids,
        world_entity_ids=world_entity_ids,
        item_ids=item_ids,
    )

    buf: list[str] = []
    async for delta in ai_client.stream_chat(
        db, messages, scene="assistant.chat", project_id=conv.project_id
    ):
        buf.append(delta)
        yield delta

    full = "".join(buf).strip()
    if full:
        append_assistant_message(db, conversation_id, full)
