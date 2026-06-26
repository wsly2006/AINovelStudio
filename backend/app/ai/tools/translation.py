"""翻译 pipeline 的 MCP tools(P0-M6)。

把 M1-M5 的术语表 CRUD / 章节翻译 / 一致性检查 这些 HTTP 路由后面的服务,
也以 MCP 工具的形式暴露,让 Claude Desktop / Code 能直接驱动翻译流程。

设计要点:
- list_glossary / get_chapter_version 只读,直接 mcp_safe=True
- upsert_glossary_entry / translate_chapter 是写操作,dangerous=True,
  受 hooks.writes_enabled 闸门保护
- translate_chapter 同步阻塞返回,内部走 chapter_translation_service
  的 translate_chapter_blocking(asyncio.run 把异步 SSE 流收完)
- 不返回译文全文,只给 500 字 preview;完整内容让 LLM 用 get_chapter_version
  专门拉
"""

from __future__ import annotations

from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.schemas.translation_glossary import (
    ENTRY_TYPES,
    GlossaryCreate,
    GlossaryUpdate,
)
from app.services import (
    chapter_translation_service,
    chapter_version_service,
    translation_consistency_service,
    translation_glossary_service,
)

_PREVIEW_LEN = 500


@tool(category="translation")
@friendly_errors
def list_glossary(
    project_id: int,
    target_lang: str = "en-US",
) -> list[dict]:
    """列出某工程在指定目标语下的翻译术语表。

    参数:
    - project_id: 工程 id(必填)
    - target_lang: 'en-US' / 'es-ES' / 'id-ID' / 'ja-JP' / 'ko-KR' / 'vi-VN'

    每条返回 id / source(中文) / target(译文) / target_lang / entry_type /
    locked / notes。target 为空表示该术语还没确定译法。

    需要某 source 现在译什么时,先调本工具,而不是凭印象。
    """
    with with_db() as db:
        rows = translation_glossary_service.list_entries(
            db, project_id, target_lang=target_lang
        )
        return [r.model_dump(mode="json") for r in rows]


@tool(category="translation", dangerous=True)
@friendly_errors
def upsert_glossary_entry(
    project_id: int,
    source: str,
    target: str,
    target_lang: str = "en-US",
    entry_type: str = "other",
    notes: str | None = None,
) -> dict:
    """新建或更新一条翻译术语。

    按 (project_id, source, target_lang) 唯一约束 upsert:
    - 已存在 → 更新 target / entry_type / notes
    - 不存在 → 新建

    locked=True 的条目不动(那是作者校对锁定的,LLM 不应覆盖)。
    entry_type 必须是 person | place | org | term | skill | item | other。

    用于在翻译过程中遇到新名词时记下译法,后续翻译会自动注入 prompt 保持一致。
    """
    if entry_type not in ENTRY_TYPES:
        raise ValueError(
            f"entry_type 必须是 {list(ENTRY_TYPES)} 之一,收到 {entry_type!r}"
        )
    with with_db() as db:
        existing_rows = translation_glossary_service.list_entries(
            db, project_id, target_lang=target_lang
        )
        existing = next((e for e in existing_rows if e.source == source), None)
        if existing is None:
            created = translation_glossary_service.create_entry(
                db,
                project_id,
                GlossaryCreate(
                    source=source,
                    target=target,
                    target_lang=target_lang,
                    entry_type=entry_type,
                    notes=notes,
                ),
            )
            return {"action": "created", "entry": created.model_dump(mode="json")}
        if existing.locked:
            return {
                "action": "skipped_locked",
                "entry": existing.model_dump(mode="json"),
            }
        updated = translation_glossary_service.update_entry(
            db,
            existing.id,
            GlossaryUpdate(
                target=target,
                entry_type=entry_type,
                notes=notes,
            ),
        )
        return {"action": "updated", "entry": updated.model_dump(mode="json")}


@tool(category="translation", dangerous=True)
@friendly_errors
def translate_chapter(
    chapter_id: int,
    target_lang: str = "en-US",
    extra_instruction: str | None = None,
) -> dict:
    """把单个章节翻成目标语言,落库为 chapter_versions(lang=target_lang)。

    - 不动 chapter.content(中文是真相)
    - 自动注入项目术语表 + translation_style_guide
    - 同步阻塞:跑完才返回。LLM 调用方应有耐心,长章节可能数十秒

    返回 {version_id, word_count, target_lang, chapter_id, content_preview}。
    content_preview 只截前 500 字符,要完整译文用 get_chapter_version。
    """
    with with_db() as db:
        done = chapter_translation_service.translate_chapter_blocking(
            db,
            chapter_id,
            target_lang,
            extra_instruction=extra_instruction,
        )
        # 拉一下完整 version 拿 preview;不返回全文避免塞爆 LLM 上下文
        version = chapter_version_service.get_version(db, done["version_id"])
        full = version.content or ""
        preview = full[:_PREVIEW_LEN]
        if len(full) > _PREVIEW_LEN:
            preview += "…"
        return {
            "chapter_id": done["chapter_id"],
            "version_id": done["version_id"],
            "target_lang": done["target_lang"],
            "word_count": done["word_count"],
            "content_preview": preview,
            "truncated": len(full) > _PREVIEW_LEN,
        }


@tool(category="translation")
@friendly_errors
def check_translation_consistency(
    project_id: int,
    target_lang: str = "en-US",
) -> dict:
    """扫工程的最新翻译版本,对照术语表检查名词漂移。

    对每章最新 lang=target_lang 的 chapter_version 做纯字符串匹配:
    若某术语在中文原文里出现,但 target 字符串没出现在译文里,记一条 issue。

    返回 {target_lang, checked_chapters, total_chapters, glossary_size, issues}。
    issues 形如 [{chapter_id, chapter_order, chapter_title, version_id,
    source, expected_target, entry_type}]。

    适合翻译完一批章节后做收尾检查;空 issues 表示术语全命中。
    """
    with with_db() as db:
        return translation_consistency_service.check_project(
            db, project_id, target_lang=target_lang
        )


@tool(category="translation")
@friendly_errors
def get_chapter_version(version_id: int) -> dict:
    """读取单条章节版本的完整内容(包含 lang 字段)。

    给 translate_chapter 配套用:拿到 version_id 后想看完整译文就调本工具。
    也能查中文版本的历史快照。

    返回 {id, chapter_id, content, word_count, reason, label, lang, created_at}。
    """
    with with_db() as db:
        return chapter_version_service.get_version(db, version_id).model_dump(
            mode="json"
        )
