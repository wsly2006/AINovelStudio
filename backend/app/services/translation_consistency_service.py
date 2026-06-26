"""翻译一致性检查:扫工程的「最新翻译版本」,对照术语表查 target 漂移。

策略(M4,纯字符串匹配):
- 对每章拿 lang=target_lang 的最新 chapter_version
- 对每条术语:若 source 在 chapter.content(中文原文)出现,
  且 target 在 version.content 没出现,记一条 issue
- 只出报告,不改任何东西

不做的(M5+):
- 同义词 / 大小写变体(Li Mubai vs Mubai Li / li mubai)
- AI 语义判断
- 一键修复
"""

from collections.abc import Iterable

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_version import ChapterVersion
from app.models.project import Project
from app.models.translation_glossary import TranslationGlossary


class ProjectNotFoundForConsistencyError(Exception):
    """工程不存在"""


def _latest_version_per_chapter(
    db: Session, chapter_ids: Iterable[int], target_lang: str
) -> dict[int, ChapterVersion]:
    """对每个 chapter_id 取该 target_lang 下 created_at 最新的一条版本。

    实现走 Python 端聚合 —— SQLite 没有窗口函数的稳定支持,
    版本表上限 5/lang/chapter,数据量很小,O(N) 完全够。
    """
    ids = list(chapter_ids)
    if not ids:
        return {}
    stmt = (
        select(ChapterVersion)
        .where(
            ChapterVersion.chapter_id.in_(ids),
            ChapterVersion.lang == target_lang,
        )
        .order_by(ChapterVersion.chapter_id, desc(ChapterVersion.created_at))
    )
    latest: dict[int, ChapterVersion] = {}
    for v in db.execute(stmt).scalars().all():
        # 因为按 created_at desc 排,首次见到的就是最新的
        latest.setdefault(v.chapter_id, v)
    return latest


def check_project(
    db: Session,
    project_id: int,
    target_lang: str = "en-US",
) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundForConsistencyError(project_id)

    # 1. 拉工程章节
    ch_stmt = (
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .order_by(Chapter.order_index)
    )
    chapters = list(db.execute(ch_stmt).scalars().all())

    # 2. 拉每章在 target_lang 下的最新翻译版本
    latest_map = _latest_version_per_chapter(
        db, (c.id for c in chapters), target_lang
    )

    # 3. 拉术语表(只看 target 非空的条目)
    g_stmt = (
        select(TranslationGlossary)
        .where(
            TranslationGlossary.project_id == project_id,
            TranslationGlossary.target_lang == target_lang,
        )
        .order_by(TranslationGlossary.id)
    )
    glossary = [
        e for e in db.execute(g_stmt).scalars().all() if (e.target or "").strip()
    ]

    issues: list[dict] = []
    checked = 0
    for ch in chapters:
        v = latest_map.get(ch.id)
        if v is None:
            continue
        checked += 1
        original = ch.content or ""
        translated = v.content or ""
        for g in glossary:
            src = g.source
            tgt = g.target
            if not src or not tgt:
                continue
            # 漂移定义:中文原文里出现这个术语,但译文里看不到说好的对应英文
            if src in original and tgt not in translated:
                issues.append(
                    {
                        "chapter_id": ch.id,
                        "chapter_order": ch.order_index,
                        "chapter_title": ch.title or "",
                        "version_id": v.id,
                        "source": src,
                        "expected_target": tgt,
                        "entry_type": g.entry_type,
                    }
                )

    return {
        "target_lang": target_lang,
        "checked_chapters": checked,
        "total_chapters": len(chapters),
        "glossary_size": len(glossary),
        "issues": issues,
    }


__all__ = [
    "ProjectNotFoundForConsistencyError",
    "check_project",
]
