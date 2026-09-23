"""Hybrid, hierarchical retrieval primitives with safe deterministic defaults."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

from app.rag.models import EvidenceBundle, ParentContext, Passage, SearchHit

_TOKEN = re.compile(r"\w+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    return _TOKEN.findall(value.casefold())


class LexicalRetriever(Protocol):
    def search(
        self, query: str, limit: int, filters: Mapping[str, str] | None = None
    ) -> list[SearchHit]: ...


class VectorRetriever(Protocol):
    def search(
        self, query: str, limit: int, filters: Mapping[str, str] | None = None
    ) -> list[SearchHit]: ...


class Reranker(Protocol):
    def score(self, query: str, passages: Sequence[Passage]) -> Mapping[str, float]: ...


def matches_filters(passage: Passage, filters: Mapping[str, str] | None) -> bool:
    """Return True only when every requested metadata filter matches exactly."""
    if not filters:
        return True
    searchable = {**passage.metadata, "source_id": passage.source_id}
    return all(searchable.get(key) == value for key, value in filters.items())


class InMemoryBM25:
    """Small BM25 implementation for local development and deterministic tests."""

    def __init__(self, passages: Sequence[Passage], k1: float = 1.5, b: float = 0.75) -> None:
        self.passages = tuple(passages)
        self.k1, self.b = k1, b
        self.docs = {passage.id: _tokens(passage.text) for passage in passages}
        self.avg_length = sum(map(len, self.docs.values())) / max(len(self.docs), 1)
        self.document_frequency: Counter[str] = Counter()
        for tokens in self.docs.values():
            self.document_frequency.update(set(tokens))

    def search(
        self, query: str, limit: int, filters: Mapping[str, str] | None = None
    ) -> list[SearchHit]:
        query_tokens = _tokens(query)
        scored: list[tuple[Passage, float]] = []
        count = len(self.passages)
        for passage in self.passages:
            if not matches_filters(passage, filters):
                continue
            terms, length = Counter(self.docs[passage.id]), len(self.docs[passage.id])
            score = 0.0
            for term in query_tokens:
                df = self.document_frequency[term]
                if not df:
                    continue
                idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
                score += (
                    idf
                    * (terms[term] * (self.k1 + 1))
                    / (terms[term] + self.k1 * (1 - self.b + self.b * length / self.avg_length))
                )
            if score:
                scored.append((passage, score))
        scored.sort(key=lambda item: (-item[1], item[0].id))
        return [
            SearchHit(passage, score, index + 1, "lexical")
            for index, (passage, score) in enumerate(scored[:limit])
        ]


class HashingVectorSearch:
    """Dependency-free semantic fallback; replace with a real embedding index in production."""

    def __init__(self, passages: Sequence[Passage], dimensions: int = 256) -> None:
        self.passages = tuple(passages)
        self.dimensions = dimensions
        self.vectors = {passage.id: self._embed(passage.text) for passage in passages}

    def _embed(self, text: str) -> dict[int, float]:
        vector: defaultdict[int, float] = defaultdict(float)
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector.values()))
        return {key: value / norm for key, value in vector.items()} if norm else {}

    def search(
        self, query: str, limit: int, filters: Mapping[str, str] | None = None
    ) -> list[SearchHit]:
        query_vector = self._embed(query)
        scored = []
        for passage in self.passages:
            if not matches_filters(passage, filters):
                continue
            score = sum(
                value * self.vectors[passage.id].get(key, 0.0)
                for key, value in query_vector.items()
            )
            if score:
                scored.append((passage, score))
        scored.sort(key=lambda item: (-item[1], item[0].id))
        return [
            SearchHit(passage, score, index + 1, "vector")
            for index, (passage, score) in enumerate(scored[:limit])
        ]


def reciprocal_rank_fusion(
    result_sets: Iterable[Sequence[SearchHit]], k: int = 60
) -> list[SearchHit]:
    """Fuse independently ranked channels without assuming comparable scores."""
    scores: defaultdict[str, float] = defaultdict(float)
    passages: dict[str, Passage] = {}
    for result_set in result_sets:
        for hit in result_set:
            scores[hit.passage.id] += 1 / (k + hit.rank)
            passages[hit.passage.id] = hit.passage
    ordered = sorted(scores, key=lambda passage_id: (-scores[passage_id], passage_id))
    return [
        SearchHit(passages[pid], scores[pid], rank + 1, "hybrid")
        for rank, pid in enumerate(ordered)
    ]


class LexicalOverlapReranker:
    """Safe fallback reranker; production adapters should use a cross-encoder."""

    def score(self, query: str, passages: Sequence[Passage]) -> Mapping[str, float]:
        query_terms = set(_tokens(query))
        return {
            passage.id: len(query_terms.intersection(_tokens(passage.text)))
            / max(len(query_terms), 1)
            for passage in passages
        }


def diversify_hits(
    hits: Sequence[SearchHit], limit: int, max_per_source: int = 2
) -> list[SearchHit]:
    """Prevent a single long call from monopolising an answer's evidence."""
    chosen: list[SearchHit] = []
    source_counts: Counter[str] = Counter()
    for hit in hits:
        if source_counts[hit.passage.source_id] >= max_per_source:
            continue
        chosen.append(hit)
        source_counts[hit.passage.source_id] += 1
        if len(chosen) == limit:
            break
    return chosen


def max_marginal_relevance(
    hits: Sequence[SearchHit], limit: int, relevance: Mapping[str, float], lambda_mult: float = 0.75
) -> list[SearchHit]:
    """Select relevant but non-duplicative passages using lexical MMR.

    A vector-store adapter can replace the Jaccard similarity below with its
    embedding cosine similarity without changing the orchestration contract.
    """
    if not 0.0 <= lambda_mult <= 1.0:
        raise ValueError("lambda_mult must be between 0 and 1")
    remaining = list(hits)
    chosen: list[SearchHit] = []
    token_sets = {hit.passage.id: set(_tokens(hit.passage.text)) for hit in hits}
    while remaining and len(chosen) < limit:

        def mmr_score(hit: SearchHit) -> tuple[float, str]:
            maximum_similarity = max(
                (
                    _jaccard(token_sets[hit.passage.id], token_sets[selected.passage.id])
                    for selected in chosen
                ),
                default=0.0,
            )
            return (
                lambda_mult * relevance.get(hit.passage.id, 0.0)
                - (1 - lambda_mult) * maximum_similarity,
                hit.passage.id,
            )

        best = max(remaining, key=mmr_score)
        chosen.append(best)
        remaining.remove(best)
    return chosen


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


class ContextPacker:
    """Adds parent context only after exact passages have been selected."""

    def __init__(self, parents: Sequence[ParentContext], max_characters: int = 9_000) -> None:
        self.by_passage = {
            passage_id: parent for parent in parents for passage_id in parent.passage_ids
        }
        self.max_characters = max_characters

    def pack(self, hits: Sequence[SearchHit]) -> list[EvidenceBundle]:
        bundles: list[EvidenceBundle] = []
        remaining = self.max_characters
        for hit in hits:
            parent = self.by_passage.get(hit.passage.id)
            context = parent.text if parent else hit.passage.text
            context = context[:remaining]
            if not context:
                break
            bundles.append(EvidenceBundle(hit.passage, context, hit.score))
            remaining -= len(context)
        return bundles


class HybridRetriever:
    """Orchestrates filtered BM25 + vector retrieval, RRF, reranking and packing."""

    def __init__(
        self,
        lexical: LexicalRetriever,
        vector: VectorRetriever,
        reranker: Reranker,
        packer: ContextPacker,
    ) -> None:
        self.lexical, self.vector, self.reranker, self.packer = lexical, vector, reranker, packer

    @classmethod
    def in_memory(
        cls, passages: Sequence[Passage], parents: Sequence[ParentContext]
    ) -> HybridRetriever:
        return cls(
            InMemoryBM25(passages),
            HashingVectorSearch(passages),
            LexicalOverlapReranker(),
            ContextPacker(parents),
        )

    def retrieve(
        self,
        query: str,
        filters: Mapping[str, str] | None = None,
        candidates_per_channel: int = 25,
        evidence_limit: int = 8,
        max_per_source: int = 2,
    ) -> list[EvidenceBundle]:
        lexical_hits = self.lexical.search(query, candidates_per_channel, filters)
        vector_hits = self.vector.search(query, candidates_per_channel, filters)
        fused = reciprocal_rank_fusion((lexical_hits, vector_hits))
        scores = self.reranker.score(query, [hit.passage for hit in fused])
        reranked = sorted(
            fused,
            key=lambda hit: (-scores.get(hit.passage.id, 0.0), -hit.score, hit.passage.id),
        )
        diverse = max_marginal_relevance(reranked, evidence_limit * 3, scores)
        return self.packer.pack(diversify_hits(diverse, evidence_limit, max_per_source))
