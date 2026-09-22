"""Offline regression / groundedness eval for the transcript-QA pipeline.

Run manually — it makes real API calls, so it is intentionally NOT part of
the `pytest` suite (no network calls in unit tests):

    python -m evals.run_eval                      # uses LLM_PROVIDER from .env
    python -m evals.run_eval --provider groq       # override for one run
    python -m evals.run_eval --compare anthropic groq huggingface

For each golden case it asks the configured provider the question against
the relevant transcript(s), then checks:
  - "grounded" cases (the 6 real interview-guide questions): did at least
    one citation survive verbatim verification against the source text?
  - "trap" cases (questions the transcripts don't address): did the model
    correctly NOT produce a verified citation — i.e. did it avoid
    fabricating support for a guess?
A run is scored on pass rate AND on a separate "fabricated citations"
counter — a raw citation that fails verbatim verification is a hallucinated
quote that our guardrail caught before it reached a user; tracking it over
time/providers/models is the actual faithfulness metric for this app.

Results are written to evals/results/eval-<timestamp>.json so provider/model
changes can be compared like any other regression suite.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings  # noqa: E402
from app.experts import EXPERTS, get_expert  # noqa: E402
from app.providers import build_provider  # noqa: E402
from app.providers.types import DocInput  # noqa: E402
from app.transcript_parser import load_transcript  # noqa: E402
from evals.golden_cases import EvalCase, all_cases  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"
MODEL_ATTR = {"anthropic": "claude_model", "groq": "groq_model", "huggingface": "hf_model"}


def _docs_for(expert_id: str) -> list[DocInput]:
    experts = EXPERTS if expert_id == "all" else [get_expert(expert_id)]
    docs = []
    for e in experts:
        t = load_transcript(e["id"], e["file"])
        docs.append(
            DocInput(expert_id=e["id"], title=f"{e['name']} ({e['market']})", text=t.raw_text)
        )
    return docs


def _verify(quote: str, expert_id: str) -> bool:
    experts = EXPERTS if expert_id == "all" else [get_expert(expert_id)]
    return any(quote.strip() in load_transcript(e["id"], e["file"]).raw_text for e in experts)


def run_case(provider, case: EvalCase) -> dict:
    docs = _docs_for(case.expert_id)
    prompt = (
        f'Question: "{case.question}"\n\n'
        "Answer using ONLY the transcript document(s) provided. If it isn't addressed, "
        'say exactly "Not addressed in the transcript(s)."'
    )
    result = provider.ask(docs, prompt, max_tokens=400)
    verified = [c for c in result.raw_citations if _verify(c.cited_text, case.expert_id)]
    fabricated = len(result.raw_citations) - len(verified)
    is_grounded = len(verified) > 0
    passed = is_grounded == case.expect_grounded and fabricated == 0

    return {
        "id": case.id,
        "expect_grounded": case.expect_grounded,
        "is_grounded": is_grounded,
        "fabricated_citations": fabricated,
        "passed": passed,
        "answer": result.answer_text,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }


def run(provider_name: str) -> dict:
    settings = Settings(llm_provider=provider_name)
    provider = build_provider(settings)
    cases = all_cases()

    rows = [run_case(provider, c) for c in cases]
    passed = sum(r["passed"] for r in rows)
    fabricated_total = sum(r["fabricated_citations"] for r in rows)

    return {
        "provider": provider_name,
        "model": getattr(settings, MODEL_ATTR.get(provider_name, ""), ""),
        "total_cases": len(rows),
        "passed": passed,
        "pass_rate": round(passed / len(rows), 3),
        "fabricated_citations_total": fabricated_total,
        "avg_latency_ms": round(sum(r["latency_ms"] for r in rows) / len(rows)),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--provider", default=None, help="anthropic | groq | huggingface")
    parser.add_argument(
        "--compare", nargs="+", default=None, help="Run and compare multiple providers"
    )
    args = parser.parse_args()

    providers = args.compare or [args.provider or Settings().llm_provider]

    RESULTS_DIR.mkdir(exist_ok=True)
    summaries = []
    for p in providers:
        print(f"\n=== Running eval against provider: {p} ===")
        summary = run(p)
        summaries.append(summary)
        print(
            f"{p}: {summary['passed']}/{summary['total_cases']} passed "
            f"({summary['pass_rate']:.0%}), "
            f"{summary['fabricated_citations_total']} fabricated citation(s), "
            f"avg latency {summary['avg_latency_ms']}ms"
        )
        for r in summary["rows"]:
            if not r["passed"]:
                print(
                    f"  FAIL {r['id']}: expected_grounded={r['expect_grounded']} "
                    f"got_grounded={r['is_grounded']} fabricated={r['fabricated_citations']}"
                )

    ts = time.strftime("%Y%m%d-%H%M%S")
    out_file = RESULTS_DIR / f"eval-{ts}.json"
    out_file.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\nFull report written to {out_file}")


if __name__ == "__main__":
    main()
