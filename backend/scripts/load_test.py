"""Measure how latency and LLM usage behave as concurrent users grow.

Fires bursts of N simultaneous users asking the same question and reports latency
percentiles plus how many LLM calls the burst actually caused (read from the API's
own /api/observability counters). With the content-addressed cache and request
coalescing, the first burst makes one LLM call no matter how many users are in it,
and every later burst makes none.

Usage (API running locally in no-auth mode):
    python scripts/load_test.py --users 1 10 50 100
    python scripts/load_test.py --users 50 --question "What are the main barriers?"
"""

import argparse
import json
import statistics
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor


def _request(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def _timed_ask(base: str, question: str) -> tuple[float, int]:
    started = time.perf_counter()
    body = _request(f"{base}/api/projects/Robotics/ask", {"question": question})
    return (time.perf_counter() - started) * 1000, len(body.get("citations", []))


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--users", type=int, nargs="+", default=[1, 10, 50, 100])
    parser.add_argument(
        "--question",
        default="How long does it take a hospital to decide on buying a robotic system?",
    )
    parser.add_argument(
        "--reuse-cache",
        action="store_true",
        help="Do not tag the question with a run id (the first burst may already be cached).",
    )
    args = parser.parse_args()

    # A unique run tag makes the first burst genuinely cold, so the demo shows one
    # LLM call serving the whole burst rather than a result cached by an earlier run.
    question = (
        args.question if args.reuse_cache else f"{args.question} (load test {uuid.uuid4().hex[:6]})"
    )

    print(f"question: {question}\n")
    print(f"{'users':>6} {'p50 ms':>9} {'p95 ms':>9} {'max ms':>9} {'LLM calls':>10} {'cited':>6}")
    for users in args.users:
        before = _request(f"{args.base}/api/observability")["llmCalls"]
        with ThreadPoolExecutor(max_workers=users) as pool:
            results = list(pool.map(lambda _: _timed_ask(args.base, question), range(users)))
        after = _request(f"{args.base}/api/observability")["llmCalls"]
        latencies = [latency for latency, _ in results]
        cited = statistics.mode(count for _, count in results)
        print(
            f"{users:>6} {_percentile(latencies, 50):>9.0f} {_percentile(latencies, 95):>9.0f} "
            f"{max(latencies):>9.0f} {after - before:>10} {cited:>6}"
        )


if __name__ == "__main__":
    main()
