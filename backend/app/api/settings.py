from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.database import get_db
from app.schemas.settings import (
    AIReviewSettingsUpdate,
    AISettingsRead,
    AISettingsUpdate,
)
from app.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/ai", response_model=AISettingsRead)
def get_ai_settings(db: Session = Depends(get_db)) -> AISettingsRead:
    s = settings_service.get_or_create(db)
    return settings_service.to_read(s)


@router.put("/ai", response_model=AISettingsRead)
def update_ai_settings(
    payload: AISettingsUpdate, db: Session = Depends(get_db)
) -> AISettingsRead:
    s = settings_service.update(db, payload)
    return settings_service.to_read(s)


@router.put("/ai/review", response_model=AISettingsRead)
def update_review_settings(
    payload: AIReviewSettingsUpdate, db: Session = Depends(get_db)
) -> AISettingsRead:
    """单独维护审稿模型。enabled=False 时清空,使评审场景回落写作模型。"""
    s = settings_service.update_review(db, payload)
    return settings_service.to_read(s)


@router.post("/ai/test")
async def test_ai_settings(
    role: str = "writing", db: Session = Depends(get_db)
) -> dict:
    """跑一次极小的 chat 验证模型 / base_url / key 是否真的能用。

    role=writing(默认) → 测写作模型;role=review → 测审稿模型。
    用最少的 token 数避免本地大模型卡半天。任何异常都翻译成 ok=False + message。
    """
    # 选 role 对应的 scene:写作走 settings.test,审稿走 chapter.score 触发审稿路由
    scene = "chapter.score" if role == "review" else "settings.test"
    messages = [{"role": "user", "content": "ping"}]
    try:
        text = await ai_client.complete(db, messages, scene=scene, max_tokens=8)
    except ai_client.AINotConfiguredError as e:
        return {"ok": False, "message": str(e)}
    except ai_client.AIError as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "sample": (text or "").strip()[:80]}

