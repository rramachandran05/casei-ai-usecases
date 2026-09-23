import pytest

from casei_geofm.inventory import FILTER_COLUMNS, export, filter_candidates, load, to_dataframe
from casei_geofm.schemas.candidate import (
    Candidate, CaseiRef, Compatibility, Label, Ranking, UseCase,
)


def make_candidates():
    return [
        Candidate(casei=CaseiRef(campaign="ABoVE", campaign_id="c1", product_id="p1"),
                  label=Label(target_variable="canopy_height", label_type="airborne_retrieval",
                              label_provenance="DIRECT_LABEL"),
                  use_case=UseCase(phenomenon="vegetation_structure",
                                   proposed_task="pixel_regression"),
                  compatibility=Compatibility(native_or_transformable="TRANSFORMABLE"),
                  ranking=Ranking(label_value="HIGH", prithvi_readiness="HIGH")),
        Candidate(casei=CaseiRef(campaign="FIREX-AQ", campaign_id="c2", product_id="p2"),
                  label=Label(target_variable="aerosol_profile", label_type="instrument_retrieval",
                              label_provenance="WEAK_OR_PROXY_LABEL"),
                  use_case=UseCase(phenomenon="atmospheric_composition",
                                   proposed_task="patch_regression"),
                  compatibility=Compatibility(native_or_transformable="INCOMPATIBLE"),
                  ranking=Ranking(label_value="HIGH", prithvi_readiness="LOW")),
    ]


def test_export_round_trips_all_three_formats(tmp_path):
    paths = export(make_candidates(), out_dir=tmp_path)
    assert all(p.exists() for p in paths.values())
    df = load(paths["parquet"])
    assert len(df) == 2


def test_all_required_filter_dimensions_work(tmp_path):
    paths = export(make_candidates(), out_dir=tmp_path)
    df = load(paths["parquet"])
    checks = {
        "campaign": "ABoVE",
        "phenomenon": "vegetation_structure",
        "task_family": "pixel_regression",
        "label_provenance": "DIRECT_LABEL",
        "compatibility_class": "TRANSFORMABLE",
        "evidence_level": 1,
        "label_value": "HIGH",
        "prithvi_readiness": "HIGH",
    }
    assert set(checks) == set(FILTER_COLUMNS)
    for key, value in checks.items():
        result = filter_candidates(df, **{key: value})
        assert len(result) >= 1, f"filter {key}={value} returned nothing"


def test_divergent_rankings_visible_in_export(tmp_path):
    paths = export(make_candidates(), out_dir=tmp_path)
    df = load(paths["parquet"])
    divergent = df[df["ranking_label_value"] != df["ranking_prithvi_readiness"]]
    assert len(divergent) == 1, "dual rankings must be independently queryable"


def test_unknown_filter_key_rejected(tmp_path):
    paths = export(make_candidates(), out_dir=tmp_path)
    df = load(paths["parquet"])
    with pytest.raises(KeyError):
        filter_candidates(df, nonexistent="x")
