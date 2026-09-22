from app.experts import EXPERTS
from app.transcript_parser import parse_transcript


def test_parses_all_timestamp_markers():
    transcript = parse_transcript("france", EXPERTS[0]["file"])
    # Transcript_1_France.txt has 14 "MM:SS" marker lines (7 Q + 7 A turns).
    assert len(transcript.segments) == 14
    assert transcript.segments[0].timestamp == "00:00"


def test_timestamp_for_offset_resolves_to_the_enclosing_segment():
    transcript = parse_transcript("france", EXPERTS[0]["file"])
    phrase = "Very important. The clinical argument"
    offset = transcript.raw_text.index(phrase)
    assert transcript.timestamp_for_offset(offset) == "02:18"


def test_timestamp_for_offset_before_any_marker_falls_back_to_first():
    transcript = parse_transcript("france", EXPERTS[0]["file"])
    assert transcript.timestamp_for_offset(0) == "00:00"


def test_raw_text_is_verbatim_source_file_content():
    transcript = parse_transcript("germany", EXPERTS[1]["file"])
    assert "Anna Keller" in transcript.raw_text
    # We must never alter the text we cite against, or char offsets returned
    # by the Citations API (or our own substring search) would drift.
    assert transcript.raw_text == EXPERTS[1]["file"].read_text(encoding="utf-8")
