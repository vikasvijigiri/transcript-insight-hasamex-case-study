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
the ``analysis_cache`` database table otherwise, so they survive deploys and can
be shared between machines through ``CACHE_DATABASE_URL``. A small in-process
LRU sits in front of either store; keys are content-addressed, so a memory hit
can never be stale. Coalescing is per process; across replicas the same pattern
would take a Redis ``SET NX`` lock.
"""

import hashlib
import json
import logging
import os
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AnalysisCacheEntry
from .observability import record_cache

logger = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = "v3"
# Where analyses were stored before the cache moved into the database; read only
# by ``scripts/import_file_cache.py`` to carry old results forward.
LEGACY_CACHE_DIR = Path(__file__).parent / "data" / "cache"
MEMORY_CACHE_ENTRIES = 512

_memory: OrderedDict[str, dict[str, Any]] = OrderedDict()
_memory_guard = threading.Lock()
_ready_engines: set[int] = set()
_ready_guard = threading.Lock()


def _redis() -> Redis | None:
    """Use shared Redis when configured; otherwise the database holds the cache."""
    url = os.getenv("REDIS_URL", "").strip()
    return Redis.from_url(url, decode_responses=True) if url else None


def _cache_engine() -> Engine:
    """The engine for the cache table, creating the table on first use."""
    from .database import get_engine

    settings = get_settings()
    engine = get_engine(settings.cache_database_url or settings.database_url)
    with _ready_guard:
        if id(engine) not in _ready_engines:
            AnalysisCacheEntry.__table__.create(engine, checkfirst=True)  # type: ignore[attr-defined]
            _ready_engines.add(id(engine))
    return engine


def _remember(key: str, data: dict[str, Any]) -> None:
    with _memory_guard:
        _memory[key] = data
        _memory.move_to_end(key)
        while len(_memory) > MEMORY_CACHE_ENTRIES:
            _memory.popitem(last=False)


def clear_memory() -> None:
    """Drop the in-process layer (tests, or after pointing at a different store)."""
    with _memory_guard:
        _memory.clear()


def build_key(*parts: str) -> str:
    """Create a filesystem-safe key without leaking prompt or source text."""
    material = "".join((CACHE_SCHEMA_VERSION, *parts)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _read_store(key: str) -> dict[str, Any] | None:
    client = _redis()
    if client:
        try:
            payload = client.get(f"hasamex:analysis:{key}")
            return json.loads(payload) if payload else None
        except RedisError:
            # Cache availability must never prevent evidence retrieval.
            pass
    try:
        with Session(_cache_engine()) as session:
            entry = session.get(AnalysisCacheEntry, key)
            return json.loads(entry.payload_json) if entry else None
    except SQLAlchemyError:
        logger.warning("analysis_cache_read_failed key=%s", key, exc_info=True)
        return None


def read_cache(key: str) -> dict[str, Any] | None:
    with _memory_guard:
        if key in _memory:
            _memory.move_to_end(key)
            return _memory[key]
    data = _read_store(key)
    if data is not None:
        _remember(key, data)
    return data


def write_cache(key: str, data: dict[str, Any]) -> None:
    """Persist a result; a store outage only costs a future recomputation."""
    _remember(key, data)
    payload = json.dumps(data, sort_keys=True)
    client = _redis()
    if client:
        try:
            client.set(f"hasamex:analysis:{key}", payload)
            return
        except RedisError:
            pass
    try:
        with Session(_cache_engine()) as session, session.begin():
            session.merge(AnalysisCacheEntry(key=key, payload_json=payload))
    except SQLAlchemyError:
        # Includes losing a race with another process writing the same key,
        # which already stored the identical content-addressed result.
        logger.warning("analysis_cache_write_failed key=%s", key, exc_info=True)


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
