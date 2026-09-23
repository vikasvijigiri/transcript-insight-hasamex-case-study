from app.experts import EXPERTS
from app.rag.chunking import TranscriptChunker
from app.rag.grounding import GroundingValidator
from app.rag.models import CitationDraft, ClaimDraft, GroundedResponseDraft, ParentContext, Passage
from app.rag.retrieval import HybridRetriever, max_marginal_relevance, reciprocal_rank_fusion
from app.transcript_parser import parse_transcript


def _passage(identifier: str, source: str, text: str, market: str) -> Passage:
    return Passage(
        id=identifier,
        source_id=source,
        text=text,
        turn_ids=(),
        start_timestamp="01:00",
        end_timestamp="01:00",
        raw_start=0,
        raw_end=len(text),
        metadata={"market": market},
    )


def test_chunker_preserves_source_offsets_and_speaker_turns():
    transcript = parse_transcript("france", EXPERTS[0]["file"])
    output = TranscriptChunker(passage_words=45).chunk(transcript, {"market": "France"})
    assert output.turns[1].speaker == "Dr. Martin"
    assert (
        transcript.raw_text[output.turns[1].raw_start : output.turns[1].raw_end].strip()
        == output.turns[1].text
    )
    assert output.passages[0].metadata["market"] == "France"


def test_hybrid_retrieval_filters_and_diversifies_sources():
    france = _passage(
        "f1", "france", "ROI and maintenance cost decide the capital purchase", "France"
    )
    france_second = _passage("f2", "france", "ROI depends on utilisation volume", "France")
    germany = _passage("g1", "germany", "Procurement considers ROI and service cost", "Germany")
    parents = [
        ParentContext("pf", "france", france.text + "\n" + france_second.text, ("f1", "f2")),
        ParentContext("pg", "germany", germany.text, ("g1",)),
    ]
    retriever = HybridRetriever.in_memory([france, france_second, germany], parents)
    bundles = retriever.retrieve(
        "How does ROI affect purchase?", evidence_limit=3, max_per_source=1
    )
    assert {bundle.passage.source_id for bundle in bundles} == {"france", "germany"}
    filtered = retriever.retrieve("ROI", filters={"market": "Germany"})
    assert [bundle.passage.id for bundle in filtered] == ["g1"]


def test_rrf_rewards_documents_found_by_multiple_channels():
    passage = _passage("shared", "france", "ROI", "France")
    lexical_only = _passage("lexical", "uk", "ROI", "UK")
    from app.rag.models import SearchHit

    results = reciprocal_rank_fusion(
        (
            [SearchHit(passage, 0.9, 1, "lexical"), SearchHit(lexical_only, 0.8, 2, "lexical")],
            [SearchHit(passage, 0.2, 2, "vector")],
        )
    )
    assert results[0].passage.id == "shared"


def test_mmr_reduces_near_duplicate_passages():
    from app.rag.models import SearchHit

    first = _passage("first", "france", "ROI maintenance cost and utilisation", "France")
    duplicate = _passage("duplicate", "france", "ROI maintenance cost and utilisation", "France")
    distinct = _passage("distinct", "germany", "Clinical training affects adoption", "Germany")
    chosen = max_marginal_relevance(
        [
            SearchHit(first, 1, 1, "hybrid"),
            SearchHit(duplicate, 0.99, 2, "hybrid"),
            SearchHit(distinct, 0.7, 3, "hybrid"),
        ],
        2,
        {"first": 1, "duplicate": 0.99, "distinct": 0.7},
        lambda_mult=0.5,
    )
    assert [hit.passage.id for hit in chosen] == ["first", "distinct"]


def test_grounding_validator_rejects_unverifiable_or_uncited_claims():
    transcript = parse_transcript("france", EXPERTS[0]["file"])
    quote = "Very important. The clinical argument may get surgeons interested"
    valid = GroundingValidator({"france": transcript}).validate(
        GroundedResponseDraft(
            "ROI matters.",
            [ClaimDraft("roi", "ROI matters")],
            [CitationDraft("roi", "france", quote)],
        )
    )
    assert valid.valid
    assert valid.citations[0].timestamp == "02:18"
    invalid = GroundingValidator({"france": transcript}).validate(
        GroundedResponseDraft(
            "Answer",
            [ClaimDraft("roi", "ROI matters")],
            [CitationDraft("roi", "france", "Invented")],
        )
    )
    assert not invalid.valid
    assert any("no valid citation" in error for error in invalid.errors)
