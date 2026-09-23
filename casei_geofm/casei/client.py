"""Thin client for the ADMG/CASEI API (verified live 2026-09-23).

Full-table JSON at https://admg.nasa-impact.net/api/<table>, envelope
{success, message, data}, no auth/pagination observed. The `doi` table
(2,607 data products) takes minutes to download — long timeout, retries,
and a mandatory disk cache.
"""

import json
import time
from pathlib import Path

import httpx

BASE_URL = "https://admg.nasa-impact.net/api"
DEFAULT_CACHE = Path("data/cache/casei")

TABLES = [
    "campaign", "platform", "instrument", "deployment", "doi",
    "collection_period", "measurement_type", "measurement_style",
    "focus_area", "geophysical_concept", "season", "repository",
    "platform_type", "gcmd_phenomenon", "iop", "significant_event",
    "geographical_region", "measurement_region",
]


def fetch_table(name: str, cache_dir: Path | str = DEFAULT_CACHE,
                timeout: float = 300.0, retries: int = 3) -> list[dict]:
    """Return the full table, from disk cache when present (zero network calls)."""
    cache_dir = Path(cache_dir)
    cache_file = cache_dir / f"{name}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())["data"]

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = httpx.get(f"{BASE_URL}/{name}", timeout=timeout, follow_redirects=True)
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success"):
                raise RuntimeError(f"CASEI API reported failure for '{name}': {payload.get('message')}")
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(payload))
            return payload["data"]
        except Exception as e:  # noqa: BLE001 — retry any transport/parse failure
            last_error = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"CASEI fetch failed for '{name}' after {retries} attempts") from last_error
