"""Deterministic, provider-independent RAG evaluation contracts.

These checks deliberately do not ask an LLM to judge another LLM. They are
used both by offline benchmarks and by request-time guardrails to prove the
properties that are mechanically provable for this product: citations point
to an immutable source span, retrieval contains the expected evidence, and an
answer abstains when the corpus does not support a claim.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EvidenceSpan:
    """An immutable, auditable span from an indexed source version."""

    evidence_id: str
    source_id: str
    source_version: str
    quote: str
    source_text: str
    start_char: int
    end_char: int
    timestamp: str | None = None
    market: str | None = None


@dataclass(frozen=True)
class CitationCheck:
    evidence_id: str
    valid: bool
    reason: str | None = None


@dataclass(frozen=True)
class RetrievalHit:
    """A ranked result consumed by deterministic retrieval metrics."""

    evidence_id: str
    source_id: str
    rank: int
    market: str | None = None


@dataclass(frozen=True)
class RetrievalMetrics:
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    unique_sources: int
    unique_markets: int

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


_ABSTENTION_RE = re.compile(
    r"\b(not (?:addressed|available|covered)|insufficient evidence|"
    r"cannot (?:answer|determine)|do not contain the answer)\b",
    re.IGNORECASE,
)


def validate_citation(span: EvidenceSpan) -> CitationCheck:
    """Verify an exact quote and offsets against the original source text.

    The offset is not treated as an LLM hint: it must precisely identify the
    displayed quote in the immutable source version. This catches both a
    fabricated quote and a real quote attributed to the wrong occurrence.
    """

    if not span.quote.strip():
        return CitationCheck(span.evidence_id, False, "Citation quote is empty.")
    if span.start_char < 0 or span.end_char < span.start_char:
        return CitationCheck(span.evidence_id, False, "Citation offsets are invalid.")
    if span.end_char > len(span.source_text):
        return CitationCheck(span.evidence_id, False, "Citation end offset exceeds source length.")
    selected_text = span.source_text[span.start_char : span.end_char]
    if selected_text != span.quote:
        return CitationCheck(
            span.evidence_id,
            False,
            "Citation quote does not match the declared source offsets.",
        )
    return CitationCheck(span.evidence_id, True)


def citation_completeness(claim_count: int, cited_claim_count: int) -> float:
    """Return the proportion of material claims carrying verified evidence."""

    if claim_count < 0 or cited_claim_count < 0:
        raise ValueError("Claim counts cannot be negative.")
    if cited_claim_count > claim_count:
        raise ValueError("Cited claim count cannot exceed total claim count.")
    return 1.0 if claim_count == 0 else cited_claim_count / claim_count


def is_valid_abstention(answer: str, citation_count: int) -> bool:
    """An unsupported answer must explicitly abstain and cite no evidence."""

    return citation_count == 0 and bool(_ABSTENTION_RE.search(answer))


def evaluate_retrieval(
    hits: Iterable[RetrievalHit], expected_evidence_ids: set[str], k: int
) -> RetrievalMetrics:
    """Calculate retrieval quality and diversity from a labelled golden case."""

    if k < 1:
        raise ValueError("k must be at least 1.")
    ranked_hits = sorted(hits, key=lambda hit: hit.rank)[:k]
    relevant_ranks = [
        index + 1
        for index, hit in enumerate(ranked_hits)
        if hit.evidence_id in expected_evidence_ids
    ]
    retrieved_ids = {hit.evidence_id for hit in ranked_hits}
    recall = (
        len(retrieved_ids & expected_evidence_ids) / len(expected_evidence_ids)
        if expected_evidence_ids
        else 1.0
    )
    mrr = 1.0 / relevant_ranks[0] if relevant_ranks else 0.0
    dcg = sum(1.0 / math.log2(rank + 1) for rank in relevant_ranks)
    ideal_count = min(len(expected_evidence_ids), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    ndcg = dcg / ideal_dcg if ideal_dcg else 1.0
    return RetrievalMetrics(
        recall_at_k=round(recall, 4),
        mrr=round(mrr, 4),
        ndcg_at_k=round(ndcg, 4),
        unique_sources=len({hit.source_id for hit in ranked_hits}),
        unique_markets=len({hit.market for hit in ranked_hits if hit.market}),
    )
