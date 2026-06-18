from sqlalchemy.orm import Session

from app.models.settings import AISettings
from app.schemas.settings import (
    AIReviewSettingsUpdate,
    AISettingsRead,
    AISettingsUpdate,
)

SINGLETON_ID = 1
_VALID_PROVIDERS = {
    "claude", "openai", "deepseek", "qwen",
    "ollama", "gemma_e4b", "gemma_26b",
    "custom", "env",
}
_LOCAL_PROVIDERS = {"ollama", "gemma_e4b", "gemma_26b"}


def _review_configured(s: AISettings) -> bool:
    """审稿模型必须 model 有值,且 api_key 有值或 provider 是本地推理。

    放这里是为了避免和 ai.runtime 形成循环 import(runtime 依赖本模块)。
    """
    if not (s.review_model or "").strip():
        return False
    if (s.review_api_key or "").strip():
        return True
    return s.review_provider in _LOCAL_PROVIDERS


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
        review_provider=(
            s.review_provider
            if s.review_provider in _VALID_PROVIDERS
            else None
        ),
        review_model=s.review_model,
        review_base_url=s.review_base_url,
        review_api_key_set=bool(s.review_api_key),
        review_temperature=s.review_temperature,
        review_max_tokens=s.review_max_tokens,
        review_configured=_review_configured(s),
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


def update_review(db: Session, payload: AIReviewSettingsUpdate) -> AISettings:
    """更新审稿模型。enabled=False 视为禁用,清空所有审稿列。"""
    s = get_or_create(db)
    if not payload.enabled:
        s.review_provider = None
        s.review_model = None
        s.review_base_url = None
        s.review_api_key = None
        s.review_temperature = None
        s.review_max_tokens = None
        db.commit()
        db.refresh(s)
        return s

    s.review_provider = payload.provider or s.review_provider or "custom"
    s.review_model = (payload.model or "").strip() or s.review_model
    s.review_base_url = (
        (payload.base_url or "").strip() or None
        if payload.base_url is not None
        else s.review_base_url
    )
    if not payload.keep_existing_key:
        s.review_api_key = (payload.api_key or "").strip() or None
    if payload.temperature is not None:
        s.review_temperature = payload.temperature
    if payload.max_tokens is not None:
        s.review_max_tokens = payload.max_tokens
    db.commit()
    db.refresh(s)
    return s
