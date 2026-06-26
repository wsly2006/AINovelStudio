"""章节翻译服务:把中文 chapter.content 翻成目标语言,
落库为 chapter_versions(lang=target_lang, reason='translated')。

设计:
- 不动 chapter.content,中文永远是「真相」
- 术语表全量注入(项目级,~200 条上限,先全推,溢出问题等真有再说)
- 走 ai_client.stream_chat 流式输出,逐 token 推 SSE delta
"""

from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai.client import AIError, AINotConfiguredError
from app.models.chapter import Chapter
from app.models.project import Project
from app.models.translation_glossary import TranslationGlossary
from app.services import chapter_version_service, prompt_service
from app.services.chapter_service import ChapterNotFoundError, _count_words


# 目标语种用户可读名,塞进 system prompt
LANG_LABELS = {
    "en-US": "English (US English, fluent web-novel idiom)",
    "es-ES": "Spanish (España)",
    "id-ID": "Indonesian (Bahasa Indonesia)",
    "ja-JP": "Japanese (日本語、ライトノベル風)",
    "ko-KR": "Korean (한국어、웹소설 스타일)",
    "vi-VN": "Vietnamese (Tiếng Việt)",
}


def _glossary_block(entries: list[TranslationGlossary]) -> str:
    """把术语表压成 prompt 的对照块。target 为空的条目跳过 —— 没译法没法约束 AI。"""
    rows = [e for e in entries if (e.target or "").strip()]
    if not rows:
        return "(暂无对照,请按目标语自然命名,但请保持本章内同一中文词译法一致)"
    out = []
    for e in rows:
        bit = f"{e.source} → {e.target}"
        if e.notes:
            bit += f"  ({e.notes})"
        out.append(bit)
    return "\n".join(out)


def _previous_summary(db: Session, project_id: int, current_id: int) -> str:
    """前序章节的中文 summary 列表。翻译时给 AI 留前情提要,避免上下文断裂。"""
    stmt = (
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.order_index)
    )
    chapters = list(db.execute(stmt).scalars().all())
    lines: list[str] = []
    for c in chapters:
        if c.id == current_id:
            break
        if c.summary:
            lines.append(f"- 第 {c.order_index} 章《{c.title}》: {c.summary}")
    return "\n".join(lines) if lines else "(无前序章节)"


def _project_brief(project: Project) -> str:
    parts = [f"《{project.name}》"]
    if project.genre:
        parts.append(f"类型:{project.genre}")
    if project.description:
        parts.append(f"简介:{project.description}")
    return " / ".join(parts)


def _build_messages(
    db: Session,
    chapter: Chapter,
    project: Project,
    target_lang: str,
    glossary_entries: list[TranslationGlossary],
    extra_instruction: str | None,
) -> list[dict]:
    label = LANG_LABELS.get(target_lang, target_lang)
    chapter_label = (
        f"第 {chapter.order_index} 章《{chapter.title}》"
        if chapter.title
        else f"第 {chapter.order_index} 章"
    )
    synopsis_block = ""
    syn = (project.synopsis or "").strip()
    if syn:
        synopsis_block = f"故事总纲(供保持调性一致):\n{syn}"
    extra_block = ""
    if extra_instruction and extra_instruction.strip():
        extra_block = f"额外要求:{extra_instruction.strip()}\n\n"

    # 文风指令:作者写的目标语自然语言文风偏好,与术语表同级硬约束。
    # 空时给兜底文案,避免 prompt 里出现「【文风指令】:」后面挂空字符串。
    guide = (project.translation_style_guide or "").strip()
    style_guide_block = guide or "(作者未指定特殊文风,按目标语自然文风行文)"

    return prompt_service.render(
        db,
        "chapter.translate",
        {
            "target_lang_label": label,
            "project_info": _project_brief(project),
            "synopsis_block": synopsis_block,
            "glossary_block": _glossary_block(glossary_entries),
            "style_guide_block": style_guide_block,
            "previous_summary": _previous_summary(
                db, project.id, chapter.id
            ),
            "chapter_label": chapter_label,
            "original_content": chapter.content or "",
            "extra_instruction_block": extra_block,
        },
    )


async def translate_and_persist(
    db: Session,
    chapter_id: int,
    target_lang: str,
    *,
    extra_instruction: str | None = None,
) -> AsyncGenerator[dict, None]:
    """串起整条:校验 → prompt → stream → 累积 → snapshot 落库,逐步 yield SSE 事件。

    事件:
    - start: {chapter_id, target_lang}
    - delta: {text}
    - done:  {version_id, word_count, chapter_id}
    - error: {message}
    """
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        yield {"event": "error", "data": {"message": "章节不存在"}}
        return
    if not (chapter.content or "").strip():
        yield {
            "event": "error",
            "data": {"message": "本章正文为空,先写完再翻"},
        }
        return

    project = db.get(Project, chapter.project_id)
    if project is None:
        yield {"event": "error", "data": {"message": "工程不存在"}}
        return

    # 拉术语表(本工程,本目标语)。target 为空的条目交给 prompt 层过滤
    g_stmt = (
        select(TranslationGlossary)
        .where(
            TranslationGlossary.project_id == project.id,
            TranslationGlossary.target_lang == target_lang,
        )
        .order_by(TranslationGlossary.entry_type, TranslationGlossary.source)
    )
    glossary = list(db.execute(g_stmt).scalars().all())

    messages = _build_messages(
        db, chapter, project, target_lang, glossary, extra_instruction
    )

    yield {
        "event": "start",
        "data": {"chapter_id": chapter.id, "target_lang": target_lang},
    }

    chunks: list[str] = []
    try:
        async for delta in ai_client.stream_chat(
            db,
            messages,
            scene="chapter.translate",
            project_id=project.id,
        ):
            if not delta:
                continue
            chunks.append(delta)
            yield {"event": "delta", "data": {"text": delta}}
    except AINotConfiguredError as e:
        yield {"event": "error", "data": {"message": str(e)}}
        return
    except AIError as e:
        yield {"event": "error", "data": {"message": str(e)}}
        return

    full = "".join(chunks).strip()
    if not full:
        yield {
            "event": "error",
            "data": {"message": "AI 未返回任何译文,本次未保存"},
        }
        return

    # 落库:走 lang-aware snapshot,与本语种已有版本独立 trim
    version = chapter_version_service.snapshot(
        db,
        chapter_id,
        reason="translated",
        label=f"AI 翻译 → {target_lang}",
        lang=target_lang,
        content_override=full,
    )
    yield {
        "event": "done",
        "data": {
            "version_id": version.id,
            "chapter_id": chapter.id,
            "word_count": version.word_count,
            "target_lang": target_lang,
        },
    }


__all__ = [
    "LANG_LABELS",
    "translate_and_persist",
]
