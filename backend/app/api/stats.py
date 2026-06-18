"""Token 用量统计接口。"""

from datetime import date as date_cls, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.stats import TokenStatsResponse
from app.services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/tokens", response_model=TokenStatsResponse)
def get_token_stats(
    date: str | None = Query(default=None, description="YYYY-MM-DD,留空表示今天"),
    db: Session = Depends(get_db),
) -> TokenStatsResponse:
    if date:
        try:
            d = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as e:
            raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from e
    else:
        d = date_cls.today()
    return stats_service.get_token_stats(db, d)
