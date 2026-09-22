"""Golden regression set for the transcript-QA pipeline.

Two kinds of cases:
- "guide" cases: the 6 real interview-guide questions, once per expert —
  each MUST be answered and grounded, since the transcripts do address all
  six for all three experts.
- "trap" cases: plausible-sounding questions that are NOT answered anywhere
  in the transcripts. These are the most important check for the case
  study's "do not invent information" requirement — a good pipeline
  refuses these instead of guessing, and never fabricates a supporting
  quote to back up a guess.
"""

from dataclasses import dataclass


@dataclass
class EvalCase:
    id: str
    expert_id: str  # "france" | "germany" | "uk" | "all" (all 3 docs, chat-style)
    question: str
    expect_grounded: bool  # True: must return >=1 verified citation
    notes: str = ""


TRAP_CASES = [
    EvalCase(
        id="trap-france-pricing",
        expert_id="france",
        question="What is the list price of the robotic surgery system in France?",
        expect_grounded=False,
        notes="No price figure is stated anywhere in the France transcript.",
    ),
    EvalCase(
        id="trap-germany-competitor",
        expert_id="germany",
        question="Which specific robotic surgery vendor does the hospital prefer?",
        expect_grounded=False,
        notes="No vendor/brand name appears in the Germany transcript.",
    ),
    EvalCase(
        id="trap-uk-covid",
        expert_id="uk",
        question="How did COVID-19 affect robotic surgery adoption in the UK?",
        expect_grounded=False,
        notes="COVID is never mentioned in the UK transcript.",
    ),
    EvalCase(
        id="trap-cross-market-share",
        expert_id="all",
        question="What percentage market share does each country currently hold?",
        expect_grounded=False,
        notes="No market-share figures are given by any of the 3 experts.",
    ),
]


def guide_cases(expert_ids: list[str], questions: list[str]) -> list[EvalCase]:
    cases = []
    for expert_id in expert_ids:
        for i, q in enumerate(questions):
            cases.append(
                EvalCase(
                    id=f"guide-{expert_id}-{i + 1}",
                    expert_id=expert_id,
                    question=q,
                    expect_grounded=True,
                    notes="Interview-guide question — the transcript does address this.",
                )
            )
    return cases


def all_cases() -> list[EvalCase]:
    from app.experts import EXPERTS, INTERVIEW_GUIDE_FILE
    from app.interview_guide import load_questions

    expert_ids = [e["id"] for e in EXPERTS]
    questions = load_questions(INTERVIEW_GUIDE_FILE)
    return guide_cases(expert_ids, questions) + TRAP_CASES
