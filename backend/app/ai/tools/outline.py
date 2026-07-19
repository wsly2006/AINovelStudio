"""大纲工具:读大纲 / 改大纲 / AI 批量草拟 / 追加落库。

「大纲」本身没有独立表 — 就是 chapter 的 title + summary + beats 三个字段。
所以这里既没有新数据模型,也不重复 chapter CRUD,直接复用:
- 读取 → 从 Chapter 直取
- 修改 → chapter_service.update_chapter(带上 beats)
- AI 草拟 → outline_service.batch_suggest(不落库,只返 drafts)
- 追加 → outline_service.batch_create(status='outlined' 的空正文章节)

「用大纲生成正文」不需要单独工具 — 现有的 generate_chapter_content 会自动读
chapter.summary + chapter.beats 组装 prompt,LLM 顺着大纲写就是了。
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.async_util import run_async_blocking
from app.ai.tools.db import with_db
from app.ai.tools.errors import friendly_errors
from app.ai.tools.registry import tool
from app.models.chapter import Chapter
from app.schemas.chapter import ChapterBeat, ChapterUpdate, OutlineDraft
from app.services import chapter_service, outline_service


def _coerce_beats(raw: Any) -> list[ChapterBeat]:
    """把 LLM 传进来的 beats 参数(list[dict])转成 ChapterBeat 列表。

    容忍缺字段 / 多字段,严格校验交给 ChapterBeat 本身的 validator。
    传空列表 [] → 返回空列表(update_chapter_outline 用它清空节拍)。
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("beats 必须是数组,如 [{'title':'开场','detail':'...'}]")
    out: list[ChapterBeat] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"beat 应为对象,收到 {type(item).__name__}")
        out.append(ChapterBeat(**item))
    return out


def _coerce_drafts(raw: Any) -> list[OutlineDraft]:
    """把 LLM 传进来的 drafts(list[dict])转成 OutlineDraft 列表。"""
    if not isinstance(raw, list) or not raw:
        raise ValueError("drafts 必须是非空数组")
    out: list[OutlineDraft] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"draft 应为对象,收到 {type(item).__name__}")
        beats = _coerce_beats(item.get("beats"))
        out.append(
            OutlineDraft(
                title=(item.get("title") or "").strip()[:200],
                summary=(item.get("summary") or None),
                beats=beats,
            )
        )
    return out


@tool(category="outline")
@friendly_errors
def get_project_outline(project_id: int) -> list[dict]:
    """列出工程的完整大纲:每章的 title / summary / beats。

    与 list_chapters 的区别:list_chapters 不返回 beats(节拍),这里回。
    典型场景:LLM 要通读全书结构、找剧情漏洞、给下一章排点子时先调这个。

    返回按 order_index 排序的数组,每项:
        {id, order_index, title, status, word_count,
         summary, beats: [{title, detail, thread_titles}] | null}
    """
    with with_db() as db:
        # 先确认工程存在(friendly_errors 会把 ProjectNotFoundError 转成 LLM 友好提示)
        chapter_service.list_chapters(db, project_id)  # 只用于触发 ProjectNotFound 检测
        from sqlalchemy import select

        rows = list(
            db.execute(
                select(Chapter)
                .where(Chapter.project_id == project_id)
                .order_by(Chapter.order_index)
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": c.id,
                "order_index": c.order_index,
                "title": c.title,
                "status": c.status,
                "word_count": c.word_count,
                "summary": c.summary,
                "beats": c.beats,
            }
            for c in rows
        ]


@tool(category="outline", dangerous=True)
@friendly_errors
def update_chapter_outline(
    chapter_id: int,
    title: str | None = None,
    summary: str | None = None,
    beats: list[dict] | None = None,
    status: str | None = None,
) -> dict:
    """修改单个章节的大纲(title / summary / beats / status)。

    不动 content — 要改正文用 update_chapter 或 generate_chapter_content。
    改 beats 会连带清空已存在的 beats_alignment(旧对账不再可信)。

    参数:
    - chapter_id: 章节 id(必填)
    - title: 新标题;传 None 不动,传空串等价清空
    - summary: 新大纲文本;None 不动,空串→None
    - beats: 节拍列表;None 不动,[] 清空。每一项形如:
        {"title": "开场对峙", "detail": "9 黑衣人围木仁雄", "thread_titles": ["主线A"]}
      detail / thread_titles 可省
    - status: draft | outlined | writing | done

    返回更新后的章节详情(含 content — 若正文本身没变,只是重新拉出来)。
    """
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if summary is not None:
        # 空串等价 None,匹配 schema 的 _strip_summary 行为
        payload["summary"] = summary or None
    if beats is not None:
        payload["beats"] = [b.model_dump() for b in _coerce_beats(beats)]
    if status is not None:
        payload["status"] = status

    if not payload:
        raise ValueError("至少传入 title / summary / beats / status 中的一个字段")

    with with_db() as db:
        chapter_service.update_chapter(db, chapter_id, ChapterUpdate(**payload))
        return chapter_service.get_chapter(db, chapter_id).model_dump(mode="json")


@tool(category="outline", dangerous=True)
@friendly_errors
def suggest_chapter_outlines(
    project_id: int,
    count: int = 5,
    start_order_index: int | None = None,
    extra_instruction: str | None = None,
    target_word_count: int = 4000,
) -> dict:
    """让 AI 批量草拟连续 N 章大纲,**不落库**。

    走的是和前端「大纲模式 - 批量草拟」按钮完全一样的服务
    (outline_service.batch_suggest),自动带上工程简介 / 主线 / 前序章节 /
    人物 / 世界观。

    参数:
    - project_id: 工程 id
    - count: 要草拟几章(1-30,默认 5)
    - start_order_index: 从第几章开始草拟。None = 追加到末尾之后;给值则
      从该 order_index 开始,前序 = order_index < 它的所有章节
    - extra_instruction: 追加指令,如"这几章要引出反派并交代主角身世"
    - target_word_count: 每章目标字数,影响节拍密度

    返回 {drafts: [{title, summary, beats: [...]}]}。
    看过后满意就调 add_chapter_outlines(project_id, drafts) 落库。
    """
    if count < 1 or count > 30:
        raise ValueError("count 必须在 1-30 之间")

    async def _run() -> list[OutlineDraft]:
        # SQLAlchemy Session 非线程安全,新线程新 loop 里独立开
        from app.database import SessionLocal

        db = SessionLocal()
        try:
            return await outline_service.batch_suggest(
                db,
                project_id,
                count=count,
                start_order_index=start_order_index,
                extra_instruction=extra_instruction,
                target_word_count=target_word_count,
            )
        finally:
            db.close()

    drafts = run_async_blocking(_run())
    return {"drafts": [d.model_dump(mode="json") for d in drafts]}


@tool(category="outline", dangerous=True)
@friendly_errors
def add_chapter_outlines(
    project_id: int,
    drafts: list[dict],
) -> dict:
    """把大纲草稿追加到工程末尾,每条建一个 status='outlined' 的空正文章节。

    典型工作流:
        r = suggest_chapter_outlines(project_id=5, count=3)
        # 人工/LLM 审阅 r["drafts"],可以按需修改再传回
        add_chapter_outlines(project_id=5, drafts=r["drafts"])

    参数:
    - project_id: 工程 id
    - drafts: 每项 {title, summary?, beats?}。beats 每项 {title, detail?, thread_titles?}

    返回 {created: [{id, order_index, title, ...}]}。新章节 status='outlined',
    正文为空,后续可用 generate_chapter_content 让 AI 顺着大纲写正文。
    """
    coerced = _coerce_drafts(drafts)
    with with_db() as db:
        created = outline_service.batch_create(db, project_id, coerced)
        return {"created": [c.model_dump(mode="json") for c in created]}
