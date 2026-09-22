"""Tiny disk cache for the pre-computable results (per-expert Q&A, cross-expert
themes). This exists for two practical reasons for a demo app:
  1. Reproducibility — the answers shown in the recorded demo video don't
     change if the endpoint is hit again.
  2. Cost/latency — re-running the full extraction on every page load would
     mean 18+ live API calls just to render the main screen.
Pass ?refresh=true to bypass the cache and recompute against the live API.
"""

import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def read_cache(key: str):
    f = CACHE_DIR / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return None


def write_cache(key: str, data) -> None:
    f = CACHE_DIR / f"{key}.json"
    f.write_text(json.dumps(data, indent=2), encoding="utf-8")
