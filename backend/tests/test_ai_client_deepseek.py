"""DeepSeek V4 thinking 会占满 max_tokens 导致 content 为空;客户端需显式关闭。"""

from app.ai.client import _build_kwargs, _is_deepseek
from app.ai.runtime import RuntimeAIConfig


def _cfg(**overrides) -> RuntimeAIConfig:
    base = dict(
        model="deepseek/deepseek-v4-flash",
        api_base=None,
        api_key="sk-test",
        temperature=0.7,
        max_tokens=4096,
        configured=True,
        provider="deepseek",
    )
    base.update(overrides)
    return RuntimeAIConfig(**base)


def test_is_deepseek_by_provider_and_model() -> None:
    assert _is_deepseek(_cfg())
    assert _is_deepseek(_cfg(provider="custom", model="deepseek-v4-flash"))
    assert _is_deepseek(_cfg(provider="openai", model="deepseek/deepseek-chat"))
    assert not _is_deepseek(_cfg(provider="openai", model="gpt-4o"))


def test_build_kwargs_disables_deepseek_thinking() -> None:
    kwargs = _build_kwargs(_cfg())
    assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}
    assert kwargs["model"] == "deepseek/deepseek-v4-flash"
    assert kwargs["api_key"] == "sk-test"


def test_build_kwargs_other_providers_untouched() -> None:
    kwargs = _build_kwargs(_cfg(provider="openai", model="gpt-4o"))
    assert "extra_body" not in kwargs
