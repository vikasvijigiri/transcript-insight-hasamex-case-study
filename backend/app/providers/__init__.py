"""Factory that builds the configured LLM provider. Everything else in the
app (main.py, the eval harness) depends only on the `Provider` protocol in
`.types`, never on a concrete SDK — swapping providers is a config change,
not a code change."""

from functools import lru_cache

from ..config import Settings, get_settings
from .openai_compatible_provider import OpenAICompatibleProvider
from .types import AskResult, DocInput, Provider, ProviderCallError, RawCitation

__all__ = [
    "AskResult",
    "DocInput",
    "Provider",
    "ProviderCallError",
    "RawCitation",
    "build_provider",
    "get_provider",
]


def build_provider(settings: Settings) -> Provider:
    if settings.llm_provider == "gemini":
        return OpenAICompatibleProvider(
            name="gemini",
            base_url=settings.gemini_base_url,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            max_retries=settings.max_retries,
            max_concurrent_requests=settings.llm_max_concurrent_requests,
        )
    if settings.llm_provider == "groq":
        return OpenAICompatibleProvider(
            name="groq",
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            max_retries=settings.max_retries,
            max_concurrent_requests=settings.llm_max_concurrent_requests,
        )
    if settings.llm_provider == "huggingface":
        return OpenAICompatibleProvider(
            name="huggingface",
            base_url=settings.hf_base_url,
            api_key=settings.hf_api_key,
            model=settings.hf_model,
            max_retries=settings.max_retries,
            max_concurrent_requests=settings.llm_max_concurrent_requests,
        )
    raise ValueError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'. Expected one of: "
        "gemini, groq, huggingface."
    )


@lru_cache
def get_provider() -> Provider:
    return build_provider(get_settings())
