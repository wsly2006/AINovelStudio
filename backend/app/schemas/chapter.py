from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ChapterStatus = Literal["draft", "outlined", "writing", "done"]


class ChapterBeat(BaseModel):
    """章节节拍:写正文前的「本章会发生什么」一拍。"""

    title: str = Field(min_length=1, max_length=80)
    detail: str | None = Field(default=None, max_length=600)
    # 推进的主线名(冗余存 title,避免改名/删主线后悬挂)
    thread_titles: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title 不能为空")
        return v

    @field_validator("detail")
    @classmethod
    def _strip_detail(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("thread_titles")
    @classmethod
    def _normalize_threads(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for t in v or []:
            t = (t or "").strip()
            if not t or t in seen:
                continue
            if len(t) > 120:
                t = t[:120]
            seen.add(t)
            out.append(t)
        return out


BeatAlignmentStatus = Literal["covered", "partial", "missing"]


class BeatAlignmentItem(BaseModel):
    """单个节拍的对账结果。"""

    beat_index: int = Field(ge=0)
    status: BeatAlignmentStatus
    # AI 认为对应的事件 ids(可空,missing 时通常为空)
    matched_event_ids: list[int] = Field(default_factory=list)
    # 30-100 字简评:为什么 partial / missing,或哪几个事件支撑了 covered
    note: str | None = Field(default=None, max_length=400)


class ChapterCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    summary: str | None = Field(default=None, max_length=4000)

    @field_validator("title", mode="before")
    @classmethod
    def _strip(cls, v) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @field_validator("summary")
    @classmethod
    def _strip_summary(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    status: ChapterStatus | None = None
    # 节拍:传 [] 表示清空,传 null/不传 表示不动
    beats: list[ChapterBeat] | None = Field(default=None, max_length=20)

    @field_validator("title", mode="before")
    @classmethod
    def _strip_title(cls, v) -> str | None:
        if v is None:
            return None
        return str(v).strip()


class ChapterListItem(BaseModel):
    """列表用 schema,不含 content。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    order_index: int
    summary: str | None
    status: ChapterStatus
    word_count: int
    created_at: datetime
    updated_at: datetime
    # 最近一次 AI 评分的综合分,未评过为 None。仅在 list 接口里填,detail 不填。
    latest_overall_score: int | None = None
    # 最近一次 AI 文风检查命中的段落数,未检查过为 None;0 表示已检查且无命中。
    latest_style_issue_count: int | None = None


class ChapterDetail(ChapterListItem):
    """详情,含 content + beats,Phase 3 编辑器使用。"""

    content: str
    beats: list[ChapterBeat] | None = None
    beats_alignment: list[BeatAlignmentItem] | None = None


class ChapterReorder(BaseModel):
    chapter_ids: list[int] = Field(min_length=1)


class ChapterContentUpdate(BaseModel):
    content: str = Field(default="", max_length=2_000_000)


class ChapterContentSaved(BaseModel):
    """PUT content 的返回:仅元信息,避免回传同一份正文。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    word_count: int
    updated_at: datetime


class SuggestBeatsRequest(BaseModel):
    """AI 草拟节拍的入参。"""

    target_word_count: int = Field(default=4000, ge=500, le=20000)
    extra_instruction: str | None = Field(default=None, max_length=2000)


class SuggestBeatsResponse(BaseModel):
    beats: list[ChapterBeat]


class BeatsAlignmentResponse(BaseModel):
    """对账接口返回:每个节拍的覆盖状态 + 整体计数。"""

    items: list[BeatAlignmentItem]
    covered: int
    partial: int
    missing: int


# ── 大纲模式相关 ───────────────────────────────────────

class OutlineDraft(BaseModel):
    """批量草拟接口返回的单个章节草稿,不落库。"""

    title: str = Field(default="", max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    beats: list[ChapterBeat] = Field(default_factory=list, max_length=20)


class OutlineBatchSuggestRequest(BaseModel):
    """批量草拟入参。"""

    count: int = Field(default=10, ge=1, le=30)
    # 起始位置:留空 = 末尾追加;给值 = 从该 order_index 开始(必须存在)
    start_order_index: int | None = Field(default=None, ge=1)
    extra_instruction: str | None = Field(default=None, max_length=2000)
    target_word_count: int = Field(default=4000, ge=500, le=20000)


class OutlineBatchSuggestResponse(BaseModel):
    drafts: list[OutlineDraft]


class OutlineBatchCreateRequest(BaseModel):
    """确认落库:把草稿数组追加为新章节(末尾追加,status='outlined')。"""

    drafts: list[OutlineDraft] = Field(min_length=1, max_length=30)


class OutlineBatchCreateResponse(BaseModel):
    chapters: list[ChapterListItem]


OutlineAlignmentStatus = Literal["covered", "partial", "missing"]


class OutlineBeatAlignment(BaseModel):
    beat_index: int = Field(ge=0)
    status: OutlineAlignmentStatus
    note: str | None = Field(default=None, max_length=400)


class OutlineAlignmentResult(BaseModel):
    """章节正文与大纲对账结果。"""

    summary_status: OutlineAlignmentStatus
    summary_note: str | None = Field(default=None, max_length=400)
    beats: list[OutlineBeatAlignment]
    overall_note: str | None = Field(default=None, max_length=600)
    # 计数(从 beats + summary 派生,前端徽章用)
    covered: int
    partial: int
    missing: int
