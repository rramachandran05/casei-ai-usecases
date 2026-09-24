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

    from casei_geofm.schemas.llm_io import (
        InventedMetadataError, _traceable, reject_unknown_overrides,
    )
    input_text = json.dumps(payload["product"], default=str)
    opportunities = []
    flags = []
    for opp in resp.opportunities:
        dumped = opp.model_dump()
        try:
            reject_unknown_overrides(payload["product"], dumped, PROTECTED_FIELDS,
                                     input_text=input_text)
        except InventedMetadataError as e:
            # reject the untraceable value but keep the opportunity: reset the
            # field to UNKNOWN and flag it for review
            for field in PROTECTED_FIELDS:
                if dumped.get(field) not in (None, "", "UNKNOWN") and \
                        not _traceable(str(dumped[field]), input_text):
                    dumped[field] = "UNKNOWN"
            flags.append(str(e))
        opportunities.append(dumped)

    return {
        "product_id": record["product_id"],
        "opportunities": opportunities,
        "reasoning": resp.reasoning,
        "guardrail_flags": flags,
    }


def run(records: list[dict], limit: int | None = None, api=None,
        checkpoint_every: int = 25, out_dir: Path | str = STAGE1_DIR) -> list[dict]:
    """Successive runs EXTEND the stage file: existing results are kept and
    reprocessed products are updated in place, so --limit slices accumulate."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_file = out_dir / "results.json"
    by_id: dict[str, dict] = {}
    if results_file.exists():
        by_id = {r["product_id"]: r for r in json.loads(results_file.read_text())}

    subset = records[:limit] if limit else records
    for done, record in enumerate(subset, 1):
        result = detect(record, api=api)
        by_id[result["product_id"]] = result
        if done % checkpoint_every == 0 or done == len(subset):
            merged = list(by_id.values())
            results_file.write_text(json.dumps(merged))
            print(f"  stage1: {done}/{len(subset)} products this run, "
                  f"{len(merged)} total "
                  f"({sum(1 for r in merged if r['opportunities'])} with opportunities)")
    return list(by_id.values())
