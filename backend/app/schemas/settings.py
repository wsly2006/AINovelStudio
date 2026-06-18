from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 与前端 PRESETS 一一对应,便于 UI 高亮当前选中
ProviderKey = Literal[
    "claude", "openai", "deepseek", "qwen",
    "ollama", "gemma_e4b", "gemma_26b",
    "custom", "env",
]


class AISettingsRead(BaseModel):
    """读出的配置。api_key 永远不返回真实值,只表示是否已设置。

    review_* 字段为 None 时表示尚未配置审稿模型,前端会回落显示「跟写作模型相同」。
    """

    model_config = ConfigDict(from_attributes=True)

    provider: ProviderKey
    model: str
    base_url: str | None
    api_key_set: bool = Field(description="api_key 是否已配置")
    temperature: float
    max_tokens: int

    # 审稿模型(可选)
    review_provider: ProviderKey | None = None
    review_model: str | None = None
    review_base_url: str | None = None
    review_api_key_set: bool = False
    review_temperature: float | None = None
    review_max_tokens: int | None = None
    review_configured: bool = Field(
        default=False,
        description="审稿配置是否完整可用(model 有值且 key 有值或为本地推理)",
    )


class AISettingsUpdate(BaseModel):
    """写作模型更新(单写作角色,审稿走 /ai/review 子接口)。"""

    provider: ProviderKey
    model: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=400)
    # 保留之前的 key 不变(前端不回显也不修改时传 None;清空传空字符串)
    keep_existing_key: bool = Field(default=False)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=128, le=32768)


class AIReviewSettingsUpdate(BaseModel):
    """审稿模型更新。enabled=False 时清空所有审稿字段,使评审场景回落写作模型。"""

    enabled: bool = Field(default=True)
    provider: ProviderKey | None = None
    model: str | None = Field(default=None, max_length=120)
    base_url: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=400)
    keep_existing_key: bool = Field(default=False)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=128, le=32768)
