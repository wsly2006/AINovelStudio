from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate


class ProjectNameConflictError(Exception):
    """工程名重复"""


class ProjectNotFoundError(Exception):
    """工程不存在"""


def _build_read(
    p: Project,
    chapter_count: int,
    word_count: int,
    last_edited_at: datetime,
) -> ProjectRead:
    return ProjectRead.model_validate(
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "channel": p.channel,
            "genre": p.genre,
            "tags": list(p.tags or []),
            "cover_color": p.cover_color,
            "progression_enabled": p.progression_enabled,
            "words_per_chapter": p.words_per_chapter,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "chapter_count": chapter_count,
            "word_count": word_count,
            "last_edited_at": last_edited_at,
        }
    )


def _stats_for(db: Session, project_id: int, project_updated_at: datetime) -> tuple[int, int, datetime]:
    """单个工程的派生字段。"""
    stmt = select(
        func.count(Chapter.id),
        func.coalesce(func.sum(Chapter.word_count), 0),
        func.max(Chapter.updated_at),
    ).where(Chapter.project_id == project_id)
    cnt, words, latest = db.execute(stmt).one()
    return int(cnt), int(words), (latest or project_updated_at)


def list_projects(db: Session) -> list[ProjectRead]:
    # 单条 SQL group by 取所有工程的统计
    stats_stmt = (
        select(
            Chapter.project_id,
            func.count(Chapter.id).label("cnt"),
            func.coalesce(func.sum(Chapter.word_count), 0).label("words"),
            func.max(Chapter.updated_at).label("latest"),
        )
        .group_by(Chapter.project_id)
    )
    stats_map = {
        row.project_id: (row.cnt, int(row.words or 0), row.latest)
        for row in db.execute(stats_stmt).all()
    }

    proj_stmt = select(Project)
    projects = db.execute(proj_stmt).scalars().all()

    items = []
    for p in projects:
        cnt, words, latest = stats_map.get(p.id, (0, 0, None))
        items.append(_build_read(p, cnt, words, latest or p.updated_at))

    # 按 last_edited_at 倒序(最近编辑的在前)
    items.sort(key=lambda r: r.last_edited_at, reverse=True)
    return items


def get_project(db: Session, project_id: int) -> ProjectRead:
    p = db.get(Project, project_id)
    if p is None:
        raise ProjectNotFoundError(project_id)
    cnt, words, latest = _stats_for(db, p.id, p.updated_at)
    return _build_read(p, cnt, words, latest)


def create_project(db: Session, payload: ProjectCreate) -> ProjectRead:
    # 进阶体系判定优先级:
    # 1. progression_system 显式传入(空串=用户选了「不启用」)
    # 2. progression_enabled=True
    # 3. 按 genre 自动判定
    # 4. 按 tags 自动判定(如「异能」「末世」标签)
    from app.services import ladder_service

    explicit_system = payload.progression_system
    if explicit_system is not None:
        seed_key: str | None = explicit_system or None
        progression = bool(seed_key) or payload.progression_enabled
    else:
        if ladder_service.should_enable_progression(payload.genre):
            seed_key = payload.genre
        else:
            seed_key = ladder_service.system_for_tags(payload.tags)
        progression = payload.progression_enabled or seed_key is not None

    p = Project(
        name=payload.name,
        description=payload.description,
        channel=payload.channel,
        genre=payload.genre,
        tags=list(payload.tags or []),
        cover_color=payload.cover_color,
        progression_enabled=progression,
        words_per_chapter=payload.words_per_chapter,
    )
    db.add(p)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ProjectNameConflictError(payload.name) from e
    db.refresh(p)

    if seed_key:
        ladder_service.seed_defaults_for_genre(db, p.id, seed_key)

    return _build_read(p, 0, 0, p.updated_at)


def update_project(db: Session, project_id: int, payload: ProjectUpdate) -> ProjectRead:
    p = db.get(Project, project_id)
    if p is None:
        raise ProjectNotFoundError(project_id)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(p, k, v)

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ProjectNameConflictError(data.get("name", "")) from e
    db.refresh(p)
    cnt, words, latest = _stats_for(db, p.id, p.updated_at)
    return _build_read(p, cnt, words, latest)


def delete_project(db: Session, project_id: int) -> None:
    p = db.get(Project, project_id)
    if p is None:
        raise ProjectNotFoundError(project_id)
    db.delete(p)
    db.commit()
