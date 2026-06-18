"""章节 AI 评分服务。

调 LiteLLM 让模型按 4 维度打分,返回 JSON,落库后留作历史。
解析失败时不留废数据,直接抛错给上层 API,前端提示用户重试。
"""

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.ai import prompts
from app.ai.runtime import resolve as resolve_ai_runtime
from app.models.chapter import Chapter
from app.models.chapter_score import ChapterScore
from app.schemas.chapter_score import ChapterScoreItem
from app.services.chapter_service import ChapterNotFoundError

DIM_KEYS = ("writing", "plot", "characters", "overall")


class ChapterScoreParseError(Exception):
    """AI 输出无法解析为评分 JSON"""


def _extract_json(text: str) -> dict[str, Any]:
    """从模型输出里抠出 JSON 对象。

    模型偶尔会带 markdown 代码块或解释文字,这里退一步用花括号匹配兜底。
    """
    if not text:
        raise ChapterScoreParseError("模型返回为空")
    # 先试一次裸 JSON
    try:
        return json.loads(text)
    except Exception:
        pass
    # 抠出第一个 {...} 块
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ChapterScoreParseError(f"未找到 JSON 对象: {text[:200]}")
    try:
        return json.loads(m.group(0))
    except Exception as e:
        raise ChapterScoreParseError(f"JSON 解析失败: {e}") from e


def _coerce_score(raw: Any, key: str) -> int:
    if isinstance(raw, bool):
        # bool 是 int 的子类,得排掉
        raise ChapterScoreParseError(f"{key} 不应为 bool")
    if isinstance(raw, (int, float)):
        n = int(round(raw))
    else:
        try:
            n = int(round(float(str(raw))))
        except Exception as e:
            raise ChapterScoreParseError(f"{key} 不是数字: {raw!r}") from e
    if not 1 <= n <= 10:
        # 越界就夹回 [1,10],而不是直接报错——避免一次评分白跑
        n = max(1, min(10, n))
    return n


async def score_chapter(db: Session, chapter_id: int) -> ChapterScoreItem:
    chapter = db.get(Chapter, chapter_id)
    if chapter is None:
        raise ChapterNotFoundError(chapter_id)

    messages = prompts.build_score_messages(chapter.project, chapter, db=db)
    raw = await ai_client.complete(
        db,
        messages,
        scene="chapter.score",
        max_tokens=1500,
        project_id=chapter.project_id,
    )
    data = _extract_json(raw)

    scores = {k: _coerce_score(data.get(k), k) for k in DIM_KEYS}
    feedback = str(data.get("feedback") or "").strip()

    cfg = resolve_ai_runtime(db)
    row = ChapterScore(
        chapter_id=chapter.id,
        writing=scores["writing"],
        plot=scores["plot"],
        characters=scores["characters"],
        overall=scores["overall"],
        feedback=feedback,
        model=cfg.model,
        word_count=chapter.word_count or 0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ChapterScoreItem.model_validate(row)


def list_scores(db: Session, chapter_id: int) -> list[ChapterScoreItem]:
    if db.get(Chapter, chapter_id) is None:
        raise ChapterNotFoundError(chapter_id)
    stmt = (
        select(ChapterScore)
        .where(ChapterScore.chapter_id == chapter_id)
        .order_by(ChapterScore.created_at.desc(), ChapterScore.id.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return [ChapterScoreItem.model_validate(r) for r in rows]


def delete_score(db: Session, score_id: int) -> ChapterScore:
    row = db.get(ChapterScore, score_id)
    if row is None:
        raise ChapterScoreNotFoundError(score_id)
    db.delete(row)
    db.commit()
    return row


class ChapterScoreNotFoundError(Exception):
    """评分记录不存在"""
