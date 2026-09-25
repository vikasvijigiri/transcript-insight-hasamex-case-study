"""Parses a raw transcript .txt file into timestamped segments AND keeps the
exact raw text around, because a verified quote's char offset (found by a
literal substring search) is only meaningful against the *exact* text we sent
to the model.

We never re-format or clean the transcript before sending it to the model —
whatever bytes we parse here are the same bytes sent as the citation source,
so a citation's start_char_index always resolves correctly back to a
timestamp.
"""

import re
from dataclasses import dataclass
from pathlib import Path

TIMESTAMP_RE = re.compile(r"^(\d{2}:\d{2})\s*$")


@dataclass
class Segment:
    timestamp: str
    start_char: int  # offset into the raw transcript text where this segment begins


@dataclass
class Transcript:
    expert_id: str
    raw_text: str
    segments: list[Segment]

    def timestamp_for_offset(self, char_offset: int) -> str:
        """Nearest timestamp marker at or before char_offset. Falls back to the
        first timestamp if the offset is before any marker (shouldn't happen
        in practice since headers precede the first timestamp)."""
        best = self.segments[0].timestamp if self.segments else "00:00"
        for seg in self.segments:
            if seg.start_char <= char_offset:
                best = seg.timestamp
            else:
                break
        return best


def parse_transcript(expert_id: str, file_path: Path) -> Transcript:
    raw_text = file_path.read_text(encoding="utf-8")
    lines = raw_text.splitlines(keepends=True)

    segments: list[Segment] = []
    offset = 0
    for line in lines:
        stripped = line.rstrip("\n").rstrip("\r")
        m = TIMESTAMP_RE.match(stripped)
        if m:
            # The segment "starts" right after this timestamp line, since the
            # timestamp itself is just a marker, not part of the spoken text.
            segments.append(Segment(timestamp=m.group(1), start_char=offset + len(line)))
        offset += len(line)

    return Transcript(expert_id=expert_id, raw_text=raw_text, segments=segments)


_CACHE: dict[str, Transcript] = {}


def load_transcript(expert_id: str, file_path: Path) -> Transcript:
    if expert_id not in _CACHE:
        _CACHE[expert_id] = parse_transcript(expert_id, file_path)
    return _CACHE[expert_id]
