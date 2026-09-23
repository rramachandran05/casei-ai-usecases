import pytest

from casei_geofm.schemas.candidate import Candidate, CaseiRef, Label, UseCase, make_candidate_id
from casei_geofm.schemas.llm_io import InventedMetadataError, reject_unknown_overrides
from casei_geofm.schemas.model import ModelCard


def test_model_card_loads():
    card = ModelCard.load()
    assert card.name == "Prithvi-EO-2.0"
    assert card.input.spatial_resolution_m == 30
    assert len(card.input.bands) == 6


def test_candidate_id_deterministic_and_tuple_sensitive():
    a = make_candidate_id("c1", "p1", "canopy_height", "pixel_regression", "HLS")
    b = make_candidate_id("c1", "p1", "canopy_height", "pixel_regression", "HLS")
    assert a == b and len(a) == 16
    for changed in [
        ("c2", "p1", "canopy_height", "pixel_regression", "HLS"),
        ("c1", "p2", "canopy_height", "pixel_regression", "HLS"),
        ("c1", "p1", "biomass", "pixel_regression", "HLS"),
        ("c1", "p1", "canopy_height", "super_resolution", "HLS"),
        ("c1", "p1", "canopy_height", "pixel_regression", "Landsat"),
    ]:
        assert make_candidate_id(*changed) != a


def test_candidate_defaults_are_unknown_and_no_numeric_scores():
    c = Candidate()
    assert c.label.target_variable == "UNKNOWN"
    assert c.compatibility.science_fit == "UNKNOWN"
    assert c.ranking.label_value == "UNKNOWN"
    assert c.candidate_id  # auto-derived
    dumped = c.model_dump()
    for section in ("ranking", "compatibility"):
        for v in dumped[section].values():
            assert not isinstance(v, (int, float)), "no numeric scores allowed"


def test_candidate_id_autoderives_from_tuple():
    c1 = Candidate(casei=CaseiRef(campaign_id="c1", product_id="p1"),
                   label=Label(target_variable="biomass"),
                   use_case=UseCase(proposed_task="pixel_regression"))
    c2 = Candidate(casei=CaseiRef(campaign_id="c1", product_id="p1"),
                   label=Label(target_variable="biomass"),
                   use_case=UseCase(proposed_task="patch_regression"))
    assert c1.candidate_id != c2.candidate_id


def test_reject_unknown_overrides_raises_on_invention():
    input_record = {"spatial_resolution": "UNKNOWN", "temporal_resolution": "daily"}
    with pytest.raises(InventedMetadataError):
        reject_unknown_overrides(
            input_record,
            {"spatial_resolution": "30m"},
            protected_fields=["spatial_resolution", "temporal_resolution"],
        )


def test_reject_unknown_overrides_accepts_honest_response():
    input_record = {"spatial_resolution": "UNKNOWN", "temporal_resolution": "daily"}
    reject_unknown_overrides(
        input_record,
        {"spatial_resolution": "UNKNOWN", "temporal_resolution": "daily"},
        protected_fields=["spatial_resolution", "temporal_resolution"],
    )


def test_reject_unknown_overrides_allows_input_traceable_values():
    """Real case from the pilot slice: product-level resolution is UNKNOWN but
    the instrument metadata in the same payload carries the value — copying it
    up is evidence use, not invention."""
    input_record = {"spatial_resolution": "UNKNOWN"}
    input_text = ('{"instruments": [{"name": "LMA", '
                  '"spatial_resolution": "6-12 m (horizontal), 20-30 m (vertical)"}]}')
    reject_unknown_overrides(
        input_record,
        {"spatial_resolution": "6-12 m (horizontal), 20-30 m (vertical)"},
        protected_fields=["spatial_resolution"],
        input_text=input_text,
    )  # no raise
    # but a value whose numbers appear nowhere in the input still trips
    import pytest as _pytest
    with _pytest.raises(InventedMetadataError):
        reject_unknown_overrides(
            input_record, {"spatial_resolution": "500 m"},
            protected_fields=["spatial_resolution"], input_text=input_text)
