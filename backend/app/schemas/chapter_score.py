from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChapterScoreItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    writing: int
    plot: int
    characters: int
    overall: int
    feedback: str
    model: str | None
    word_count: int
    created_at: datetime
