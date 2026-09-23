import json

import pytest

from casei_geofm import evidence
from casei_geofm.schemas.candidate import Candidate

UMM = {
    "TemporalExtents": [{"RangeDateTimes": [{"BeginningDateTime": "2019-01-01"}]}],
    "SpatialExtent": {"HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": []}}},
    "ScienceKeywords": [{"Term": "VEGETATION", "VariableLevel1": "CANOPY CHARACTERISTICS"}],
    "ArchiveAndDistributionInformation": {
        "FileDistributionInformation": [{"Format": "netCDF-4"}]},
}


def test_promote_level2_records_changes(tmp_path, monkeypatch):
    (tmp_path / "C123-TEST.json").write_text(json.dumps(UMM))
    c = Candidate()
    assert c.evidence.evidence_level == 1
    out = evidence.promote_level2(c, "C123-TEST", cache_dir=tmp_path)
    assert out.evidence.evidence_level == 2
    log = " ".join(out.evidence.promotion_log)
    assert "netCDF-4" in log and "temporal coverage confirmed" in log
    assert "CANOPY CHARACTERISTICS" in log
    assert any("cmr.earthdata.nasa.gov" in u for u in out.evidence.urls)


def test_promote_level2_without_concept_id_or_doi_stays_level1(tmp_path):
    c = Candidate()
    out = evidence.promote_level2(c, "UNKNOWN", cache_dir=tmp_path)
    assert out.evidence.evidence_level == 1
    assert "no CMR concept_id or DOI" in out.evidence.promotion_log[0]


def test_stale_concept_id_falls_back_to_doi(tmp_path):
    # stale id -> cached None; DOI lookup -> cached record
    (tmp_path / "C-STALE.json").write_text("null")
    (tmp_path / "doi-10.3334_X_1.json").write_text(json.dumps(UMM))
    c = Candidate()
    out = evidence.promote_level2(c, "C-STALE", doi="10.3334/X/1", cache_dir=tmp_path)
    assert out.evidence.evidence_level == 2


def test_promote_level3_requires_level2_first():
    c = Candidate()
    with pytest.raises(ValueError, match="requires level2"):
        evidence.promote_level3(c, "opened granule, CRS EPSG:4326, values plausible")


def test_promote_level3_records_inspection(tmp_path):
    (tmp_path / "C9.json").write_text(json.dumps(UMM))
    c = Candidate()
    evidence.promote_level2(c, "C9", cache_dir=tmp_path)
    out = evidence.promote_level3(c, "opened granule: 3660x3660 px, UTM 13N, biomass 0-540 Mg/ha")
    assert out.evidence.evidence_level == 3
    assert "biomass 0-540" in out.evidence.promotion_log[-1]


@pytest.mark.network
def test_live_cmr_collection_lookup(tmp_path):
    # stale 2021-era CASEI concept_id (FIFE product) resolves via DOI fallback
    record = evidence.fetch_cmr_collection(
        "C179002949-ORNL_DAAC", doi="10.3334/ORNLDAAC/121", cache_dir=tmp_path)
    assert record is not None and "TemporalExtents" in record
