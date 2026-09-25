"""Copy analyses from the old JSON-file cache into the database cache.

Before the cache moved into the database, results were stored as one JSON file
per key under ``app/data/cache/``. Keys are unchanged, so importing those files
lets the database serve them without new LLM calls. Existing rows are kept.

Usage (from ``backend/``; writes to CACHE_DATABASE_URL, else DATABASE_URL):
    python scripts/import_file_cache.py
    python scripts/import_file_cache.py --source path/to/cache
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import cache  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=cache.LEGACY_CACHE_DIR)
    args = parser.parse_args()

    imported = skipped = 0
    for path in sorted(args.source.glob("*.json")):
        key = path.stem
        if cache.read_cache(key) is not None:
            skipped += 1
            continue
        cache.write_cache(key, json.loads(path.read_text(encoding="utf-8")))
        imported += 1
    print(f"imported={imported} already_present={skipped} source={args.source}")


if __name__ == "__main__":
    main()
