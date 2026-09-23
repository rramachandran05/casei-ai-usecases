"""Progressive evidence model (01-spec.md's most important guardrail).

Level 1 — CASEI metadata inference ("appears potentially useful").
Level 2 — archive/product metadata confirmed via the CMR collection record.
Level 3 — representative file opened and inspected.

Promotions record what changed; a Level-1 candidate is never described as a
confirmed training dataset (enforced by ranking.ranker.lint_level1_phrasing).
"""

import json
from pathlib import Path

import httpx

from casei_geofm.schemas.candidate import Candidate

CMR_COLLECTIONS = "https://cmr.earthdata.nasa.gov/search/collections.umm_json"
CACHE_DIR = Path("data/cache/cmr_collections")
UNKNOWN = "UNKNOWN"


def _cmr_lookup(params: dict, cache_key: str, cache_dir: Path) -> dict | None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    f = cache_dir / f"{cache_key}.json"
    if f.exists():
        return json.loads(f.read_text())
    resp = httpx.get(CMR_COLLECTIONS, params=params, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    record = items[0].get("umm") if items else None
    f.write_text(json.dumps(record))
    return record


def fetch_cmr_collection(concept_id: str = UNKNOWN, doi: str = UNKNOWN,
                         cache_dir: Path | str = CACHE_DIR) -> dict | None:
    """Resolve a CMR collection by concept_id, falling back to DOI search.

    The fallback matters: CASEI's stored concept_ids date to ~2021 and many
    DAACs have since migrated to cloud providers (sampled 2026-09-23: only
    5/12 stored ids still resolve; DOI lookup finds the migrated records)."""
    cache_dir = Path(cache_dir)
    record = None
    if concept_id and concept_id != UNKNOWN:
        record = _cmr_lookup({"concept_id": concept_id}, concept_id, cache_dir)
    if record is None and doi and doi != UNKNOWN:
        record = _cmr_lookup({"doi": doi}, "doi-" + doi.replace("/", "_"), cache_dir)
    return record


def promote_level2(candidate: Candidate, concept_id: str, doi: str = UNKNOWN,
                   cache_dir: Path | str = CACHE_DIR) -> Candidate:
    """Confirm/correct candidate metadata against the CMR collection record."""
    if (not concept_id or concept_id == UNKNOWN) and (not doi or doi == UNKNOWN):
        candidate.evidence.promotion_log.append(
            "level2: skipped — no CMR concept_id or DOI available")
        return candidate
    record = fetch_cmr_collection(concept_id, doi, cache_dir)
    if record is None:
        candidate.evidence.promotion_log.append(
            f"level2: CMR returned no collection for {concept_id} / doi {doi}")
        return candidate

    changes = []

    formats = {a.get("Format") for a in
               (record.get("ArchiveAndDistributionInformation", {})
                      .get("FileDistributionInformation") or []) if a.get("Format")}
    if formats:
        changes.append(f"data_formats confirmed: {sorted(formats)}")

    temporal = record.get("TemporalExtents")
    if temporal:
        changes.append("temporal coverage confirmed from CMR TemporalExtents")

    spatial = (record.get("SpatialExtent", {})
                     .get("HorizontalSpatialDomain", {}).get("Geometry"))
    if spatial:
        changes.append("spatial extent confirmed from CMR SpatialExtent")

    keywords = record.get("ScienceKeywords")
    if keywords:
        vars_ = sorted({k.get("VariableLevel1", k.get("Term", "")) for k in keywords} - {""})
        if vars_:
            changes.append(f"variables per CMR science keywords: {vars_[:8]}")

    candidate.evidence.evidence_level = 2
    candidate.evidence.promotion_log.append(
        "level2: " + ("; ".join(changes) if changes else "CMR record found, sparse metadata"))
    candidate.evidence.urls.append(
        f"https://cmr.earthdata.nasa.gov/search/concepts/{concept_id}.html")
    return candidate


def promote_level3(candidate: Candidate, inspection_notes: str) -> Candidate:
    """Record a manual/scripted inspection of a representative file. The pilot
    opens representative granules for a HIGH-tier sample only; the inspection
    itself (coordinates, dimensions, projection, value ranges) is performed by
    the operator or a per-format script and summarized in `inspection_notes`."""
    if candidate.evidence.evidence_level < 2:
        raise ValueError("level3 requires level2 first — promote in order")
    candidate.evidence.evidence_level = 3
    candidate.evidence.promotion_log.append(f"level3: {inspection_notes}")
    return candidate
