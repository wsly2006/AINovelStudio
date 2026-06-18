"""把 DB 中的 AI 设置解析为 LiteLLM 调用参数。

优先级:
- DB 里有完整配置(api_key 或 ollama provider) → 用 DB,显式覆盖 env
- 否则回退到 .env(由 LiteLLM 自己读),保留 .env 里的 key 继续可用
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings as env_settings
from app.services import settings_service


@dataclass
class RuntimeAIConfig:
    model: str
    api_base: str | None
    api_key: str | None  # None → 让 LiteLLM 从 env 读
    temperature: float
    max_tokens: int
    configured: bool
    provider: str  # 仅供 /info 展示


def resolve(db: Session) -> RuntimeAIConfig:
    s = settings_service.get_or_create(db)

    # DB 有 key 或者是本地推理(ollama / gemma_*)→ 使用 DB
    if s.api_key or s.provider in {"ollama", "gemma_e4b", "gemma_26b"}:
        return RuntimeAIConfig(
            model=s.model,
            api_base=s.base_url,
            api_key=s.api_key,
            temperature=s.temperature,
            max_tokens=s.max_tokens,
            configured=True,
            provider=s.provider,
        )

    # 回退到 env:DB 里仍可保留 model/temperature/max_tokens 这些非密参数
    return RuntimeAIConfig(
        model=s.model or env_settings.ai_model,
        api_base=s.base_url or env_settings.ai_base_url,
        api_key=None,
        temperature=s.temperature,
        max_tokens=s.max_tokens,
        configured=env_settings.ai_configured,
        provider="env",
    )
