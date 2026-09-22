"""Typed, validated application configuration.

Centralising env parsing here (instead of scattered `os.environ.get(...)`
calls) means: missing/invalid config fails fast at startup with a clear
error, there's one place to see every knob the app exposes, and tests can
override settings by constructing `Settings(...)` directly instead of
mutating process env vars.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Which provider answers questions. "anthropic" is the default/production path
    # (native Citations API = exact offset-grounded quotes). "groq" / "huggingface"
    # route to OpenAI-compatible endpoints serving open-weight models (e.g.
    # openai/gpt-oss-120b) — used for the eval harness and high-volume dev
    # iteration where Anthropic's per-minute rate limits get in the way.
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(default="claude-sonnet-5", alias="CLAUDE_MODEL")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")

    hf_api_key: str = Field(default="", alias="HF_API_KEY")
    hf_model: str = Field(default="openai/gpt-oss-120b", alias="HF_MODEL")
    hf_base_url: str = Field(default="https://router.huggingface.co/v1", alias="HF_BASE_URL")

    # Comma-separated list of allowed origins, e.g. "http://localhost:3000,https://app.example.com"
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Resilience knobs for calls to the Anthropic API
    request_timeout_seconds: float = Field(default=60.0, alias="ANTHROPIC_TIMEOUT_SECONDS")
    max_retries: int = Field(default=3, alias="ANTHROPIC_MAX_RETRIES")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
