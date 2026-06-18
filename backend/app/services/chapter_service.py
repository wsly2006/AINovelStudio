from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.project import Project
from app.schemas.chapter import (
    ChapterCreate,
    ChapterDetail,
    ChapterListItem,
    ChapterUpdate,
)


class ChapterNotFoundError(Exception):
    """章节不存在"""


class ProjectNotFoundForChapterError(Exception):
    """章节关联的工程不存在"""


class ReorderMismatchError(Exception):
    """重排传入的 id 集合与现有章节不匹配"""


def _count_words(text: str | None) -> int:
    """简易字数:去掉空白字符后的长度。中文字符按 1 字计。"""
    if not text:
        return 0
    return len("".join(text.split()))


def list_chapters(db: Session, project_id: int) -> list[ChapterListItem]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForChapterError(project_id)
    stmt = select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.order_index)
    rows = db.execute(stmt).scalars().all()
    return [ChapterListItem.model_validate(c) for c in rows]


def get_chapter(db: Session, chapter_id: int) -> ChapterDetail:
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)
    return ChapterDetail.model_validate(c)


def create_chapter(
    db: Session, project_id: int, payload: ChapterCreate
) -> ChapterDetail:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForChapterError(project_id)

    # order_index = max + 1
    stmt = select(Chapter.order_index).where(Chapter.project_id == project_id)
    existing = db.execute(stmt).scalars().all()
    next_order = (max(existing) + 1) if existing else 1

    c = Chapter(
        project_id=project_id,
        title=payload.title,
        order_index=next_order,
        content="",
        word_count=0,
        status="draft",
        summary=payload.summary,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return ChapterDetail.model_validate(c)


def update_chapter(
    db: Session, chapter_id: int, payload: ChapterUpdate
) -> ChapterDetail:
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return ChapterDetail.model_validate(c)


def delete_chapter(db: Session, chapter_id: int) -> None:
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)
    db.delete(c)
    db.commit()


def reorder_chapters(db: Session, project_id: int, chapter_ids: list[int]) -> list[ChapterListItem]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForChapterError(project_id)

    stmt = select(Chapter).where(Chapter.project_id == project_id)
    existing = db.execute(stmt).scalars().all()
    existing_ids = {c.id for c in existing}

    if set(chapter_ids) != existing_ids:
        raise ReorderMismatchError(
            f"传入 ids 与该工程章节不匹配: 传入={set(chapter_ids)}, 实际={existing_ids}"
        )

    by_id = {c.id: c for c in existing}

    # 先把所有 order_index 置为负值,避免 UniqueConstraint 冲突
    for c in existing:
        c.order_index = -c.order_index
    db.flush()

    for new_idx, cid in enumerate(chapter_ids, start=1):
        by_id[cid].order_index = new_idx
    db.commit()

    return list_chapters(db, project_id)


def update_word_count_after_content_change(c: Chapter) -> None:
    """供 Phase 3 调用:content 变化后更新字数。"""
    c.word_count = _count_words(c.content)


def save_content(db: Session, chapter_id: int, content: str) -> Chapter:
    """保存章节正文,顺便重算字数。返回 Chapter 实体供 API 取元信息。"""
    c = db.get(Chapter, chapter_id)
    if c is None:
        raise ChapterNotFoundError(chapter_id)
    c.content = content
    update_word_count_after_content_change(c)
    db.commit()
    db.refresh(c)
    return c
