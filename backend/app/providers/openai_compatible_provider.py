"""Provider for any OpenAI-chat-completions-compatible endpoint: Groq
(e.g. `openai/gpt-oss-120b`), Hugging Face's Inference Providers router, or
in principle Together/Fireworks/a local vLLM server. One class covers all
of them since they share the same wire protocol — swap `base_url`/`model`.

Why this exists alongside the Anthropic provider, not instead of it: these
endpoints are used where request volume matters more than citation
precision — the eval harness (hundreds of calls per run) and local dev
iteration — where the Anthropic API's tighter per-minute rate limits make
fast iteration painful. OSS models hosted on Groq get materially higher
throughput.

The tradeoff, stated plainly: none of these endpoints have Anthropic's
native Citations feature. There is no API-guaranteed offset into the source
document. So grounding here is enforced entirely by us, in two steps:
  1. Prompt the model to return strict JSON with verbatim quotes, tagged by
     which numbered document they came from.
  2. For every returned quote, do a literal substring search
     (`document.text.find(quote)`) against that exact document. If the
     quote isn't found verbatim, we drop it — never show a citation we
     can't prove is real. The char offset used for the timestamp lookup is
     the offset returned by that search, not by the model.
This is a strictly weaker grounding guarantee than the Anthropic path (a
model can still just not produce a matching quote, in which case the claim
loses its citation entirely) but it never fabricates one.
"""

import json
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_random_exponential

from ..logging_config import get_logger
from .anthropic_provider import ProviderCallError
from .types import GROUNDING_INSTRUCTION, AskResult, DocInput, RawCitation

logger = get_logger(__name__)

_RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)

_JSON_INSTRUCTION = (
    "\n\nRespond with ONLY a single JSON object, no prose before or after it, matching "
    "exactly this shape:\n"
    '{"answer": "1-3 sentence answer", '
    '"quotes": [{"document_index": <int>, "quote": "verbatim substring copied '
    'character-for-character from that document, no paraphrasing"}]}\n'
    "Include one quote per distinct document your answer draws on. If nothing in the "
    'documents supports an answer, use {"answer": "Not addressed in the transcript(s).", '
    '"quotes": []}.'
)


class OpenAICompatibleProvider:
    def __init__(self, name: str, base_url: str, api_key: str, model: str, max_retries: int = 3):
        if not api_key:
            raise ProviderCallError(
                f"No API key configured for provider '{name}'. Set the corresponding "
                f"env var (see backend/.env.example)."
            )
        self.name = name
        self._model = model
        self._max_retries = max_retries
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def _create(self, **kwargs):
        retryer = Retrying(
            retry=retry_if_exception_type(_RETRYABLE),
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(self._max_retries),
            reraise=True,
        )
        return retryer(lambda: self._client.chat.completions.create(**kwargs))

    def _build_prompt(self, docs: list[DocInput], prompt: str) -> str:
        doc_blocks = []
        for i, d in enumerate(docs):
            doc_blocks.append(f"DOCUMENT {i} — {d.title}\n---\n{d.text}\n---")
        return "\n\n".join(doc_blocks) + "\n\n" + prompt + _JSON_INSTRUCTION

    def ask(self, docs: list[DocInput], prompt: str, max_tokens: int = 1024) -> AskResult:
        started = time.monotonic()
        try:
            response = self._create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": GROUNDING_INSTRUCTION},
                    {"role": "user", "content": self._build_prompt(docs, prompt)},
                ],
            )
        except APIStatusError as e:
            logger.error("%s API call failed with status %s: %s", self.name, e.status_code, e)
            raise ProviderCallError(f"{self.name} API error ({e.status_code}): {e}") from e
        except _RETRYABLE as e:
            logger.error("%s API call failed after retries: %s", self.name, e)
            raise ProviderCallError(f"{self.name} API is currently unavailable: {e}") from e

        latency_ms = int((time.monotonic() - started) * 1000)
        raw_text = response.choices[0].message.content or "{}"

        answer_text, raw_citations = self._parse_and_verify(raw_text, docs)

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0

        logger.info(
            "llm_call provider=%s model=%s latency_ms=%d input_tokens=%d output_tokens=%d "
            "num_docs=%d num_citations=%d",
            self.name,
            self._model,
            latency_ms,
            input_tokens,
            output_tokens,
            len(docs),
            len(raw_citations),
        )

        return AskResult(
            answer_text=answer_text,
            raw_citations=raw_citations,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            provider=self.name,
        )

    def _parse_and_verify(
        self, raw_text: str, docs: list[DocInput]
    ) -> tuple[str, list[RawCitation]]:
        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "%s returned non-JSON output; showing answer with no citations", self.name
            )
            return raw_text.strip(), []

        answer = str(parsed.get("answer", "")).strip()
        raw_citations: list[RawCitation] = []
        for q in parsed.get("quotes", []) or []:
            try:
                doc_index = int(q["document_index"])
                quote = str(q["quote"]).strip()
            except (KeyError, TypeError, ValueError):
                continue
            if not quote or doc_index < 0 or doc_index >= len(docs):
                continue
            offset = docs[doc_index].text.find(quote)
            if offset == -1:
                # The model's "verbatim" quote doesn't actually appear in the source —
                # drop it rather than show an unverifiable citation.
                logger.warning(
                    "%s produced a quote not found verbatim in document %d; dropping it",
                    self.name,
                    doc_index,
                )
                continue
            raw_citations.append(
                RawCitation(document_index=doc_index, cited_text=quote, start_char_index=offset)
            )

        return answer, raw_citations
