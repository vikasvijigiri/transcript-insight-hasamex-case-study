"""Idempotent transcript ingestion with timestamp- and speaker-safe chunking."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Call, DocumentVersion, ParentSection, Passage, Speaker, Turn
from app.repositories import EvidenceRepository

TIMESTAMP_LINE = re.compile(r"^(?P<time>\d{2}:\d{2})\s*$")
SPEAKER_LINE = re.compile(r"^(?P<speaker>[^:\n]{1,100}):\s*(?P<text>.+)$")


@dataclass(frozen=True)
class ParsedTurn:
    ordinal: int
    timestamp: str
    speaker: str | None
    text: str
    start_char: int
    end_char: int


def token_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def parse_turns(raw_text: str) -> list[ParsedTurn]:
    """Parse a transcript without altering source offsets or quoted text."""
    lines = raw_text.splitlines(keepends=True)
    items: list[ParsedTurn] = []
    offset = 0
    current_timestamp = "00:00"
    has_timestamp = False
    for line in lines:
        content = line.rstrip("\r\n")
        timestamp = TIMESTAMP_LINE.match(content)
        if timestamp:
            current_timestamp = timestamp.group("time")
            has_timestamp = True
        else:
            speaker = SPEAKER_LINE.match(content)
            # Header metadata such as "Market: France" is not a spoken turn.
            if has_timestamp and speaker:
                items.append(
                    ParsedTurn(
                        len(items),
                        current_timestamp,
                        speaker.group("speaker"),
                        content,
                        offset,
                        offset + len(content),
                    )
                )
        offset += len(line)
    return items


def _group_turns(turns: list[Turn], max_tokens: int) -> list[list[Turn]]:
    groups: list[list[Turn]] = []
    current: list[Turn] = []
    current_size = 0
    for turn in turns:
        size = token_count(turn.raw_text)
        if current and current_size + size > max_tokens:
            groups.append(current)
            current, current_size = [], 0
        current.append(turn)
        current_size += size
    if current:
        groups.append(current)
    return groups


@dataclass(frozen=True)
class IngestionResult:
    document_version: DocumentVersion
    created: bool
    turn_count: int
    passage_count: int


class TranscriptIngestionService:
    def __init__(
        self, session: Session, passage_max_tokens: int = 420, parent_max_tokens: int = 1800
    ):
        self.session = session
        self.repo = EvidenceRepository(session)
        self.passage_max_tokens = passage_max_tokens
        self.parent_max_tokens = parent_max_tokens

    def ingest_file(self, **kwargs: str) -> IngestionResult:
        path = Path(kwargs.pop("path"))
        return self.ingest_text(
            raw_text=path.read_text(encoding="utf-8"),
            filename=path.name,
            external_key=str(path),
            **kwargs,
        )

    def ingest_text(
        self,
        *,
        tenant_id: str,
        project_name: str,
        external_key: str,
        filename: str,
        expert_id: str,
        raw_text: str,
        market: str | None = None,
        role: str | None = None,
    ) -> IngestionResult:
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        project = self.repo.get_or_create_project(tenant_id, project_name)
        source = self.repo.get_or_create_source(project, external_key, filename)
        existing = self.repo.existing_version(source, content_hash)
        if existing is not None:
            call = self.session.scalar(select(Call).where(Call.document_version_id == existing.id))
            if call is None:
                raise RuntimeError(f"Document version {existing.id} has no associated call")
            turn_count = (
                self.session.scalar(
                    select(func.count()).select_from(Turn).where(Turn.call_id == call.id)
                )
                or 0
            )
            passage_count = (
                self.session.scalar(
                    select(func.count()).select_from(Passage).where(Passage.call_id == call.id)
                )
                or 0
            )
            return IngestionResult(
                existing,
                False,
                turn_count,
                passage_count,
            )

        version_number = (
            self.session.scalar(
                select(func.max(DocumentVersion.version_number)).where(
                    DocumentVersion.source_document_id == source.id
                )
            )
            or 0
        ) + 1
        version = DocumentVersion(
            source_document_id=source.id,
            version_number=version_number,
            content_hash=content_hash,
            raw_text=raw_text,
        )
        self.session.add(version)
        self.session.flush()
        call = Call(document_version_id=version.id, expert_id=expert_id, market=market, role=role)
        self.session.add(call)
        self.session.flush()
        speakers: dict[str, Speaker] = {}
        persisted_turns: list[Turn] = []
        for parsed in parse_turns(raw_text):
            speaker_id = None
            if parsed.speaker:
                speaker = speakers.get(parsed.speaker)
                if speaker is None:
                    speaker = Speaker(call_id=call.id, name=parsed.speaker)
                    self.session.add(speaker)
                    self.session.flush()
                    speakers[parsed.speaker] = speaker
                speaker_id = speaker.id
            turn = Turn(
                call_id=call.id,
                speaker_id=speaker_id,
                ordinal=parsed.ordinal,
                start_timestamp=parsed.timestamp,
                start_char=parsed.start_char,
                end_char=parsed.end_char,
                raw_text=parsed.text,
            )
            self.session.add(turn)
            persisted_turns.append(turn)
        self.session.flush()
        parents = _group_turns(persisted_turns, self.parent_max_tokens)
        passages: list[Passage] = []
        for parent_ordinal, parent_turns in enumerate(parents):
            parent = ParentSection(
                call_id=call.id,
                ordinal=parent_ordinal,
                start_turn_ordinal=parent_turns[0].ordinal,
                end_turn_ordinal=parent_turns[-1].ordinal,
                text="\n".join(turn.raw_text for turn in parent_turns),
            )
            self.session.add(parent)
            self.session.flush()
            for passage_turns in _group_turns(parent_turns, self.passage_max_tokens):
                passage = Passage(
                    parent_section_id=parent.id,
                    call_id=call.id,
                    ordinal=len(passages),
                    start_turn_ordinal=passage_turns[0].ordinal,
                    end_turn_ordinal=passage_turns[-1].ordinal,
                    start_char=passage_turns[0].start_char,
                    end_char=passage_turns[-1].end_char,
                    text="\n".join(turn.raw_text for turn in passage_turns),
                )
                self.session.add(passage)
                passages.append(passage)
        self.session.commit()
        return IngestionResult(version, True, len(persisted_turns), len(passages))
