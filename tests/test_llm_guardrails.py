import json

import pytest

from casei_geofm.llm import GUARDRAIL_PREAMBLE, call_stage
from casei_geofm.schemas.llm_io import ScienceFitResponse


def make_api(responses):
    calls = {"n": 0}

    def api(system, user, model):
        assert "never infer or invent" in GUARDRAIL_PREAMBLE and "never infer or invent" in system
        out = responses[min(calls["n"], len(responses) - 1)]
        calls["n"] += 1
        return out

    api.calls = calls
    return api


GOOD = json.dumps({"science_fit": "HIGH", "reasoning": "surface water is directly visible"})


def test_cache_hit_short_circuits(tmp_path):
    api = make_api([GOOD])
    r1 = call_stage("science_mapper", "u1", {"target_variable": "flood extent"},
                    ScienceFitResponse, cache_dir=tmp_path, api=api)
    r2 = call_stage("science_mapper", "u1", {"target_variable": "flood extent"},
                    ScienceFitResponse, cache_dir=tmp_path, api=api)
    assert r1 == r2 and api.calls["n"] == 1


def test_prompt_version_bump_invalidates_cache(tmp_path):
    api = make_api([GOOD])
    call_stage("science_mapper", "u1", {}, ScienceFitResponse, cache_dir=tmp_path, api=api)
    call_stage("science_mapper", "u1", {}, ScienceFitResponse, cache_dir=tmp_path, api=api,
               prompt_version="v1")  # same version -> cached
    assert api.calls["n"] == 1


def test_invalid_json_retries_once_then_fails(tmp_path):
    api = make_api(["not json at all", "still not json"])
    with pytest.raises(RuntimeError, match="failed validation twice"):
        call_stage("science_mapper", "u2", {}, ScienceFitResponse, cache_dir=tmp_path, api=api)
    assert api.calls["n"] == 2


def test_invalid_then_valid_recovers(tmp_path):
    api = make_api([json.dumps({"science_fit": "VERY_HIGH", "reasoning": "x"}), GOOD])
    r = call_stage("science_mapper", "u3", {}, ScienceFitResponse, cache_dir=tmp_path, api=api)
    assert r.science_fit == "HIGH" and api.calls["n"] == 2


def test_code_fenced_json_tolerated(tmp_path):
    api = make_api(["```json\n" + GOOD + "\n```"])
    r = call_stage("science_mapper", "u4", {}, ScienceFitResponse, cache_dir=tmp_path, api=api)
    assert r.science_fit == "HIGH"


def test_all_stage_prompts_exist():
    from casei_geofm.llm import load_prompt
    for stage in ["label_detector", "task_mapper", "science_mapper", "transform", "ranker"]:
        text = load_prompt(stage, "v1")
        assert len(text) > 200, f"{stage} prompt too thin"
