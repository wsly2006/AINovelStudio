from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"
    frontend_origin: str = "http://localhost:5173"
    host: str = "127.0.0.1"
    port: int = 8765

    # --- AI 配置(LiteLLM) ---
    # model 名按 LiteLLM 约定:claude-* / gpt-* / deepseek/* / openai/* / ollama/* 等
    ai_model: str = "claude-opus-4-7"
    # 可选:某些 provider 需要,如自托管 OpenAI 兼容端点
    ai_base_url: str | None = None
    # 默认温度 / 上下文上限(tokens 估算)
    ai_temperature: float = 0.7
    ai_max_tokens: int = 4096

    @property
    def ai_configured(self) -> bool:
        """是否至少有一种 API key 可用。无 key 时 AI 接口会返回 503。"""
        import os

        keys = [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "DEEPSEEK_API_KEY",
            "DASHSCOPE_API_KEY",
            "MOONSHOT_API_KEY",
            "GEMINI_API_KEY",
        ]
        return any(os.getenv(k) for k in keys)


settings = Settings()
