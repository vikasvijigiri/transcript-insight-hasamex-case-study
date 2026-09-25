"""Content-addressed analysis cache with request coalescing.

This is what keeps inference cost and latency flat as users grow:

* Keys are derived from the exact model input (source text, prompt version,
  provider, model), never from who asked. The first user to request an analysis
  pays for the LLM call; every later user with the same sources gets a cache hit.
  No tenant data can leak through a hit: it requires the identical source text,
  which that caller already holds.
* ``get_or_compute`` coalesces concurrent identical requests ("single-flight"):
  N simultaneous requests for the same uncached analysis produce one LLM call,
  and the other N-1 wait for its result instead of each calling the model.

Results live in Redis when ``REDIS_URL`` is set (shared across replicas) and in
local JSON files otherwise. Coalescing is per process; across replicas the same
pattern would take a Redis ``SET NX`` lock.
"""

import hashlib
import json
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from .observability import record_cache

CACHE_SCHEMA_VERSION = "v3"
CACHE_DIR = Path(__file__).parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _redis() -> Redis | None:
    """Use shared Redis when configured; keep files only for zero-config local work."""
    url = os.getenv("REDIS_URL", "").strip()
    return Redis.from_url(url, decode_responses=True) if url else None


def build_key(*parts: str) -> str:
    """Create a filesystem-safe key without leaking prompt or source text."""
    material = "\x1f".join((CACHE_SCHEMA_VERSION, *parts)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def read_cache(key: str) -> dict[str, Any] | None:
    client = _redis()
    if client:
        try:
            payload = client.get(f"hasamex:analysis:{key}")
            return json.loads(payload) if payload else None
        except RedisError:
            # Cache availability must never prevent evidence retrieval.
            pass
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cache(key: str, data: dict[str, Any]) -> None:
    """Write atomically so readers never observe partially-written JSON."""
    client = _redis()
    if client:
        try:
            client.set(f"hasamex:analysis:{key}", json.dumps(data, sort_keys=True))
            return
        except RedisError:
            pass
    path = CACHE_DIR / f"{key}.json"
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary_path, path)


_inflight: dict[str, threading.Lock] = {}
_inflight_guard = threading.Lock()


def get_or_compute(
    key: str,
    compute: Callable[[], dict[str, Any]],
    *,
    refresh: bool = False,
    cacheable: Callable[[dict[str, Any]], bool] = lambda _: True,
) -> dict[str, Any]:
    """Return the cached analysis for ``key`` or compute it exactly once.

    Concurrent callers with the same key share one computation: the first takes
    the key's lock and calls ``compute``; the rest block on that lock and then
    read the freshly written result. Failures are never cached, so a transient
    provider error is retried by the next request.
    """
    if not refresh:
        cached = read_cache(key)
        if cached is not None:
            record_cache("hit")
            return cached
    with _inflight_guard:
        lock = _inflight.setdefault(key, threading.Lock())
    with lock:
        if not refresh:
            cached = read_cache(key)
            if cached is not None:
                record_cache("coalesced")
                return cached
        record_cache("miss")
        try:
            result = compute()
            if cacheable(result):
                write_cache(key, result)
            return result
        finally:
            with _inflight_guard:
                if _inflight.get(key) is lock:
                    del _inflight[key]
