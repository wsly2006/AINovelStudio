"""翻译术语表服务:CRUD + 从已有人物/物品/世界观批量种子。

设计要点:
- 唯一键是 (project_id, source, target_lang) —— 同一中文词在同一目标语只有一条
- seed 时 source 取中文 name + aliases 展开,target 留空让作者填或后续 AI 补
- locked=True 的行 seed 时永远不动
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.character import Character
from app.models.item import Item
from app.models.project import Project
from app.models.translation_glossary import TranslationGlossary
from app.models.world_entity import WorldEntity
from app.schemas.translation_glossary import (
    GlossaryCreate,
    GlossaryRead,
    GlossarySeedResult,
    GlossaryUpdate,
)


class GlossaryNotFoundError(Exception):
    pass


class GlossaryConflictError(Exception):
    """同一 (project_id, source, target_lang) 已存在"""


class ProjectNotFoundForGlossaryError(Exception):
    pass


def list_entries(
    db: Session,
    project_id: int,
    *,
    target_lang: str | None = None,
    entry_type: str | None = None,
) -> list[GlossaryRead]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForGlossaryError(project_id)
    stmt = select(TranslationGlossary).where(
        TranslationGlossary.project_id == project_id
    )
    if target_lang:
        stmt = stmt.where(TranslationGlossary.target_lang == target_lang)
    if entry_type:
        stmt = stmt.where(TranslationGlossary.entry_type == entry_type)
    stmt = stmt.order_by(
        TranslationGlossary.entry_type,
        TranslationGlossary.source,
    )
    rows = db.execute(stmt).scalars().all()
    return [GlossaryRead.model_validate(r) for r in rows]


def get_entry(db: Session, entry_id: int) -> GlossaryRead:
    e = db.get(TranslationGlossary, entry_id)
    if e is None:
        raise GlossaryNotFoundError(entry_id)
    return GlossaryRead.model_validate(e)


def create_entry(
    db: Session, project_id: int, payload: GlossaryCreate
) -> GlossaryRead:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForGlossaryError(project_id)

    e = TranslationGlossary(
        project_id=project_id,
        source=payload.source,
        target=payload.target,
        target_lang=payload.target_lang,
        entry_type=payload.entry_type,
        notes=payload.notes,
        locked=payload.locked,
    )
    db.add(e)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise GlossaryConflictError(
            f"({payload.source}, {payload.target_lang}) 已存在"
        ) from exc
    db.refresh(e)
    return GlossaryRead.model_validate(e)


def update_entry(
    db: Session, entry_id: int, payload: GlossaryUpdate
) -> GlossaryRead:
    e = db.get(TranslationGlossary, entry_id)
    if e is None:
        raise GlossaryNotFoundError(entry_id)

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(e, k, v)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise GlossaryConflictError(
            f"({data.get('source', e.source)}, {data.get('target_lang', e.target_lang)}) 已存在"
        ) from exc
    db.refresh(e)
    return GlossaryRead.model_validate(e)


def delete_entry(db: Session, entry_id: int) -> None:
    e = db.get(TranslationGlossary, entry_id)
    if e is None:
        raise GlossaryNotFoundError(entry_id)
    db.delete(e)
    db.commit()


# ── seed:从工程现有人物/物品/世界观批量灌入术语表 ──────────────


# 把 world_entity.kind 映射到 glossary.entry_type
_WORLD_KIND_TO_TYPE = {
    "location": "place",
    "organization": "org",
    "concept": "term",
}


def bulk_seed_from_project(
    db: Session,
    project_id: int,
    *,
    target_lang: str = "en-US",
    overwrite: bool = False,
) -> GlossarySeedResult:
    """从工程的人物/物品/世界观把名词批量塞进术语表。

    - source = 中文 name(以及 aliases 里的每一项)
    - target 留空,让作者后续填或 AI 补
    - 已存在 (project_id, source, target_lang) 的:
        - locked=True → 永远跳过
        - locked=False & overwrite=False → 跳过
        - locked=False & overwrite=True → 把 entry_type 重新对齐(target/notes 不动)
    """
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForGlossaryError(project_id)

    # 先把已存在的查出来,后面用 (source, target_lang) 索引
    existing_stmt = select(TranslationGlossary).where(
        TranslationGlossary.project_id == project_id,
        TranslationGlossary.target_lang == target_lang,
    )
    existing_rows = db.execute(existing_stmt).scalars().all()
    existing_index: dict[tuple[str, str], TranslationGlossary] = {
        (r.source, r.target_lang): r for r in existing_rows
    }

    # 收集候选 (source, entry_type) 对;一个 source 多次出现取第一个 type
    candidates: list[tuple[str, str]] = []
    seen_sources: set[str] = set()

    def _push(source: str, etype: str) -> None:
        s = (source or "").strip()
        if not s or s in seen_sources:
            return
        seen_sources.add(s)
        candidates.append((s, etype))

    # characters
    char_stmt = select(Character).where(Character.project_id == project_id)
    for c in db.execute(char_stmt).scalars().all():
        _push(c.name, "person")
        for a in c.aliases or []:
            _push(a, "person")

    # items
    item_stmt = select(Item).where(Item.project_id == project_id)
    for it in db.execute(item_stmt).scalars().all():
        _push(it.name, "item")
        for a in it.aliases or []:
            _push(a, "item")

    # world entities (location / organization / concept)
    we_stmt = select(WorldEntity).where(WorldEntity.project_id == project_id)
    for w in db.execute(we_stmt).scalars().all():
        etype = _WORLD_KIND_TO_TYPE.get(w.kind, "other")
        _push(w.name, etype)
        for a in w.aliases or []:
            _push(a, etype)

    created = 0
    skipped = 0
    updated = 0
    for source, etype in candidates:
        existing = existing_index.get((source, target_lang))
        if existing is not None:
            if existing.locked or not overwrite:
                skipped += 1
                continue
            # 仅在分类不一致时重写,避免无意义 update
            if existing.entry_type != etype:
                existing.entry_type = etype
                updated += 1
            else:
                skipped += 1
            continue

        e = TranslationGlossary(
            project_id=project_id,
            source=source,
            target="",
            target_lang=target_lang,
            entry_type=etype,
            locked=False,
        )
        db.add(e)
        created += 1

    db.commit()
    return GlossarySeedResult(created=created, skipped=skipped, updated=updated)


__all__ = [
    "GlossaryConflictError",
    "GlossaryNotFoundError",
    "ProjectNotFoundForGlossaryError",
    "bulk_seed_from_project",
    "create_entry",
    "delete_entry",
    "get_entry",
    "list_entries",
    "update_entry",
]
