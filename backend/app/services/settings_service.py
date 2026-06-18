from sqlalchemy.orm import Session

from app.models.settings import AISettings
from app.schemas.settings import AISettingsRead, AISettingsUpdate

SINGLETON_ID = 1
_VALID_PROVIDERS = {
    "claude", "openai", "deepseek", "qwen",
    "ollama", "gemma_e4b", "gemma_26b",
    "custom", "env",
}


def get_or_create(db: Session) -> AISettings:
    s = db.get(AISettings, SINGLETON_ID)
    if s is None:
        s = AISettings(id=SINGLETON_ID)
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def to_read(s: AISettings) -> AISettingsRead:
    return AISettingsRead(
        provider=s.provider if s.provider in _VALID_PROVIDERS else "env",
        model=s.model,
        base_url=s.base_url,
        api_key_set=bool(s.api_key),
        temperature=s.temperature,
        max_tokens=s.max_tokens,
    )


def update(db: Session, payload: AISettingsUpdate) -> AISettings:
    s = get_or_create(db)
    s.provider = payload.provider
    s.model = payload.model.strip()
    s.base_url = (payload.base_url or "").strip() or None
    if not payload.keep_existing_key:
        # 空字符串 → 清空;有值 → 替换
        s.api_key = (payload.api_key or "").strip() or None
    s.temperature = payload.temperature
    s.max_tokens = payload.max_tokens
    db.commit()
    db.refresh(s)
    return s
