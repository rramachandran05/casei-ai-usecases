"""Granule search clients: NASA CMR (HLS) and STAC (Sentinel-2, Landsat).

Backends and collection ids verified live 2026-09-23 — see config/satellites.yaml.
Both return the same normalized scene dicts: {id, time_start, cloud_cover}.
All queries cached on disk keyed by a query hash.
"""

import hashlib
import json
from pathlib import Path

import httpx

CACHE_DIR = Path("data/cache/granules")


def _cached(key: dict, fetch) -> list[dict]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()[:24]
    f = CACHE_DIR / f"{h}.json"
    if f.exists():
        return json.loads(f.read_text())
    scenes = fetch()
    f.write_text(json.dumps(scenes))
    return scenes


def search_cmr(endpoint: str, collection: str, bbox: list[float],
               start: str, end: str, page_size: int = 200) -> list[dict]:
    key = {"backend": "cmr", "c": collection, "b": bbox, "s": start, "e": end}

    def fetch():
        resp = httpx.get(endpoint, params={
            "short_name": collection,
            "bounding_box": ",".join(str(round(v, 5)) for v in bbox),
            "temporal": f"{start},{end}",
            "page_size": page_size,
        }, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        entries = resp.json()["feed"]["entry"]
        return [{
            "id": e.get("producer_granule_id") or e.get("title"),
            "time_start": e.get("time_start"),
            "cloud_cover": float(e["cloud_cover"]) if e.get("cloud_cover") not in (None, "") else None,
        } for e in entries]

    return _cached(key, fetch)


def search_stac(endpoint: str, collection: str, bbox: list[float],
                start: str, end: str, limit: int = 200) -> list[dict]:
    key = {"backend": "stac", "u": endpoint, "c": collection, "b": bbox, "s": start, "e": end}

    def fetch():
        resp = httpx.post(endpoint, json={
            "collections": [collection],
            "bbox": bbox,
            "datetime": f"{start}/{end}",
            "limit": limit,
        }, timeout=60.0, follow_redirects=True)
        resp.raise_for_status()
        feats = resp.json().get("features", [])
        return [{
            "id": f.get("id"),
            "time_start": f["properties"].get("datetime"),
            "cloud_cover": f["properties"].get("eo:cloud_cover"),
        } for f in feats]

    return _cached(key, fetch)
