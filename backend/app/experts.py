"""Static metadata for the 3 experts in this case pack.

Keeping this hardcoded (rather than parsed from the transcript header) is a
deliberate small tradeoff for reliability in a 3-transcript demo. At scale
(30+ transcripts) this would move into a manifest/DB row created at ingest
time instead of being hand-maintained.
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

EXPERTS = [
    {
        "id": "france",
        "name": "Dr. Jean Martin",
        "role": "Head of Urology",
        "market": "France",
        "file": DATA_DIR / "Transcript_1_France.txt",
    },
    {
        "id": "germany",
        "name": "Anna Keller",
        "role": "Former Hospital Procurement Director",
        "market": "Germany",
        "file": DATA_DIR / "Transcript_2_Germany.txt",
    },
    {
        "id": "uk",
        "name": "Dr. Emily Carter",
        "role": "Consultant Urologist",
        "market": "United Kingdom",
        "file": DATA_DIR / "Transcript_3_UK.txt",
    },
]

INTERVIEW_GUIDE_FILE = DATA_DIR / "Interview_Guide.txt"


def get_expert(expert_id: str) -> dict:
    for e in EXPERTS:
        if e["id"] == expert_id:
            return e
    raise KeyError(f"Unknown expert id: {expert_id}")
