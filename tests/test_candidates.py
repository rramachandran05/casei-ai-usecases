import json
from pathlib import Path

import pytest
import yaml

from casei_geofm.casei.normalize import normalize
from casei_geofm.discovery import label_detector, science_mapper, task_mapper
from casei_geofm.schemas.model import ModelCard

FIXTURES = Path(__file__).parent / "fixtures" / "casei_mini"


@pytest.fixture
def records():
    return normalize(cache_dir=FIXTURES)


def fake_detector_api(opportunities):
    def api(system, user, model):
        return json.dumps({"opportunities": opportunities,
                           "reasoning": "appears potentially useful based on metadata"})
    return api


TWO_OPPS = [
    {"target_variable": "fire_burned_area", "label_type": "raster_categorical",
     "label_provenance": "DIRECT_LABEL", "label_description": "burned area map",
     "evidence_quotes": ["FIREX-AQ"], "spatial_resolution": "UNKNOWN",
     "temporal_resolution": "UNKNOWN"},
    {"target_variable": "smoke_plume_extent", "label_type": "event",
     "label_provenance": "DERIVED_LABEL", "label_description": "plume polygons",
     "evidence_quotes": ["airborne campaign"], "spatial_resolution": "UNKNOWN",
     "temporal_resolution": "UNKNOWN"},
]


def test_one_product_yields_multiple_opportunities(records, tmp_path):
    rich = next(r for r in records if r["product_id"] != "sparse-0000")
    result = label_detector.detect(rich, api=fake_detector_api(TWO_OPPS), cache_dir=tmp_path)
    assert len(result["opportunities"]) == 2


def test_no_obvious_label_is_retained_not_dropped(records, tmp_path):
    sparse = next(r for r in records if r["product_id"] == "sparse-0000")
    result = label_detector.detect(sparse, api=fake_detector_api([]), cache_dir=tmp_path)
    assert result["opportunities"] == []
    results = label_detector.run([sparse], api=fake_detector_api([]), out_dir=tmp_path / "s1")
    assert len(results) == 1, "product with no label must stay in the output"


def test_detector_sanitizes_and_flags_invented_resolution(records, tmp_path):
    """An untraceable value is rejected (reset to UNKNOWN) and flagged — the
    run continues rather than crashing."""
    rich = next(r for r in records if r["product_id"] != "sparse-0000")
    invented = [dict(TWO_OPPS[0], spatial_resolution="123456.789m")]  # nowhere in input
    result = label_detector.detect(rich, api=fake_detector_api(invented), cache_dir=tmp_path)
    assert result["opportunities"][0]["spatial_resolution"] == "UNKNOWN"
    assert result["guardrail_flags"] and "invented" in result["guardrail_flags"][0]


def test_detector_keeps_instrument_traceable_resolution(records, tmp_path):
    """A value copied from instrument metadata inside the payload is kept."""
    rich = next(r for r in records if r["instruments"]
                and r["instruments"][0]["spatial_resolution"] != "UNKNOWN")
    inst_res = rich["instruments"][0]["spatial_resolution"]
    traced = [dict(TWO_OPPS[0], spatial_resolution=inst_res)]
    result = label_detector.detect(rich, api=fake_detector_api(traced), cache_dir=tmp_path)
    assert result["opportunities"][0]["spatial_resolution"] == inst_res
    assert result["guardrail_flags"] == []


def test_empty_examples_config_still_runs(records, tmp_path, monkeypatch):
    """Examples must not constrain discovery: pipeline works with none at all."""
    real_cfg = label_detector.CONFIG_DIR
    monkeypatch.setattr(label_detector, "_prompt_context", lambda: {
        "label_taxonomy": yaml.safe_load((real_cfg / "task_taxonomy.yaml").read_text())["label_types"],
        "provenance_classes": ["DIRECT_LABEL"],
        "example_use_cases_do_not_limit_to_these": [],
    })
    rich = next(r for r in records if r["product_id"] != "sparse-0000")
    result = label_detector.detect(rich, api=fake_detector_api(TWO_OPPS), cache_dir=tmp_path)
    assert result["opportunities"], "discovery must work with zero examples"


def fake_task_api(tasks):
    def api(system, user, model):
        return json.dumps({"tasks": tasks, "reasoning": "could plausibly supervise these"})
    return api


def test_opportunity_fans_out_to_multiple_candidates_with_stable_ids(records, tmp_path):
    rich = next(r for r in records if r["product_id"] != "sparse-0000")
    tasks = [
        {"proposed_task": "semantic_segmentation", "task_description": "map burned area",
         "phenomenon": "burn_severity", "potential_science_question": "UNKNOWN"},
        {"proposed_task": "change_detection", "task_description": "pre/post fire change",
         "phenomenon": "burn_severity", "potential_science_question": "UNKNOWN"},
    ]
    cands = task_mapper.map_tasks(rich, TWO_OPPS[0], api=fake_task_api(tasks), cache_dir=tmp_path)
    assert len(cands) == 2
    assert cands[0].candidate_id != cands[1].candidate_id
    assert cands[0].casei.product_id == rich["product_id"]
    assert cands[0].label.label_provenance == "DIRECT_LABEL"
    assert cands[0].evidence.evidence_level == 1
    # rerun -> same ids (deterministic tuple hash, stable cache uid)
    again = task_mapper.map_tasks(rich, TWO_OPPS[0], api=fake_task_api(tasks), cache_dir=tmp_path)
    assert [c.candidate_id for c in again] == [c.candidate_id for c in cands]


def test_low_science_fit_retained_and_flagged(records, tmp_path):
    rich = next(r for r in records if r["product_id"] != "sparse-0000")
    tasks = [{"proposed_task": "pixel_regression", "task_description": "x",
              "phenomenon": "atmospheric_chemistry", "potential_science_question": "UNKNOWN"}]
    cands = task_mapper.map_tasks(rich, TWO_OPPS[1], api=fake_task_api(tasks), cache_dir=tmp_path)

    def low_api(system, user, model):
        return json.dumps({"science_fit": "LOW",
                           "reasoning": "little surface expression in optical bands"})

    out = science_mapper.assess(cands[0], ModelCard.load(), api=low_api, cache_dir=tmp_path)
    assert out.compatibility.science_fit == "LOW"
    assert out.retained_for_future_models is True
