from evals.contracts import (
    EvidenceSpan,
    RetrievalHit,
    citation_completeness,
    evaluate_retrieval,
    is_valid_abstention,
    validate_citation,
)


def test_citation_validation_requires_exact_declared_span():
    source = "The committee needs a clear business case before purchase."
    quote = "clear business case"
    start = source.index(quote)
    span = EvidenceSpan(
        evidence_id="evidence-1",
        source_id="call-fr-1",
        source_version="sha256:abc",
        quote=quote,
        source_text=source,
        start_char=start,
        end_char=start + len(quote),
        timestamp="02:18",
    )

    assert validate_citation(span).valid


def test_citation_validation_rejects_wrong_offset_even_for_real_quote():
    source = "ROI is important. ROI is important."
    span = EvidenceSpan(
        evidence_id="evidence-1",
        source_id="call-fr-1",
        source_version="sha256:abc",
        quote="ROI is important.",
        source_text=source,
        start_char=1,
        end_char=18,
    )

    check = validate_citation(span)
    assert not check.valid
    assert "offsets" in check.reason.lower()


def test_abstention_requires_explicit_language_and_no_citations():
    assert is_valid_abstention("Not addressed in the transcripts.", 0)
    assert not is_valid_abstention("I do not know.", 0)
    assert not is_valid_abstention("Not addressed in the transcripts.", 1)


def test_retrieval_metrics_measure_ranking_coverage_and_diversity():
    hits = [
        RetrievalHit("irrelevant", "uk-call", 1, "UK"),
        RetrievalHit("fr-evidence", "fr-call", 2, "France"),
        RetrievalHit("de-evidence", "de-call", 3, "Germany"),
    ]

    metrics = evaluate_retrieval(hits, {"fr-evidence", "de-evidence"}, k=3)

    assert metrics.recall_at_k == 1.0
    assert metrics.mrr == 0.5
    assert metrics.unique_sources == 3
    assert metrics.unique_markets == 3
    assert 0 < metrics.ndcg_at_k < 1


def test_citation_completeness_validates_counts():
    assert citation_completeness(4, 3) == 0.75
