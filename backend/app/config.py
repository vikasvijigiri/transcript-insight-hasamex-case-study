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

    # Which provider answers questions: "gemini" (default), "groq", or
    # "huggingface" — all OpenAI-compatible endpoints. Grounding (verbatim-quote
    # substring verification) is enforced by us, not by the provider. Gemini's
    # free tier (250K TPM) is the default because Groq's free tier (8K TPM) is too
    # tight for this app's multi-call /qa and /themes endpoints; Groq stays
    # available as a manual fallback via LLM_PROVIDER=groq.
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")

    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-120b", alias="GROQ_MODEL")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")

    hf_api_key: str = Field(default="", alias="HF_API_KEY")
    hf_model: str = Field(default="openai/gpt-oss-120b", alias="HF_MODEL")
    hf_base_url: str = Field(default="https://router.huggingface.co/v1", alias="HF_BASE_URL")

    # Google Gemini, via its OpenAI-compatible endpoint — free tier gives 250K TPM,
    # far above Groq's 8K TPM cap, which this app's multi-call /qa and /themes
    # endpoints were hitting in practice.
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-3.6-flash", alias="GEMINI_MODEL")
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com/v1beta/openai/",
        alias="GEMINI_BASE_URL",
    )

    # Comma-separated list of allowed origins, e.g. "http://localhost:3000,https://app.example.com"
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Retry count for transient LLM provider failures (rate limits, connection
    # errors, 5xx) — shared by all providers via OpenAICompatibleProvider.
    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
