import json

import pytest

from casei_geofm.ranking.ranker import Level1PhrasingError, lint_level1_phrasing, rank
from casei_geofm.schemas.candidate import Candidate, Evidence, Label, Ranking, UseCase


def make_response(**overrides):
    base = {
        "label_value": "HIGH",
        "label_value_reasoning": "direct continuous supervision at scale; appears rare in benchmarks",
        "prithvi_readiness": "LOW",
        "prithvi_readiness_reasoning": "no coincident scenes found; heavy transformation burden",
        "novelty": "HIGH",
        "overall_priority": "MEDIUM",
    }
    base.update(overrides)
    return json.dumps(base)


def test_dual_rankings_present_and_divergent(tmp_path):
    c = Candidate(label=Label(target_variable="canopy_chemistry"),
                  use_case=UseCase(proposed_task="spectral_prediction"))

    def api(system, user, model):
        return make_response()

    out = rank(c, api=api, cache_dir=tmp_path)
    assert out.ranking.label_value == "HIGH"
    assert out.ranking.prithvi_readiness == "LOW"
    assert out.ranking.label_value != out.ranking.prithvi_readiness, \
        "rankings must be independent — divergence must be possible"
    assert "supervision" in out.ranking.label_value_reasoning


def test_no_numeric_scores_in_ranking_schema():
    dumped = Ranking().model_dump()
    assert all(not isinstance(v, (int, float)) for v in dumped.values())


def test_level1_lint_rejects_confirmatory_phrasing():
    c = Candidate(evidence=Evidence(evidence_level=1))
    c.ranking.label_value_reasoning = "this is a confirmed training dataset"
    with pytest.raises(Level1PhrasingError):
        lint_level1_phrasing(c)


def test_level1_lint_accepts_hedged_phrasing():
    c = Candidate(evidence=Evidence(evidence_level=1))
    c.ranking.label_value_reasoning = "appears potentially useful as supervision"
    lint_level1_phrasing(c)


def test_level1_lint_allows_deterministic_facts_called_confirmed():
    """Stage-4 satellite overlap IS confirmed deterministically — saying so is
    not a dataset-confirmation claim (regression: the broad lint quarantined
    399/632 slice candidates on phrases like this)."""
    c = Candidate(evidence=Evidence(evidence_level=1))
    c.ranking.prithvi_readiness_reasoning = (
        "coincident HLS scenes are confirmed with sub-day offsets; "
        "spatial fit verified against the 30 m grid")
    lint_level1_phrasing(c)  # no raise


def test_level1_lint_still_blocks_dataset_confirmation_claims():
    c = Candidate(evidence=Evidence(evidence_level=1))
    for phrase in ["the labels are confirmed", "verified ground-truth",
                   "validated supervision", "is a training dataset"]:
        c.ranking.label_value_reasoning = phrase
        import pytest as _pytest
        with _pytest.raises(Level1PhrasingError):
            lint_level1_phrasing(c)


def test_level2_may_use_confirmed_phrasing():
    c = Candidate(evidence=Evidence(evidence_level=2))
    c.ranking.label_value_reasoning = "variables confirmed against CMR metadata"
    lint_level1_phrasing(c)  # no raise


def test_rank_applies_lint(tmp_path):
    c = Candidate(label=Label(target_variable="y"),
                  use_case=UseCase(proposed_task="pixel_regression"))

    def api(system, user, model):
        return make_response(label_value_reasoning="verified training dataset, ready to go")

    with pytest.raises(Level1PhrasingError):
        rank(c, api=api, cache_dir=tmp_path)
