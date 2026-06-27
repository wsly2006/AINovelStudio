"""作者声音档案 schema。

写入只走 PUT(upsert),所以 *Upsert* 这一个就够了。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuthorVoiceProfileUpsert(BaseModel):
    quirks: list[str] = Field(default_factory=list)
    style_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("quirks")
    @classmethod
    def _clean_quirks(cls, v: list[str]) -> list[str]:
        # 单条限 200 字,空白条目丢掉,最多保留 30 条避免 prompt 爆炸
        out: list[str] = []
        for q in v or []:
            s = (q or "").strip()
            if s:
                out.append(s[:200])
        return out[:30]


class AuthorVoiceProfileRead(AuthorVoiceProfileUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime
