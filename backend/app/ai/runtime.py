"""把 DB 中的 AI 设置解析为 LiteLLM 调用参数。

优先级:
- DB 里有完整配置(api_key 或 ollama provider) → 用 DB,显式覆盖 env
- 否则回退到 .env(由 LiteLLM 自己读),保留 .env 里的 key 继续可用

支持两个角色:
- writing(默认):正常写作 / 抽取等场景
- review:评分 / 文风检查 / 一致性检查 — 这类「自评偏差」场景适合用另一个模型;
  审稿配置任一字段缺失就回落写作角色,保证老用户零感知
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.config import settings as env_settings
from app.services import settings_service
from app.services.settings_service import _review_configured

Role = Literal["writing", "review"]


@dataclass
class RuntimeAIConfig:
    model: str
    api_base: str | None
    api_key: str | None  # None → 让 LiteLLM 从 env 读
    temperature: float
    max_tokens: int
    configured: bool
    provider: str  # 仅供 /info 展示
    role: Role = "writing"


# 走审稿模型的 scene 集合。其它 scene 全走写作。
REVIEW_SCENES: frozenset[str] = frozenset({
    "chapter.score",
    "chapter.style_check",
    "analysis.check",
})


def role_for_scene(scene: str) -> Role:
    return "review" if scene in REVIEW_SCENES else "writing"


def resolve(db: Session, role: Role = "writing") -> RuntimeAIConfig:
    s = settings_service.get_or_create(db)

    if role == "review" and _review_configured(s):
        return RuntimeAIConfig(
            model=s.review_model,
            api_base=(s.review_base_url or "").strip() or None,
            api_key=(s.review_api_key or "").strip() or None,
            temperature=s.review_temperature if s.review_temperature is not None else s.temperature,
            max_tokens=s.review_max_tokens if s.review_max_tokens is not None else s.max_tokens,
            configured=True,
            provider=s.review_provider or "custom",
            role="review",
        )

    # role=writing,或 role=review 但未配置审稿 → 走写作配置
    if s.api_key or s.provider in {"ollama", "gemma_e4b", "gemma_26b"}:
        return RuntimeAIConfig(
            model=s.model,
            api_base=s.base_url,
            api_key=s.api_key,
            temperature=s.temperature,
            max_tokens=s.max_tokens,
            configured=True,
            provider=s.provider,
            role=role,
        )

    return RuntimeAIConfig(
        model=s.model or env_settings.ai_model,
        api_base=s.base_url or env_settings.ai_base_url,
        api_key=None,
        temperature=s.temperature,
        max_tokens=s.max_tokens,
        configured=env_settings.ai_configured,
        provider="env",
        role=role,
    )
