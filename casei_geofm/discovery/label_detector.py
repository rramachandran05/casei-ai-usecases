"""Stage 1 — run every normalized product through the Label Opportunity Detector."""

import json
from pathlib import Path

import yaml

from casei_geofm.llm import call_stage
from casei_geofm.schemas.llm_io import LabelDetectorResponse

CONFIG_DIR = Path(__file__).parent.parent / "config"
STAGE1_DIR = Path("data/cache/stage1")

# Factual metadata the LLM must echo from input or leave UNKNOWN.
PROTECTED_FIELDS = ["spatial_resolution", "temporal_resolution"]


def _prompt_context() -> dict:
    taxonomy = yaml.safe_load((CONFIG_DIR / "task_taxonomy.yaml").read_text())
    examples = yaml.safe_load((CONFIG_DIR / "examples.yaml").read_text()) or {}
    return {
        "label_taxonomy": taxonomy["label_types"],
        "provenance_classes": [p for p in taxonomy["provenance_classes"] if p != "NO_OBVIOUS_LABEL"],
        "example_use_cases_do_not_limit_to_these": examples.get("examples", []),
    }


def product_payload(record: dict) -> dict:
    """The metadata slice the detector sees for one product."""
    return {
        "product_name": record["product_name"],
        "doi": record["doi"],
        "cmr_abstract": record["cmr_abstract"],
        "cmr_science_keywords": record["cmr_science_keywords"],
        "cmr_data_formats": record["cmr_data_formats"],
        "campaigns": record["campaigns"],
        "campaign_descriptions": record["campaign_descriptions"],
        "platforms": record["platforms"],
        "instruments": record["instruments"],
        "focus_areas": record["focus_areas"],
        "geophysical_concepts": record["geophysical_concepts"],
        "geographical_regions": record["geographical_regions"],
        "spatial_resolution": "UNKNOWN",   # product-level; instrument-level passed above
        "temporal_resolution": "UNKNOWN",
    }


def detect(record: dict, api=None, cache_dir: Path | None = None) -> dict:
    """Return {'product_id', 'opportunities': [...], 'reasoning'} — empty list
    means NO_OBVIOUS_LABEL; the product is retained either way."""
    payload = {"context": _prompt_context(), "product": product_payload(record)}
    kwargs = {"cache_dir": cache_dir} if cache_dir else {}
    if api:
        kwargs["api"] = api
    resp: LabelDetectorResponse = call_stage(
        "label_detector", record["product_id"], payload, LabelDetectorResponse, **kwargs)

    from casei_geofm.schemas.llm_io import reject_unknown_overrides
    for opp in resp.opportunities:
        reject_unknown_overrides(payload["product"], opp.model_dump(), PROTECTED_FIELDS)

    return {
        "product_id": record["product_id"],
        "opportunities": [o.model_dump() for o in resp.opportunities],
        "reasoning": resp.reasoning,
    }


def run(records: list[dict], limit: int | None = None, api=None,
        checkpoint_every: int = 25, out_dir: Path | str = STAGE1_DIR) -> list[dict]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results, done = [], 0
    subset = records[:limit] if limit else records
    for record in subset:
        results.append(detect(record, api=api))
        done += 1
        if done % checkpoint_every == 0 or done == len(subset):
            (out_dir / "results.json").write_text(json.dumps(results))
            print(f"  stage1: {done}/{len(subset)} products "
                  f"({sum(1 for r in results if r['opportunities'])} with opportunities)")
    return results
