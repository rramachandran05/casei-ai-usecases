"""Normalize the raw CASEI tables into product-centric records.

One record per `doi` row (data product), with campaigns, platforms,
instruments, deployments and vocab labels resolved from UUIDs. Missing or
null values become the literal "UNKNOWN" — never invented.
"""

import json
from pathlib import Path

import pandas as pd
from shapely import wkt
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from casei_geofm.casei.client import DEFAULT_CACHE, fetch_table

UNKNOWN = "UNKNOWN"

NORMALIZED_PARQUET = Path("data/cache/normalized.parquet")
NORMALIZED_JSON = Path("data/cache/normalized.json")


def _clean(value) -> str:
    """CASEI uses '', None and the literal string 'null' for missing values."""
    if value is None or value == "" or value == "null":
        return UNKNOWN
    return value if isinstance(value, str) else json.dumps(value)


def parse_ewkt(spatial_bounds: str | None) -> BaseGeometry | None:
    """Parse CASEI's EWKT geometry ('SRID=4326;POLYGON (...)')."""
    if not spatial_bounds or spatial_bounds == "null":
        return None
    text = spatial_bounds.split(";", 1)[-1]
    try:
        return wkt.loads(text)
    except Exception:  # noqa: BLE001 — malformed geometry stays UNKNOWN
        return None


def _index(records: list[dict]) -> dict[str, dict]:
    return {r["uuid"]: r for r in records}


def _names(uuids, table_index: dict[str, dict], field: str = "short_name") -> list[str]:
    out = []
    for u in uuids or []:
        rec = table_index.get(u)
        if rec:
            out.append(_clean(rec.get(field)) if rec.get(field) else _clean(rec.get("long_name")))
    return out


def normalize(cache_dir: Path | str = DEFAULT_CACHE) -> list[dict]:
    tables = {}
    for t in ["campaign", "platform", "instrument", "deployment", "doi",
              "measurement_type", "measurement_style", "focus_area",
              "geophysical_concept", "season", "geographical_region",
              "measurement_region"]:
        tables[t] = _index(fetch_table(t, cache_dir=cache_dir))

    records = []
    for doi in tables["doi"].values():
        campaigns = [tables["campaign"][u] for u in doi.get("campaigns") or [] if u in tables["campaign"]]
        instruments = [tables["instrument"][u] for u in doi.get("instruments") or [] if u in tables["instrument"]]
        platforms = [tables["platform"][u] for u in doi.get("platforms") or [] if u in tables["platform"]]

        # Deployments come through the product's campaigns.
        deployments = []
        for c in campaigns:
            for du in c.get("deployments") or []:
                if du in tables["deployment"]:
                    deployments.append(tables["deployment"][du])

        geoms = [g for g in (parse_ewkt(d.get("spatial_bounds")) for d in deployments) if g]
        aoi = unary_union(geoms) if geoms else None

        focus, concepts, regions = [], [], []
        for c in campaigns:
            focus += _names(c.get("focus_areas"), tables["focus_area"])
            concepts += _names(c.get("geophysical_concepts"), tables["geophysical_concept"])
        for d in deployments:
            regions += _names(d.get("geographical_regions"), tables["geographical_region"])

        inst_details = []
        for i in instruments:
            mt = tables["measurement_type"].get(i.get("measurement_type") or "")
            ms = tables["measurement_style"].get(i.get("measurement_style") or "")
            inst_details.append({
                "name": _clean(i.get("short_name")),
                "long_name": _clean(i.get("long_name")),
                "measurement_type": _clean(mt.get("short_name")) if mt else UNKNOWN,
                "measurement_style": _clean(ms.get("short_name")) if ms else UNKNOWN,
                "spatial_resolution": _clean(i.get("spatial_resolution")),
                "temporal_resolution": _clean(i.get("temporal_resolution")),
                "measurement_regions": _names(i.get("measurement_regions"), tables["measurement_region"]),
                "description": _clean(i.get("description")),
            })

        records.append({
            "product_id": doi["uuid"],
            "doi": _clean(doi.get("doi")),
            "concept_id": _clean(doi.get("concept_id")),
            "product_name": _clean(doi.get("cmr_entry_title")) if _clean(doi.get("cmr_entry_title")) != UNKNOWN else _clean(doi.get("long_name")),
            "cmr_short_name": _clean(doi.get("cmr_short_name")),
            "cmr_abstract": _clean(doi.get("cmr_abstract")),
            "cmr_science_keywords": _clean(doi.get("cmr_science_keywords")),
            "cmr_data_formats": _clean(doi.get("cmr_data_formats")),
            "cmr_dates": doi.get("cmr_dates") or [],
            "campaign_ids": [c["uuid"] for c in campaigns],
            "campaigns": [_clean(c.get("short_name")) for c in campaigns],
            "campaign_descriptions": [_clean(c.get("description_short")) for c in campaigns],
            "campaign_start": _clean(campaigns[0].get("start_date")) if campaigns else UNKNOWN,
            "campaign_end": _clean(campaigns[0].get("end_date")) if campaigns else UNKNOWN,
            "region_descriptions": [_clean(c.get("region_description")) for c in campaigns],
            "platforms": [_clean(p.get("short_name")) for p in platforms],
            "platform_types": sorted({_clean(pt) for p in platforms for pt in [p.get("platform_type")] if pt}) or [],
            "instruments": inst_details,
            "deployment_windows": [
                {"start": _clean(d.get("start_date")), "end": _clean(d.get("end_date"))}
                for d in deployments
            ],
            "aoi_wkt": aoi.wkt if aoi else UNKNOWN,
            "aoi_source": "deployment_union" if aoi else UNKNOWN,
            "focus_areas": sorted(set(focus)),
            "geophysical_concepts": sorted(set(concepts)),
            "geographical_regions": sorted(set(regions)),
        })
    return records


def run(cache_dir: Path | str = DEFAULT_CACHE) -> pd.DataFrame:
    records = normalize(cache_dir)
    NORMALIZED_JSON.parent.mkdir(parents=True, exist_ok=True)
    NORMALIZED_JSON.write_text(json.dumps(records))
    df = pd.DataFrame(records)
    # parquet needs stable types; nested fields stay as JSON strings there
    flat = df.copy()
    for col in flat.columns:
        if flat[col].map(lambda v: isinstance(v, (list, dict))).any():
            flat[col] = flat[col].map(json.dumps)
    flat.to_parquet(NORMALIZED_PARQUET, index=False)
    print(f"normalized {len(records)} product records -> {NORMALIZED_PARQUET}")
    return df
