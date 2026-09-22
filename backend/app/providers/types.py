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
    """Every provider (Anthropic Citations API, or an OpenAI-compatible OSS
    endpoint like Groq/HF) implements this one method. `main.py` only ever
    talks to this interface."""

    name: str

    def ask(self, docs: list[DocInput], prompt: str, max_tokens: int = 1024) -> AskResult: ...
