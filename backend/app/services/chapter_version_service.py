"""章节版本快照服务。

策略:
- 只在重大事件触发(AI 覆盖前 / 手动保存 / 还原前自动快照),autosave 不写。
- 每章节最多保留 5 条,新增后立刻淘汰最旧的。
- 还原前会先把当前内容快照一份,避免"还原选错了"再次丢数据。
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


class ChapterVersionNotFoundError(Exception):
    """版本不存在"""


def _build_preview(content: str | None) -> str:
    if not content:
        return ""
    s = content.strip().replace("\n", " ")
    return s if len(s) <= PREVIEW_LEN else s[:PREVIEW_LEN] + "..."


def _trim_excess(db: Session, chapter_id: int) -> None:
    """超过 MAX_VERSIONS_PER_CHAPTER 时删最旧的几条。"""
    stmt = (
        select(ChapterVersion.id)
        .where(ChapterVersion.chapter_id == chapter_id)
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
) -> ChapterVersion:
    """把章节当前内容快照成一条版本。reason: ai_overwrite | manual | restore。"""
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)

    v = ChapterVersion(
        chapter_id=chapter_id,
        content=c.content or "",
        word_count=c.word_count or 0,
        reason=reason,
        label=label,
    )
    db.add(v)
    db.flush()
    _trim_excess(db, chapter_id)
    if commit:
        db.commit()
        db.refresh(v)
    return v


def list_versions(db: Session, chapter_id: int) -> list[ChapterVersionListItem]:
    if db.get(Chapter, chapter_id) is None:
        raise ChapterNotFoundError(chapter_id)
    stmt = (
        select(ChapterVersion)
        .where(ChapterVersion.chapter_id == chapter_id)
        .order_by(ChapterVersion.created_at.desc(), ChapterVersion.id.desc())
        .limit(MAX_VERSIONS_PER_CHAPTER)
    )
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
    """把指定版本写回章节,并先把当前内容快照一份(reason='restore')。"""
    v = db.get(ChapterVersion, version_id)
    if v is None:
        raise ChapterVersionNotFoundError(version_id)
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
