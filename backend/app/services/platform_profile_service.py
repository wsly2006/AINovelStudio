"""平台 Profile 服务 + 启动时 seed 预制平台。

预制平台不可删除(is_preset=True),用户自建可增删改。
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.platform_profile import PlatformProfile
from app.schemas.platform_profile import (
    PlatformProfileCreate,
    PlatformProfileRead,
    PlatformProfileUpdate,
)


class PlatformProfileNotFoundError(Exception):
    pass


class PlatformProfileCodeConflictError(Exception):
    pass


class PlatformProfilePresetReadonlyError(Exception):
    """预制 profile 不可删除/不可改 code。"""


# ── 预制平台清单 ──────────────────────────────────────────
# 元数据 schema 仅作 UI 校验提示;字段实际值存在 Project 表对应列里。
# key 与 Project.{pen_name,series_name,blurb,keywords,categories} 对齐;
# 平台特有字段(如起点频道)走 categories 数组,不另开列。

_PRESETS: list[dict] = [
    {
        "code": "kdp",
        "name": "Amazon KDP",
        "region": "global",
        "formats": ["epub", "docx"],
        "chapter_strategy": "whole_book",
        "encoding": None,
        "metadata_schema": [
            {"key": "pen_name", "label": "Pen Name", "required": True, "type": "text", "max_len": 50},
            {"key": "series_name", "label": "Series", "required": False, "type": "text", "max_len": 80},
            {"key": "blurb", "label": "Description", "required": True, "type": "textarea", "max_len": 4000,
             "hint": "Amazon 商品页长简介,最多 4000 字符"},
            {"key": "keywords", "label": "Keywords", "required": True, "type": "chips", "max_count": 7,
             "hint": "KDP 上限 7 个搜索关键词"},
            {"key": "categories", "label": "Categories", "required": True, "type": "chips", "max_count": 2,
             "hint": "KDP 上架最多选 2 个 BISAC 分类"},
        ],
        "notes": (
            "- 上传方式:登录 KDP 后台 https://kdp.amazon.com\n"
            "- EPUB / docx 二选一即可,EPUB 排版更稳\n"
            "- Keywords 用英文,Categories 走 KDP 内置 BISAC"
        ),
    },
    {
        "code": "webnovel",
        "name": "Webnovel",
        "region": "global",
        "formats": ["txt", "txt_chapters", "epub"],
        "chapter_strategy": "both",
        "encoding": "utf-8",
        "metadata_schema": [
            {"key": "pen_name", "label": "Pen Name", "required": True, "type": "text", "max_len": 40},
            {"key": "series_name", "label": "Volume Name", "required": False, "type": "text", "max_len": 80},
            {"key": "blurb", "label": "Synopsis", "required": True, "type": "textarea", "max_len": 2000},
            {"key": "keywords", "label": "Tags", "required": False, "type": "chips", "max_count": 10},
            {"key": "categories", "label": "Genre", "required": True, "type": "chips", "max_count": 2,
             "hint": "Webnovel 内置 genre 分类"},
        ],
        "notes": "- 平台按章发布,推荐导出章节包逐章上传\n- 标签英文为主",
    },
    {
        "code": "royalroad",
        "name": "Royal Road",
        "region": "global",
        "formats": ["txt", "txt_chapters"],
        "chapter_strategy": "per_chapter",
        "encoding": "utf-8",
        "metadata_schema": [
            {"key": "pen_name", "label": "Author", "required": True, "type": "text", "max_len": 40},
            {"key": "blurb", "label": "Description", "required": True, "type": "textarea", "max_len": 4000,
             "hint": "支持 BBCode"},
            {"key": "keywords", "label": "Tags", "required": True, "type": "chips", "max_count": 8,
             "hint": "Royal Road 内置 tag 列表"},
        ],
        "notes": "- 章节独立上传,使用章节包模式\n- 平台社区偏 LitRPG / 升级流",
    },
    {
        "code": "wattpad",
        "name": "Wattpad",
        "region": "global",
        "formats": ["txt", "txt_chapters"],
        "chapter_strategy": "per_chapter",
        "encoding": "utf-8",
        "metadata_schema": [
            {"key": "pen_name", "label": "Author", "required": True, "type": "text", "max_len": 40},
            {"key": "blurb", "label": "Description", "required": True, "type": "textarea", "max_len": 2000},
            {"key": "keywords", "label": "Tags", "required": False, "type": "chips", "max_count": 25,
             "hint": "Wattpad 标签上限 25 个"},
            {"key": "categories", "label": "Category", "required": True, "type": "chips", "max_count": 1},
        ],
        "notes": "- 读者偏年轻向,romance / werewolf 题材占多数",
    },
    {
        "code": "qidian",
        "name": "起点中文网",
        "region": "cn",
        "formats": ["txt", "txt_chapters"],
        "chapter_strategy": "both",
        "encoding": "utf-8",
        "metadata_schema": [
            {"key": "pen_name", "label": "笔名", "required": True, "type": "text", "max_len": 30},
            {"key": "blurb", "label": "作品简介", "required": True, "type": "textarea", "max_len": 1000},
            {"key": "categories", "label": "频道 / 分类", "required": True, "type": "chips", "max_count": 3,
             "hint": "示例:[男频, 玄幻, 东方玄幻]"},
            {"key": "keywords", "label": "标签", "required": False, "type": "chips", "max_count": 5},
        ],
        "notes": "- 老平台兼容 GB18030,但当前后台已切 UTF-8",
    },
    {
        "code": "fanqie",
        "name": "番茄小说",
        "region": "cn",
        "formats": ["txt", "txt_chapters"],
        "chapter_strategy": "both",
        "encoding": "utf-8",
        "metadata_schema": [
            {"key": "pen_name", "label": "笔名", "required": True, "type": "text", "max_len": 30},
            {"key": "blurb", "label": "作品简介", "required": True, "type": "textarea", "max_len": 800},
            {"key": "categories", "label": "分类", "required": True, "type": "chips", "max_count": 2},
            {"key": "keywords", "label": "标签", "required": False, "type": "chips", "max_count": 5},
        ],
        "notes": "- 番茄推免费阅读流量,适合走完结全本",
    },
    {
        "code": "jjwxc",
        "name": "晋江文学城",
        "region": "cn",
        "formats": ["txt", "txt_chapters"],
        "chapter_strategy": "per_chapter",
        "encoding": "utf-8",
        "metadata_schema": [
            {"key": "pen_name", "label": "笔名", "required": True, "type": "text", "max_len": 30},
            {"key": "blurb", "label": "文案", "required": True, "type": "textarea", "max_len": 1000},
            {"key": "categories", "label": "分类", "required": True, "type": "chips", "max_count": 3,
             "hint": "示例:[纯爱, 现代, 都市情缘]"},
            {"key": "keywords", "label": "标签", "required": False, "type": "chips", "max_count": 6},
        ],
        "notes": "- 章节按文 ID 上传,使用章节包模式",
    },
    {
        "code": "generic",
        "name": "通用导出",
        "region": "other",
        "formats": ["json", "md", "epub", "docx", "txt"],
        "chapter_strategy": "both",
        "encoding": "utf-8",
        "metadata_schema": [],
        "notes": "- 不针对特定平台,选格式即导出,所有元数据都可选",
    },
]


def _to_dict_payload(p: PlatformProfileCreate | PlatformProfileUpdate) -> dict:
    data = p.model_dump(exclude_unset=True)
    # MetadataField 在 dump 后已是 dict
    if "metadata_schema" in data and data["metadata_schema"] is not None:
        data["metadata_schema"] = [
            f if isinstance(f, dict) else f.model_dump() for f in data["metadata_schema"]
        ]
    return data


def list_profiles(db: Session) -> list[PlatformProfileRead]:
    stmt = select(PlatformProfile).order_by(
        # 预制在前,同一组内按 region 再按 code
        PlatformProfile.is_preset.desc(),
        PlatformProfile.region,
        PlatformProfile.code,
    )
    return [PlatformProfileRead.model_validate(r) for r in db.execute(stmt).scalars().all()]


def get_profile(db: Session, profile_id: int) -> PlatformProfileRead:
    p = db.get(PlatformProfile, profile_id)
    if p is None:
        raise PlatformProfileNotFoundError(profile_id)
    return PlatformProfileRead.model_validate(p)


def get_profile_by_code(db: Session, code: str) -> PlatformProfileRead | None:
    stmt = select(PlatformProfile).where(PlatformProfile.code == code.lower())
    p = db.execute(stmt).scalar_one_or_none()
    return PlatformProfileRead.model_validate(p) if p else None


def create_profile(db: Session, payload: PlatformProfileCreate) -> PlatformProfileRead:
    data = _to_dict_payload(payload)
    p = PlatformProfile(
        code=data["code"],
        name=data["name"],
        region=data.get("region", "global"),
        is_preset=False,  # 用户自建强制 False
        formats=data.get("formats", []),
        chapter_strategy=data.get("chapter_strategy", "whole_book"),
        metadata_schema=data.get("metadata_schema", []),
        encoding=data.get("encoding"),
        notes=data.get("notes"),
    )
    db.add(p)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise PlatformProfileCodeConflictError(payload.code) from e
    db.refresh(p)
    return PlatformProfileRead.model_validate(p)


def update_profile(
    db: Session, profile_id: int, payload: PlatformProfileUpdate
) -> PlatformProfileRead:
    p = db.get(PlatformProfile, profile_id)
    if p is None:
        raise PlatformProfileNotFoundError(profile_id)
    data = _to_dict_payload(payload)
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return PlatformProfileRead.model_validate(p)


def delete_profile(db: Session, profile_id: int) -> None:
    p = db.get(PlatformProfile, profile_id)
    if p is None:
        raise PlatformProfileNotFoundError(profile_id)
    if p.is_preset:
        raise PlatformProfilePresetReadonlyError(p.code)
    db.delete(p)
    db.commit()


def seed_presets(db: Session) -> int:
    """启动时调用:对照 _PRESETS,缺失的预制 profile 插入。

    已存在(按 code)的预制:不覆盖用户的 notes 修改,但同步 schema/formats
    等结构性字段,保证后续版本升级 schema 能落地。
    """
    inserted = 0
    for tpl in _PRESETS:
        existing = db.execute(
            select(PlatformProfile).where(PlatformProfile.code == tpl["code"])
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                PlatformProfile(
                    code=tpl["code"],
                    name=tpl["name"],
                    region=tpl["region"],
                    is_preset=True,
                    formats=tpl["formats"],
                    chapter_strategy=tpl["chapter_strategy"],
                    metadata_schema=tpl["metadata_schema"],
                    encoding=tpl.get("encoding"),
                    notes=tpl.get("notes"),
                )
            )
            inserted += 1
        else:
            # 仅当仍是预制 profile 时同步结构字段;若用户曾改 is_preset(理论上不允许),不动
            if existing.is_preset:
                existing.name = tpl["name"]
                existing.region = tpl["region"]
                existing.formats = tpl["formats"]
                existing.chapter_strategy = tpl["chapter_strategy"]
                existing.metadata_schema = tpl["metadata_schema"]
                existing.encoding = tpl.get("encoding")
                # notes 不覆盖:允许预制平台被用户加私人备注而不被升级冲掉
                if existing.notes is None:
                    existing.notes = tpl.get("notes")
    if inserted or db.dirty:
        db.commit()
    return inserted
