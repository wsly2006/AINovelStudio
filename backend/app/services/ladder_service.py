"""阶梯服务 + 按 genre 推荐默认阶梯。

设计原则:工具不强加体系,只提供模板。新建工程后,
若 genre 匹配预设,会顺手生成默认阶梯,用户可随后调整或删除。
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.ladder import Ladder
from app.models.project import Project
from app.schemas.ladder import LadderCreate, LadderRead, LadderUpdate

# genre key → 默认阶梯模板列表
# key 与 zh-CN.js 的 genre.* 一致
DEFAULT_LADDERS: dict[str, list[dict]] = {
    "xianxia": [
        {
            "name": "修仙阶梯",
            "description": "传统修真小说常用的境界划分",
            "tiers": [
                "练气期", "筑基期", "金丹期", "元婴期", "化神期",
                "炼虚期", "合体期", "大乘期", "渡劫期", "仙人",
            ],
        },
    ],
    "fantasy": [
        {
            "name": "玄幻境界",
            "description": "通用玄幻力量等级",
            "tiers": [
                "凡人", "锻体", "通玄", "灵动", "元胎", "天罡",
                "归元", "洞虚", "合道", "无上",
            ],
        },
    ],
    "wuxia": [
        {
            "name": "武道境界",
            "description": "武侠常用功力等级",
            "tiers": [
                "三流", "二流", "一流", "顶尖一流", "先天",
                "宗师", "大宗师", "陆地神仙",
            ],
        },
    ],
    "eastern_fantasy": [
        {
            "name": "奇幻位阶",
            "description": "东方奇幻常见力量序列",
            "tiers": [
                "学徒", "见习", "正式", "高级", "大师",
                "宗师", "传奇", "半神", "神祇",
            ],
        },
    ],
    "esper": [
        {
            "name": "异能等级",
            "description": "末世 / 异能 / 进化流常用的能力分级",
            "tiers": [
                "普通人", "一阶", "二阶", "三阶", "四阶",
                "五阶", "六阶", "七阶", "八阶", "九阶", "神级",
            ],
        },
    ],
    "scifi": [
        {
            "name": "技术等级",
            "description": "宇宙文明科技分级(参考卡尔达肖夫)",
            "tiers": [
                "前工业", "工业", "信息", "行星级", "恒星级",
                "星系级", "宇宙级",
            ],
        },
    ],
    "game": [
        {
            "name": "玩家等级",
            "description": "游戏小说常见等级",
            "tiers": [f"Lv.{n*10}" for n in range(1, 11)],
        },
    ],
}


# 自动启用 progression 的 genre 集合
PROGRESSION_GENRES = set(DEFAULT_LADDERS.keys())

# 触发进阶体系的标签 → 推荐播种 key
# 含这些 tag 的工程,即便 genre 不在 PROGRESSION_GENRES,也会弹出体系选择
TAG_TO_SYSTEM: dict[str, str] = {
    "esper": "esper",          # 异能
    "apocalypse": "esper",     # 末世(常配异能)
    "evolution": "esper",      # 进化流
    "cultivation": "xianxia",  # 修真
    "martial": "wuxia",        # 武道
    "mecha": "esper",          # 机甲(借用阶等级)
}


def should_enable_progression(genre: str | None) -> bool:
    return bool(genre) and genre in PROGRESSION_GENRES


def system_for_tags(tags: list[str] | None) -> str | None:
    """tags 中第一个匹配到的进阶体系 key,匹配不到返回 None。"""
    for t in tags or []:
        key = TAG_TO_SYSTEM.get(t)
        if key:
            return key
    return None


class LadderNotFoundError(Exception):
    pass


class LadderNameConflictError(Exception):
    pass


class ProjectNotFoundForLadderError(Exception):
    pass


def list_ladders(db: Session, project_id: int) -> list[LadderRead]:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForLadderError(project_id)
    stmt = select(Ladder).where(Ladder.project_id == project_id).order_by(Ladder.created_at)
    return [LadderRead.model_validate(l_) for l_ in db.execute(stmt).scalars().all()]


def get_ladder(db: Session, ladder_id: int) -> LadderRead:
    l_ = db.get(Ladder, ladder_id)
    if l_ is None:
        raise LadderNotFoundError(ladder_id)
    return LadderRead.model_validate(l_)


def create_ladder(db: Session, project_id: int, payload: LadderCreate) -> LadderRead:
    if db.get(Project, project_id) is None:
        raise ProjectNotFoundForLadderError(project_id)
    l_ = Ladder(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        tiers=payload.tiers,
    )
    db.add(l_)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise LadderNameConflictError(payload.name) from e
    db.refresh(l_)
    return LadderRead.model_validate(l_)


def update_ladder(db: Session, ladder_id: int, payload: LadderUpdate) -> LadderRead:
    l_ = db.get(Ladder, ladder_id)
    if l_ is None:
        raise LadderNotFoundError(ladder_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(l_, k, v)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise LadderNameConflictError(data.get("name", "")) from e
    db.refresh(l_)
    return LadderRead.model_validate(l_)


def delete_ladder(db: Session, ladder_id: int) -> None:
    l_ = db.get(Ladder, ladder_id)
    if l_ is None:
        raise LadderNotFoundError(ladder_id)
    db.delete(l_)
    db.commit()


def seed_defaults_for_genre(db: Session, project_id: int, genre: str | None) -> int:
    """新建工程后调用:若 genre 匹配,创建默认阶梯。返回新建数量。"""
    if not should_enable_progression(genre):
        return 0
    templates = DEFAULT_LADDERS.get(genre, [])
    count = 0
    for tpl in templates:
        l_ = Ladder(
            project_id=project_id,
            name=tpl["name"],
            description=tpl.get("description"),
            tiers=list(tpl.get("tiers") or []),
        )
        db.add(l_)
        count += 1
    if count:
        db.commit()
    return count
