from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 与前端 PRESETS 一一对应,便于 UI 高亮当前选中
ProviderKey = Literal[
    "claude", "openai", "deepseek", "qwen",
    "ollama", "gemma_e4b", "gemma_26b",
    "custom", "env",
]


class AISettingsRead(BaseModel):
    """读出的配置。api_key 永远不返回真实值,只表示是否已设置。"""

    model_config = ConfigDict(from_attributes=True)

    provider: ProviderKey
    model: str
    base_url: str | None
    api_key_set: bool = Field(description="api_key 是否已配置")
    temperature: float
    max_tokens: int


class AISettingsUpdate(BaseModel):
    provider: ProviderKey
    model: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=400)
    # 保留之前的 key 不变(前端不回显也不修改时传 None;清空传空字符串)
    keep_existing_key: bool = Field(default=False)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=128, le=32768)
