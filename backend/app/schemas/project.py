from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    # 总纲:长篇大纲,包含结局走向。注入每次 AI 生成的 prompt。
    synopsis: str | None = Field(default=None, max_length=20000)
    # 频道:male/female/danmei/yuri/general,可空
    channel: str | None = Field(default=None, max_length=20)
    genre: str | None = Field(default=None, max_length=40)
    # 标签:多选 tag key,如 ["apocalypse", "rebirth", "esper"]
    tags: list[str] = Field(default_factory=list)
    cover_color: str | None = Field(default=None, max_length=16)
    progression_enabled: bool = False
    # 每章目标字数:决定 AI 一键开书时章节数 = 总字数 / 每章字数,
    # 也作为「生成本章」抽屉的默认目标字数
    words_per_chapter: int = Field(default=4000, ge=500, le=20000)

    # ── 发布元数据(P1) ─────────────────────────────────────
    pen_name: str | None = Field(default=None, max_length=80)
    series_name: str | None = Field(default=None, max_length=120)
    series_index: int | None = Field(default=None, ge=1, le=999)
    blurb: str | None = Field(default=None, max_length=8000)
    keywords: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    target_platform_codes: list[str] = Field(default_factory=list)

    # ── 翻译(P0-M5) ─────────────────────────────────────
    # 翻译风格指令,翻译 prompt 直接注入,与术语表同级硬约束
    translation_style_guide: str | None = Field(default=None, max_length=8000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        return v

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, v: list[str]) -> list[str]:
        # 去空、去重、保留首次出现顺序、限长
        seen: set[str] = set()
        out: list[str] = []
        for t in v or []:
            t = (t or "").strip()
            if not t or t in seen:
                continue
            if len(t) > 30:
                t = t[:30]
            seen.add(t)
            out.append(t)
        return out[:20]


class ProjectCreate(ProjectBase):
    # 进阶体系模板 key:None=按 genre/tags 自动判定;""=显式不启用;
    # 否则用该 key 从模板播种(如 "xianxia"/"wuxia"/"fantasy"/"eastern_fantasy"/"esper")
    progression_system: str | None = Field(default=None, max_length=40)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    synopsis: str | None = Field(default=None, max_length=20000)
    channel: str | None = Field(default=None, max_length=20)
    genre: str | None = Field(default=None, max_length=40)
    tags: list[str] | None = None
    cover_color: str | None = Field(default=None, max_length=16)
    progression_enabled: bool | None = None
    words_per_chapter: int | None = Field(default=None, ge=500, le=20000)

    # ── 发布元数据(P1) ─────────────────────────────────────
    pen_name: str | None = Field(default=None, max_length=80)
    series_name: str | None = Field(default=None, max_length=120)
    series_index: int | None = Field(default=None, ge=1, le=999)
    blurb: str | None = Field(default=None, max_length=8000)
    keywords: list[str] | None = None
    categories: list[str] | None = None
    target_platform_codes: list[str] | None = None

    # ── 翻译(P0-M5) ─────────────────────────────────────
    translation_style_guide: str | None = Field(default=None, max_length=8000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name 不能为空")
        return v


class ProjectRead(ProjectBase):
    """列表 / 详情共用。派生字段在 service 层填充。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime

    # 派生字段(由 service 注入,Phase 1 暂时为 0 / updated_at)
    chapter_count: int = 0
    word_count: int = 0
    last_edited_at: datetime
