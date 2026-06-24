"""章节版本快照服务。

策略:
- 只在重大事件触发(AI 覆盖前 / 手动保存 / 还原前自动快照 / AI 翻译完成),autosave 不写。
- 每章节 + 每语种独立保留 5 条:zh-CN 翻译 6 次只留 5 个 zh-CN 版本,
  不会因为多次翻 en-US 把 zh-CN 历史挤掉。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_version import ChapterVersion
from app.schemas.chapter_version import (
    ChapterVersionDetail,
    ChapterVersionListItem,
)
from app.services.chapter_service import ChapterNotFoundError, _count_words

MAX_VERSIONS_PER_CHAPTER = 5
PREVIEW_LEN = 80
DEFAULT_LANG = "zh-CN"


class ChapterVersionNotFoundError(Exception):
    """版本不存在"""


class ChapterVersionLangMismatchError(Exception):
    """试图把非 zh-CN 的版本还原回 chapter.content。
    chapter.content 永远是中文真相,翻译版本只读不还原。"""


def _build_preview(content: str | None) -> str:
    if not content:
        return ""
    s = content.strip().replace("\n", " ")
    return s if len(s) <= PREVIEW_LEN else s[:PREVIEW_LEN] + "..."


def _trim_excess(db: Session, chapter_id: int, lang: str) -> None:
    """超过 MAX_VERSIONS_PER_CHAPTER 时删最旧的几条。

    按 (chapter_id, lang) 分桶 trim:每个语种独立保留 5 条。
    """
    stmt = (
        select(ChapterVersion.id)
        .where(
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.lang == lang,
        )
        .order_by(ChapterVersion.created_at.desc(), ChapterVersion.id.desc())
        .offset(MAX_VERSIONS_PER_CHAPTER)
    )
    overflow_ids = db.execute(stmt).scalars().all()
    if not overflow_ids:
        return
    for vid in overflow_ids:
        v = db.get(ChapterVersion, vid)
        if v is not None:
            db.delete(v)


def snapshot(
    db: Session,
    chapter_id: int,
    reason: str,
    label: str | None = None,
    *,
    commit: bool = True,
    lang: str = DEFAULT_LANG,
    content_override: str | None = None,
) -> ChapterVersion:
    """把章节当前内容快照成一条版本。

    - reason: ai_overwrite | manual | restore | translated
    - lang: 默认 zh-CN(原文);翻译走 en-US 等
    - content_override: 显式传入要落库的内容(如 AI 翻译累积出的英文文本);
      不传时按原行为读 chapter.content
    """
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)

    if content_override is not None:
        content = content_override
        word_count = _count_words(content)
    else:
        content = c.content or ""
        word_count = c.word_count or 0

    v = ChapterVersion(
        chapter_id=chapter_id,
        content=content,
        word_count=word_count,
        reason=reason,
        label=label,
        lang=lang,
    )
    db.add(v)
    db.flush()
    _trim_excess(db, chapter_id, lang)
    if commit:
        db.commit()
        db.refresh(v)
    return v


def list_versions(
    db: Session,
    chapter_id: int,
    *,
    lang: str | None = None,
) -> list[ChapterVersionListItem]:
    """列章节版本。lang=None 时返回所有语种的版本(混排,新的在前),
    lang='en-US' 时只返回该语种。"""
    if db.get(Chapter, chapter_id) is None:
        raise ChapterNotFoundError(chapter_id)
    stmt = select(ChapterVersion).where(ChapterVersion.chapter_id == chapter_id)
    if lang:
        stmt = stmt.where(ChapterVersion.lang == lang)
    stmt = stmt.order_by(
        ChapterVersion.created_at.desc(), ChapterVersion.id.desc()
    )
    if lang:
        # 单语种限到 5 条;多语种全展示(最多 lang 数 × 5,不会失控)
        stmt = stmt.limit(MAX_VERSIONS_PER_CHAPTER)
    rows = db.execute(stmt).scalars().all()
    out: list[ChapterVersionListItem] = []
    for r in rows:
        item = ChapterVersionListItem.model_validate(r)
        item.preview = _build_preview(r.content)
        out.append(item)
    return out


def get_version(db: Session, version_id: int) -> ChapterVersionDetail:
    v = db.get(ChapterVersion, version_id)
    if v is None:
        raise ChapterVersionNotFoundError(version_id)
    return ChapterVersionDetail.model_validate(v)


def restore(db: Session, version_id: int) -> Chapter:
    """把指定版本写回章节,并先把当前内容快照一份(reason='restore')。

    chapter.content 永远是中文真相;非 zh-CN 版本不能还原回去,
    要看英文等翻译,直接读 version.content 就行。
    """
    v = db.get(ChapterVersion, version_id)
    if v is None:
        raise ChapterVersionNotFoundError(version_id)
    if (v.lang or DEFAULT_LANG) != DEFAULT_LANG:
        raise ChapterVersionLangMismatchError(
            f"version#{v.id} 是 {v.lang},不能还原到中文正文"
        )
    c = db.get(Chapter, v.chapter_id)
    if c is None:
        raise ChapterNotFoundError(v.chapter_id)

    # 把当前内容快照成一条 'restore' 版本,作为还原前的兜底
    snapshot(db, c.id, reason="restore", label=None, commit=False)

    c.content = v.content or ""
    c.word_count = _count_words(c.content)
    db.commit()
    db.refresh(c)
    return c


def delete_version(db: Session, version_id: int) -> ChapterVersion:
    """删除单条版本,返回被删的实例供 API 校验所属章节。"""
    v = db.get(ChapterVersion, version_id)
    if v is None:
        raise ChapterVersionNotFoundError(version_id)
    db.delete(v)
    db.commit()
    return v
