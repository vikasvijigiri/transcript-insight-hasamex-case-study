"""Shared types every provider implementation produces, so the rest of the
app (citation->timestamp resolution, quote verification, caching) never has
to know which LLM actually answered the question."""

from typing import Protocol

from pydantic import BaseModel


class DocInput(BaseModel):
    expert_id: str
    title: str
    text: str


class RawCitation(BaseModel):
    document_index: int
    cited_text: str
    start_char_index: int


class AskResult(BaseModel):
    answer_text: str
    raw_citations: list[RawCitation]
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    provider: str = ""


GROUNDING_INSTRUCTION = (
    "You are analysing verbatim interview transcripts for a market-research project. "
    "Only use information explicitly stated in the transcript document(s) provided. "
    "Never use outside knowledge, never estimate or invent numbers, names, or claims "
    "that are not in the transcript. If the transcripts do not address something, say "
    "so plainly instead of guessing."
)


class Provider(Protocol):
    """Every provider (an OpenAI-compatible endpoint like Gemini/Groq/HF)
    implements these methods. `main.py` only ever talks to this interface."""

    name: str

    def ask(self, docs: list[DocInput], prompt: str, max_tokens: int = 1024) -> AskResult: ...

    def ask_batch(
        self, docs: list[DocInput], prompts: list[str], max_tokens: int = 3000
    ) -> list[AskResult]:
        """Answer N independent prompts against the same document set in a single
        underlying LLM call instead of N separate ones — used where a free-tier
        rate limit (requests/minute) is the binding constraint, not tokens. Returns
        one AskResult per prompt, in the same order."""
        ...


class ProviderCallError(Exception):
    """Raised when a call to an LLM provider fails after retries. Route
    handlers catch this and turn it into a clean HTTP error instead of a
    raw 500 with an SDK stack trace."""
