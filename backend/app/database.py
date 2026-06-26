from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATA_DIR, settings

DATA_DIR.mkdir(parents=True, exist_ok=True)

# SQLite 在多线程下需要 check_same_thread=False
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# SQLite 默认不开外键约束,这里强制开启,让 ON DELETE CASCADE 生效
@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()



class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _import_all_models() -> None:
    """把所有 ORM 模型 import 一遍,触发 SQLAlchemy 注册。

    抽出来是因为:
    - init_db() 主进程要它(create_all 之前必须把所有 Mapper 注册好)
    - MCP server 进程也要它(共用同一份 SessionLocal,但不跑迁移)
    单一来源避免两边漏改。
    """
    from app.models import ai_call_log as _ai_call_log  # noqa: F401
    from app.models import ai_conversation as _ai_conversation  # noqa: F401
    from app.models import chapter as _chapter  # noqa: F401
    from app.models import chapter_score as _chapter_score  # noqa: F401
    from app.models import chapter_style_check as _chapter_style_check  # noqa: F401
    from app.models import chapter_version as _chapter_version  # noqa: F401
    from app.models import character as _character  # noqa: F401
    from app.models import consistency_issue as _consistency_issue  # noqa: F401
    from app.models import item as _item  # noqa: F401
    from app.models import ladder as _ladder  # noqa: F401
    from app.models import platform_profile as _platform_profile  # noqa: F401
    from app.models import plot_event as _plot_event  # noqa: F401
    from app.models import plot_thread as _plot_thread  # noqa: F401
    from app.models import project as _project  # noqa: F401
    from app.models import prompt_template as _prompt_template  # noqa: F401
    from app.models import relation as _relation  # noqa: F401
    from app.models import settings as _settings  # noqa: F401
    from app.models import state_event as _state_event  # noqa: F401
    from app.models import task as _task  # noqa: F401
    from app.models import translation_glossary as _translation_glossary  # noqa: F401
    from app.models import world_entity as _world_entity  # noqa: F401


def init_db() -> None:
    # 首版用 create_all 起表;Phase 2 加 Chapter 时再切到 Alembic
    _import_all_models()

    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()
    _migrate_world_items_to_items_table()
    _seed_platform_profiles()


# create_all() 不会改老表的结构,这里手动补几个新列。
# 这是过渡方案,等切到 Alembic 之前先这么用。
_NEW_COLUMNS: list[tuple[str, str, str]] = [
    # (table, column, ddl-tail) -- ddl-tail 是 ALTER TABLE 语句中列定义部分
    ("projects", "channel", "VARCHAR(20)"),
    ("projects", "tags", "JSON NOT NULL DEFAULT '[]'"),
    ("projects", "words_per_chapter", "INTEGER NOT NULL DEFAULT 4000"),
    ("projects", "synopsis", "TEXT"),
    # P1 发布元数据
    ("projects", "pen_name", "VARCHAR(80)"),
    ("projects", "series_name", "VARCHAR(120)"),
    ("projects", "series_index", "INTEGER"),
    ("projects", "blurb", "TEXT"),
    ("projects", "keywords", "JSON NOT NULL DEFAULT '[]'"),
    ("projects", "categories", "JSON NOT NULL DEFAULT '[]'"),
    ("projects", "target_platform_codes", "JSON NOT NULL DEFAULT '[]'"),
    ("chapters", "beats", "JSON"),
    ("chapters", "beats_alignment", "JSON"),
    ("chapter_versions", "lang", "VARCHAR(8) NOT NULL DEFAULT 'zh-CN'"),
    ("projects", "translation_style_guide", "TEXT"),
    ("plot_events", "thread_id", "INTEGER REFERENCES plot_threads(id) ON DELETE SET NULL"),
    # 审稿模型(可选,留空回落写作模型)
    ("ai_settings", "review_provider", "VARCHAR(20)"),
    ("ai_settings", "review_model", "VARCHAR(120)"),
    ("ai_settings", "review_base_url", "VARCHAR(255)"),
    ("ai_settings", "review_api_key", "TEXT"),
    ("ai_settings", "review_temperature", "FLOAT"),
    ("ai_settings", "review_max_tokens", "INTEGER"),
]


def _apply_lightweight_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        for table, column, ddl in _NEW_COLUMNS:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {r[1] for r in rows}
            if not existing:
                # 表本身不存在(新库) → create_all 已经按最新模型建好,跳过
                continue
            if column in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    # create_all 在迁移之前跑,那时 lang 列还不存在,带 lang 的索引建不出来;
    # 这里在 ALTER 完成后补建,旧库才能拿到一致的索引。
    _create_post_migration_indexes()


_POST_MIGRATION_INDEXES: list[tuple[str, str, str]] = [
    # (index_name, table, columns)
    (
        "ix_chapter_versions_chapter_lang_created",
        "chapter_versions",
        "chapter_id, lang, created_at",
    ),
]


def _create_post_migration_indexes() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        for name, table, cols in _POST_MIGRATION_INDEXES:
            # 表不存在时跳过(新库已经由 create_all 处理过,不会走到这里)
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            if not rows:
                continue
            conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({cols})")
            )


def _seed_platform_profiles() -> None:
    """启动时塞入预制平台 profile,已存在的同步结构字段。"""
    from app.services.platform_profile_service import seed_presets

    db = SessionLocal()
    try:
        seed_presets(db)
    finally:
        db.close()


def _migrate_world_items_to_items_table() -> None:
    """把 world_entities 中 kind='item' 的旧数据搬到 items 表。

    一次性迁移:搬完即从 world_entities 删除,避免两边都有同一条记录。
    items 表里同一 (project_id, name) 已存在的就跳过,不会重复插入。
    """
    if not settings.database_url.startswith("sqlite"):
        return
    from sqlalchemy import text

    with engine.begin() as conn:
        # items 表必须已存在(由 create_all 建好);否则说明本次启动跳过了建表
        rows = conn.execute(text("PRAGMA table_info(items)")).fetchall()
        if not rows:
            return
        rows = conn.execute(text("PRAGMA table_info(world_entities)")).fetchall()
        if not rows:
            return

        legacy = conn.execute(
            text(
                "SELECT id, project_id, name, aliases, summary, description, "
                "tags, first_seen_chapter_id, created_at, updated_at "
                "FROM world_entities WHERE kind = 'item'"
            )
        ).fetchall()
        if not legacy:
            return

        for row in legacy:
            existing = conn.execute(
                text(
                    "SELECT id FROM items WHERE project_id = :pid AND name = :name"
                ),
                {"pid": row.project_id, "name": row.name},
            ).first()
            if existing is None:
                # 保留原 world_entities.id 作为 items.id,
                # state_events.payload 里的 item_id 引用还能命中
                conn.execute(
                    text(
                        "INSERT INTO items "
                        "(id, project_id, name, aliases, summary, description, tags, "
                        "first_seen_chapter_id, created_at, updated_at) "
                        "VALUES (:id, :pid, :name, :aliases, :summary, :desc, :tags, "
                        ":fsc, :created, :updated)"
                    ),
                    {
                        "id": row.id,
                        "pid": row.project_id,
                        "name": row.name,
                        "aliases": row.aliases,
                        "summary": row.summary,
                        "desc": row.description,
                        "tags": row.tags,
                        "fsc": row.first_seen_chapter_id,
                        "created": row.created_at,
                        "updated": row.updated_at,
                    },
                )
            conn.execute(
                text("DELETE FROM world_entities WHERE id = :id"),
                {"id": row.id},
            )
