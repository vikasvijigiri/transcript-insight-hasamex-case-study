"""Anthropic provider — the default/production path.

Uses Claude's native **Citations** feature: citations are computed by the
API against the literal document text we send, not generated freeform by
the model, so a citation cannot be a paraphrase or an invented sentence.
Each citation carries a document index and a char-offset span into that
document, which `main.py` maps back to a transcript timestamp.

Production hardening: retries with exponential backoff + jitter on
transient failures (rate limits, connection errors, 5xx) via tenacity, a
request timeout, and structured logging of latency/token usage per call.
We deliberately do NOT retry on 4xx client errors — those won't succeed on
retry and just burn time and quota.
"""

import time

from anthropic import (
    Anthropic,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from ..config import Settings
from ..logging_config import get_logger
from .types import GROUNDING_INSTRUCTION, AskResult, DocInput, RawCitation

logger = get_logger(__name__)

_RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)


class ProviderCallError(Exception):
    """Raised when a call to an LLM provider fails after retries. Route
    handlers catch this and turn it into a clean HTTP error instead of a
    raw 500 with an SDK stack trace."""


def _log_retry(retry_state) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retrying Anthropic API call after %s (attempt %d)",
        type(exc).__name__ if exc else "unknown error",
        retry_state.attempt_number,
    )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, settings: Settings):
        if not settings.anthropic_api_key:
            raise ProviderCallError(
                "ANTHROPIC_API_KEY is not set. Copy backend/.env.example to backend/.env "
                "and add your key."
            )
        self._settings = settings
        self._client = Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.request_timeout_seconds,
        )

    def _create_message(self, **kwargs):
        retryer = Retrying(
            retry=retry_if_exception_type(_RETRYABLE),
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(self._settings.max_retries),
            before_sleep=_log_retry,
            reraise=True,
        )
        return retryer(lambda: self._client.messages.create(**kwargs))

    def ask(self, docs: list[DocInput], prompt: str, max_tokens: int = 1024) -> AskResult:
        content = []
        for d in docs:
            content.append(
                {
                    "type": "document",
                    "source": {"type": "text", "media_type": "text/plain", "data": d.text},
                    "title": d.title,
                    "citations": {"enabled": True},
                }
            )
        content.append({"type": "text", "text": prompt})

        started = time.monotonic()
        try:
            response = self._create_message(
                model=self._settings.claude_model,
                max_tokens=max_tokens,
                system=GROUNDING_INSTRUCTION,
                messages=[{"role": "user", "content": content}],
            )
        except APIStatusError as e:
            logger.error("Anthropic API call failed with status %s: %s", e.status_code, e.message)
            raise ProviderCallError(f"Claude API error ({e.status_code}): {e.message}") from e
        except _RETRYABLE as e:
            logger.error("Anthropic API call failed after retries: %s", e)
            raise ProviderCallError(f"Claude API is currently unavailable: {e}") from e

        latency_ms = int((time.monotonic() - started) * 1000)

        answer_parts: list[str] = []
        raw_citations: list[RawCitation] = []
        for block in response.content:
            if block.type == "text":
                answer_parts.append(block.text)
                for c in block.citations or []:
                    if getattr(c, "type", None) == "char_location":
                        raw_citations.append(
                            RawCitation(
                                document_index=c.document_index,
                                cited_text=c.cited_text,
                                start_char_index=c.start_char_index,
                            )
                        )

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0

        logger.info(
            "llm_call provider=anthropic model=%s latency_ms=%d input_tokens=%d "
            "output_tokens=%d num_docs=%d num_citations=%d",
            self._settings.claude_model,
            latency_ms,
            input_tokens,
            output_tokens,
            len(docs),
            len(raw_citations),
        )

        return AskResult(
            answer_text="".join(answer_parts),
            raw_citations=raw_citations,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            provider="anthropic",
        )
