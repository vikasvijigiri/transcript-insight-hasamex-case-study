"""Parses the interview-guide questions out of Interview_Guide.txt so the
question list has a single source of truth (the file HR sent us) instead of
being retyped into code."""

import re
from pathlib import Path

QUESTION_RE = re.compile(r"^\d+\.\s+(.*)$")


def load_questions(file_path: Path) -> list[str]:
    text = file_path.read_text(encoding="utf-8")
    questions = []
    for line in text.splitlines():
        m = QUESTION_RE.match(line.strip())
        if m:
            questions.append(m.group(1).strip())
    return questions
