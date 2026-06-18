"""Token 用量统计查询。

按指定日期(本地时间 0:00 - 24:00)聚合 ai_call_logs。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.ai_call_log import AICallLog
from app.schemas.stats import (
    TokenBucket,
    TokenCallItem,
    TokenStatsResponse,
    TokenSummary,
)

_RECENT_LIMIT = 50


def _day_range(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min)
    end = start + timedelta(days=1)
    return start, end


def _coalesce(v) -> int:
    return int(v) if v is not None else 0


def get_token_stats(db: Session, d: date) -> TokenStatsResponse:
    start, end = _day_range(d)
    base = (AICallLog.created_at >= start) & (AICallLog.created_at < end)

    # 总览
    summary_row = db.execute(
        select(
            func.count(AICallLog.id),
            func.sum(AICallLog.prompt_tokens),
            func.sum(AICallLog.completion_tokens),
            func.sum(AICallLog.total_tokens),
            func.avg(AICallLog.duration_ms),
            func.sum(case((AICallLog.status == "error", 1), else_=0)),
        ).where(base)
    ).one()
    call_count = _coalesce(summary_row[0])
    summary = TokenSummary(
        date=d.isoformat(),
        call_count=call_count,
        error_count=_coalesce(summary_row[5]),
        prompt_tokens=_coalesce(summary_row[1]),
        completion_tokens=_coalesce(summary_row[2]),
        total_tokens=_coalesce(summary_row[3]),
        avg_duration_ms=int(summary_row[4]) if summary_row[4] is not None else 0,
    )

    def _bucket(group_col, label_fn=lambda v: str(v)) -> list[TokenBucket]:
        rows = db.execute(
            select(
                group_col.label("k"),
                func.count(AICallLog.id),
                func.sum(AICallLog.prompt_tokens),
                func.sum(AICallLog.completion_tokens),
                func.sum(AICallLog.total_tokens),
            )
            .where(base)
            .group_by(group_col)
            .order_by(func.sum(AICallLog.total_tokens).desc().nullslast())
        ).all()
        return [
            TokenBucket(
                key=label_fn(r[0]),
                call_count=_coalesce(r[1]),
                prompt_tokens=_coalesce(r[2]),
                completion_tokens=_coalesce(r[3]),
                total_tokens=_coalesce(r[4]),
            )
            for r in rows
        ]

    by_scene = _bucket(AICallLog.scene)
    by_model = _bucket(AICallLog.model)

    # 按小时:strftime('%H', created_at) 在 SQLite 上可用;其它 dialect 退化为
    # 对 created_at 取 hour 部分。这里只支持 SQLite,直接用 strftime。
    hour_col = func.strftime("%H", AICallLog.created_at)
    by_hour_raw = _bucket(hour_col, label_fn=lambda v: f"{int(v):02d}")
    # 按时间排序展示更直观
    by_hour = sorted(by_hour_raw, key=lambda b: b.key)

    # 最近 N 条
    recent_rows = db.execute(
        select(AICallLog)
        .where(base)
        .order_by(AICallLog.created_at.desc())
        .limit(_RECENT_LIMIT)
    ).scalars().all()
    recent = [TokenCallItem.model_validate(r) for r in recent_rows]

    return TokenStatsResponse(
        summary=summary,
        by_scene=by_scene,
        by_model=by_model,
        by_hour=by_hour,
        recent=recent,
    )
