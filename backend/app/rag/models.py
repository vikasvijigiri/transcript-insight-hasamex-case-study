"""Stable domain types shared by ingestion, retrieval, and grounding."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceTurn:
    """An immutable, timestamped atomic evidence unit from a source record."""

    id: str
    source_id: str
    text: str
    speaker: str
    timestamp: str
    raw_start: int
    raw_end: int
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Passage:
    """A retrieval unit which retains links to its underlying source turns."""

    id: str
    source_id: str
    text: str
    turn_ids: tuple[str, ...]
    start_timestamp: str
    end_timestamp: str
    raw_start: int
    raw_end: int
    parent_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParentContext:
    id: str
    source_id: str
    text: str
    passage_ids: tuple[str, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    passage: Passage
    score: float
    rank: int
    channel: str


@dataclass(frozen=True)
class EvidenceBundle:
    """The compact, traceable context passed to a generation model."""

    passage: Passage
    context: str
    retrieval_score: float


@dataclass(frozen=True)
class CitationDraft:
    claim_id: str
    source_id: str
    quote: str
    passage_id: str | None = None
    raw_start: int | None = None


@dataclass(frozen=True)
class ClaimDraft:
    id: str
    text: str
    material: bool = True


@dataclass(frozen=True)
class GroundedResponseDraft:
    answer: str
    claims: Sequence[ClaimDraft]
    citations: Sequence[CitationDraft]


@dataclass(frozen=True)
class ValidatedCitation:
    claim_id: str
    source_id: str
    quote: str
    raw_start: int
    raw_end: int
    timestamp: str


@dataclass(frozen=True)
class GroundingResult:
    valid: bool
    citations: Sequence[ValidatedCitation]
    errors: Sequence[str]
