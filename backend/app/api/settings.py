from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai import client as ai_client
from app.database import get_db
from app.schemas.settings import AISettingsRead, AISettingsUpdate
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


@router.post("/ai/test")
async def test_ai_settings(db: Session = Depends(get_db)) -> dict:
    """跑一次极小的 chat 验证模型 / base_url / key 是否真的能用。

    用最少的 token 数避免本地大模型卡半天。任何异常都翻译成 ok=False + message。
    前端按钮上不需要看到栈,所以这里不抛 HTTPException。
    """
    messages = [{"role": "user", "content": "ping"}]
    try:
        text = await ai_client.complete(db, messages, scene="settings.test", max_tokens=8)
    except ai_client.AINotConfiguredError as e:
        return {"ok": False, "message": str(e)}
    except ai_client.AIError as e:
        return {"ok": False, "message": str(e)}
    return {"ok": True, "sample": (text or "").strip()[:80]}
