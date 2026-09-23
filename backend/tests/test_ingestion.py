from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import initialize_database
from app.ingestion import TranscriptIngestionService, parse_turns
from app.models import Base, Call, Passage, Turn

SAMPLE = """Expert 1\nMarket: France\n\n00:00\nInterviewer: What is changing?\n\n00:15\nDr. Martin: Adoption is growing in larger hospitals.\n\n00:30\nDr. Martin: Budget approval and training remain key barriers.\n"""


def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_parse_turns_preserves_timestamp_and_source_offsets():
    turns = parse_turns(SAMPLE)
    assert [(turn.timestamp, turn.speaker) for turn in turns] == [
        ("00:00", "Interviewer"),
        ("00:15", "Dr. Martin"),
        ("00:30", "Dr. Martin"),
    ]
    assert SAMPLE[turns[1].start_char : turns[1].end_char] == turns[1].text


def test_ingestion_is_idempotent_and_builds_hierarchical_passages():
    db = session()
    service = TranscriptIngestionService(db, passage_max_tokens=8, parent_max_tokens=16)
    args = dict(
        tenant_id="acme",
        project_name="Robotics",
        external_key="call-1",
        filename="call.txt",
        expert_id="expert-1",
        raw_text=SAMPLE,
        market="France",
    )
    first = service.ingest_text(**args)
    second = service.ingest_text(**args)
    assert first.created is True
    assert second.created is False
    assert first.turn_count == 3
    assert len(db.scalars(select(Turn)).all()) == 3
    passages = db.scalars(select(Passage)).all()
    assert len(passages) >= 2
    call = db.scalar(select(Call))
    assert call is not None and call.market == "France"


def test_database_bootstrap_creates_the_evidence_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'evidence.db'}"
    initialize_database(database_url)
    engine = create_engine(database_url)
    assert engine.dialect.has_table(engine.connect(), "embeddings")
