"""Harvest the complete published CASEI catalog into the local cache."""

from pathlib import Path

from casei_geofm.casei.client import DEFAULT_CACHE, TABLES, fetch_table

# Explore-interface figures at pilot start (2026-09-23); deviations are
# reported, not fatal — the catalog is a living database.
EXPECTED_COUNTS = {"campaign": 194, "platform": 153, "instrument": 605,
                   "deployment": 488, "doi": 2607}


def harvest_all(cache_dir: Path | str = DEFAULT_CACHE) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        data = fetch_table(table, cache_dir=cache_dir)
        counts[table] = len(data)
        expected = EXPECTED_COUNTS.get(table)
        flag = ""
        if expected is not None and expected != len(data):
            flag = f"  (expected ~{expected} — catalog drift, review)"
        print(f"  {table:20s} {len(data):5d}{flag}")
    return counts
