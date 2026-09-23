"""Provider for any OpenAI-chat-completions-compatible endpoint: Gemini
(via its OpenAI-compatible endpoint), Groq (e.g. `openai/gpt-oss-120b`),
Hugging Face's Inference Providers router, or in principle
Together/Fireworks/a local vLLM server. One class covers all of them since
they share the same wire protocol — swap `base_url`/`model`.

None of these endpoints have a native citations feature — there is no
API-guaranteed offset into the source document. So grounding here is
enforced entirely by us, in two steps:
  1. Prompt the model to return strict JSON with verbatim quotes, tagged by
     which numbered document they came from.
  2. For every returned quote, do a literal substring search
     (`document.text.find(quote)`) against that exact document. If the
     quote isn't found verbatim, we drop it — never show a citation we
     can't prove is real. The char offset used for the timestamp lookup is
     the offset returned by that search, not by the model.
A model can still just not produce a matching quote, in which case the
claim loses its citation entirely, but it never fabricates one.
"""

import json
import time
from threading import BoundedSemaphore

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
from ..observability import record_llm, tracer
from .types import GROUNDING_INSTRUCTION, AskResult, DocInput, ProviderCallError, RawCitation

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

_BATCH_JSON_INSTRUCTION = (
    "\n\nRespond with ONLY a single JSON object, no prose before or after it, matching "
    "exactly this shape:\n"
    '{"answers": [{"index": <int>, "answer": "1-3 sentence answer", '
    '"quotes": [{"document_index": <int>, "quote": "verbatim substring copied '
    'character-for-character from that document, no paraphrasing"}]}]}\n'
    'Include exactly one object in "answers" per numbered QUESTION below, in the same '
    'order, using its 0-based position as "index". Include one quote per distinct '
    "document that answer draws on. If nothing in the documents supports an answer to "
    'a question, use "answer": "Not addressed in the transcript(s)." and "quotes": [].'
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        max_retries: int = 3,
        max_concurrent_requests: int = 4,
    ):
        if not api_key:
            raise ProviderCallError(
                f"No API key configured for provider '{name}'. Set the corresponding "
                f"env var (see backend/.env.example)."
            )
        self.name = name
        self._model = model
        self._max_retries = max_retries
        self._inflight = BoundedSemaphore(max_concurrent_requests)
        self._client = OpenAI(base_url=base_url, api_key=api_key)

    def _create(self, **kwargs):
        if not self._inflight.acquire(blocking=False):
            raise ProviderCallError("LLM capacity is busy; please retry shortly")
        retryer = Retrying(
            retry=retry_if_exception_type(_RETRYABLE),
            wait=wait_random_exponential(multiplier=1, max=20),
            stop=stop_after_attempt(self._max_retries),
            reraise=True,
        )
        try:
            return retryer(lambda: self._client.chat.completions.create(**kwargs))
        finally:
            self._inflight.release()

    def _build_prompt(self, docs: list[DocInput], prompt: str) -> str:
        doc_blocks = []
        for i, d in enumerate(docs):
            doc_blocks.append(f"DOCUMENT {i} — {d.title}\n---\n{d.text}\n---")
        return "\n\n".join(doc_blocks) + "\n\n" + prompt + _JSON_INSTRUCTION

    def _build_batch_prompt(self, docs: list[DocInput], prompts: list[str]) -> str:
        doc_blocks = [f"DOCUMENT {i} — {d.title}\n---\n{d.text}\n---" for i, d in enumerate(docs)]
        question_blocks = [f"QUESTION {i}: {p}" for i, p in enumerate(prompts)]
        return (
            "\n\n".join(doc_blocks)
            + "\n\n"
            + "\n\n".join(question_blocks)
            + _BATCH_JSON_INSTRUCTION
        )

    def _complete(self, user_content: str, max_tokens: int):
        started = time.monotonic()
        kwargs = dict(
            model=self._model,
            max_tokens=max_tokens,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": GROUNDING_INSTRUCTION},
                {"role": "user", "content": user_content},
            ],
        )
        if self.name == "groq":
            # gpt-oss models emit hidden chain-of-thought tokens that count
            # against max_tokens before the JSON answer itself — at "medium"
            # (Groq's default) this routinely eats the whole budget on short
            # max_tokens calls, so Groq's server-side JSON-mode validator
            # rejects the truncated completion with a 400 instead of
            # returning partial text. "low" leaves enough budget for the
            # answer. Not sent to other OpenAI-compatible endpoints (e.g.
            # HF), which may not support this param.
            kwargs["extra_body"] = {"reasoning_effort": "low"}
        with tracer(__name__).start_as_current_span("llm.completion") as span:
            span.set_attribute("gen_ai.provider.name", self.name)
            span.set_attribute("gen_ai.request.model", self._model)
            try:
                response = self._create(**kwargs)
            except APIStatusError as e:
                record_llm(self.name, outcome="error")
                logger.error("%s API call failed with status %s: %s", self.name, e.status_code, e)
                raise ProviderCallError(f"{self.name} API error ({e.status_code}): {e}") from e
            except _RETRYABLE as e:
                record_llm(self.name, outcome="error")
                logger.error("%s API call failed after retries: %s", self.name, e)
                raise ProviderCallError(f"{self.name} API is currently unavailable: {e}") from e

        latency_ms = int((time.monotonic() - started) * 1000)
        raw_text = response.choices[0].message.content or "{}"
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        record_llm(
            self.name,
            outcome="success",
            duration_seconds=latency_ms / 1000,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        return raw_text, latency_ms, input_tokens, output_tokens

    def ask(self, docs: list[DocInput], prompt: str, max_tokens: int = 1024) -> AskResult:
        raw_text, latency_ms, input_tokens, output_tokens = self._complete(
            self._build_prompt(docs, prompt), max_tokens
        )
        answer_text, raw_citations = self._parse_and_verify(raw_text, docs)

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

    def ask_batch(
        self, docs: list[DocInput], prompts: list[str], max_tokens: int = 3000
    ) -> list[AskResult]:
        raw_text, latency_ms, input_tokens, output_tokens = self._complete(
            self._build_batch_prompt(docs, prompts), max_tokens
        )
        answers = self._parse_and_verify_batch(raw_text, docs, len(prompts))

        logger.info(
            "llm_call provider=%s model=%s latency_ms=%d input_tokens=%d output_tokens=%d "
            "num_docs=%d num_questions=%d num_citations=%d",
            self.name,
            self._model,
            latency_ms,
            input_tokens,
            output_tokens,
            len(docs),
            len(prompts),
            sum(len(citations) for _, citations in answers),
        )

        return [
            AskResult(
                answer_text=answer_text,
                raw_citations=raw_citations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                provider=self.name,
            )
            for answer_text, raw_citations in answers
        ]

    def _verify_quotes(self, quotes_raw, docs: list[DocInput]) -> list[RawCitation]:
        raw_citations: list[RawCitation] = []
        for q in quotes_raw or []:
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
        return raw_citations

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
        raw_citations = self._verify_quotes(parsed.get("quotes", []), docs)
        return answer, raw_citations

    def _parse_and_verify_batch(
        self, raw_text: str, docs: list[DocInput], n: int
    ) -> list[tuple[str, list[RawCitation]]]:
        try:
            parsed = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            logger.warning("%s returned non-JSON batch output; returning empty answers", self.name)
            return [("", []) for _ in range(n)]

        by_index: dict[int, tuple[str, list[RawCitation]]] = {}
        for item in parsed.get("answers", []) or []:
            try:
                idx = int(item["index"])
            except (KeyError, TypeError, ValueError):
                continue
            if idx < 0 or idx >= n:
                continue
            answer = str(item.get("answer", "")).strip()
            raw_citations = self._verify_quotes(item.get("quotes", []), docs)
            by_index[idx] = (answer, raw_citations)

        return [by_index.get(i, ("", [])) for i in range(n)]
