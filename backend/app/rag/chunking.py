"""Turn-aware transcript chunking that never loses citation offsets."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from app.rag.models import ParentContext, Passage, SourceTurn
from app.transcript_parser import Transcript

_SPEAKER_LINE = re.compile(r"^(?P<speaker>[^:\n]{1,100}):\s*(?P<text>.+)$", re.MULTILINE)
_TIMESTAMP_LINE = re.compile(r"^\d{2}:\d{2}\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ChunkedTranscript:
    turns: tuple[SourceTurn, ...]
    passages: tuple[Passage, ...]
    parents: tuple[ParentContext, ...]


class TranscriptChunker:
    """Builds passage/parent hierarchies from timestamped interview calls.

    The implementation uses conservative word budgets rather than splitting
    arbitrary characters. A production semantic segmenter can replace only
    this class while preserving the same source-span contract.
    """

    def __init__(self, passage_words: int = 110, parent_passages: int = 4) -> None:
        if passage_words < 20 or parent_passages < 1:
            raise ValueError("passage_words must be >= 20 and parent_passages >= 1")
        self.passage_words = passage_words
        self.parent_passages = parent_passages

    def chunk(
        self, transcript: Transcript, metadata: Mapping[str, str] | None = None
    ) -> ChunkedTranscript:
        shared = dict(metadata or {})
        turns = self._turns(transcript, shared)
        passages = self._passages(turns, shared)
        parents = self._parents(passages, shared)
        return ChunkedTranscript(tuple(turns), tuple(passages), tuple(parents))

    def _turns(self, transcript: Transcript, metadata: Mapping[str, str]) -> list[SourceTurn]:
        # Header fields such as ``Role:`` and ``Market:`` resemble speaker
        # labels. Only lines following the first call timestamp are turns.
        first_call_offset = transcript.segments[0].start_char if transcript.segments else 0
        matches = [
            match
            for match in _SPEAKER_LINE.finditer(transcript.raw_text)
            if match.start() >= first_call_offset and not match.group("speaker").strip().isdigit()
        ]
        timestamp_starts = [
            match.start() for match in _TIMESTAMP_LINE.finditer(transcript.raw_text)
        ]
        turns: list[SourceTurn] = []
        for match in matches:
            start = match.start()
            end = next(
                (marker_start for marker_start in timestamp_starts if marker_start > start),
                len(transcript.raw_text),
            )
            text = transcript.raw_text[start:end].strip()
            if not text:
                continue
            turns.append(
                SourceTurn(
                    id=f"{transcript.expert_id}:turn:{len(turns)}",
                    source_id=transcript.expert_id,
                    text=text,
                    speaker=match.group("speaker").strip(),
                    timestamp=transcript.timestamp_for_offset(start),
                    raw_start=start,
                    raw_end=end,
                    metadata=metadata,
                )
            )
        return turns

    def _passages(self, turns: list[SourceTurn], metadata: Mapping[str, str]) -> list[Passage]:
        passages: list[Passage] = []
        current: list[SourceTurn] = []
        words = 0
        for turn in turns:
            count = len(turn.text.split())
            if current and words + count > self.passage_words:
                passages.append(self._make_passage(current, len(passages), metadata))
                current, words = [], 0
            current.append(turn)
            words += count
        if current:
            passages.append(self._make_passage(current, len(passages), metadata))
        return passages

    @staticmethod
    def _make_passage(turns: list[SourceTurn], index: int, metadata: Mapping[str, str]) -> Passage:
        return Passage(
            id=f"{turns[0].source_id}:passage:{index}",
            source_id=turns[0].source_id,
            text="\n".join(turn.text for turn in turns),
            turn_ids=tuple(turn.id for turn in turns),
            start_timestamp=turns[0].timestamp,
            end_timestamp=turns[-1].timestamp,
            raw_start=turns[0].raw_start,
            raw_end=turns[-1].raw_end,
            parent_id=None,
            metadata=metadata,
        )

    def _parents(self, passages: list[Passage], metadata: Mapping[str, str]) -> list[ParentContext]:
        parents: list[ParentContext] = []
        for start in range(0, len(passages), self.parent_passages):
            group = passages[start : start + self.parent_passages]
            parents.append(
                ParentContext(
                    id=f"{group[0].source_id}:parent:{len(parents)}",
                    source_id=group[0].source_id,
                    text="\n\n".join(passage.text for passage in group),
                    passage_ids=tuple(passage.id for passage in group),
                    metadata=metadata,
                )
            )
        return parents
