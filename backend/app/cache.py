"""Small, safe local cache used by the development deployment.

Production workers should use Redis or a database-backed analysis-run store. This
module makes local results reproducible and invalidates them when a source, prompt,
model, or cache schema changes.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

CACHE_SCHEMA_VERSION = "v2"
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
