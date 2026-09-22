"""These endpoints (Groq/HF) have no native citation feature, so this
provider's own verbatim-substring verification IS the grounding mechanism.
This test exists specifically to prove a fabricated quote can never survive
that check — that's the load-bearing guarantee for the whole "no
invented information" requirement on this code path."""

from app.providers.openai_compatible_provider import OpenAICompatibleProvider
from app.providers.types import DocInput

DOCS = [DocInput(expert_id="france", title="t", text="Adoption is growing steadily each year.")]


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        name="groq", base_url="http://unused", api_key="fake", model="m"
    )


def test_verbatim_quote_is_kept_with_correct_offset():
    provider = _provider()
    raw = (
        '{"answer": "It is growing.", '
        '"quotes": [{"document_index": 0, "quote": "Adoption is growing steadily each year."}]}'
    )
    answer, citations = provider._parse_and_verify(raw, DOCS)
    assert answer == "It is growing."
    assert len(citations) == 1
    assert citations[0].start_char_index == 0


def test_fabricated_quote_is_dropped_not_shown():
    provider = _provider()
    raw = (
        '{"answer": "It is growing.", '
        '"quotes": [{"document_index": 0, "quote": "a sentence that does not exist"}]}'
    )
    answer, citations = provider._parse_and_verify(raw, DOCS)
    assert answer == "It is growing."
    assert citations == []


def test_out_of_range_document_index_is_dropped():
    provider = _provider()
    raw = '{"answer": "x", "quotes": [{"document_index": 5, "quote": "Adoption is growing"}]}'
    _, citations = provider._parse_and_verify(raw, DOCS)
    assert citations == []


def test_malformed_json_falls_back_to_raw_text_with_no_citations():
    provider = _provider()
    answer, citations = provider._parse_and_verify("not json at all", DOCS)
    assert answer == "not json at all"
    assert citations == []
