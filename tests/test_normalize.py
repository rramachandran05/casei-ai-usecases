from pathlib import Path

from casei_geofm.casei.normalize import UNKNOWN, normalize, parse_ewkt

FIXTURES = Path(__file__).parent / "fixtures" / "casei_mini"


def test_parse_ewkt_verified_sample():
    geom = parse_ewkt("SRID=4326;POLYGON ((-99 25, -81 25, -81 33, -99 33, -99 25))")
    assert geom is not None and geom.geom_type == "POLYGON".title()
    assert geom.bounds == (-99.0, 25.0, -81.0, 33.0)


def test_parse_ewkt_missing_or_bad():
    assert parse_ewkt(None) is None
    assert parse_ewkt("") is None
    assert parse_ewkt("null") is None
    assert parse_ewkt("SRID=4326;POLYGON ((not wkt") is None


def test_normalize_resolves_uuid_relationships():
    records = normalize(cache_dir=FIXTURES)
    assert len(records) == 3
    rich = [r for r in records if r["product_id"] != "sparse-0000"]
    for r in rich:
        assert r["campaigns"] and all(c != UNKNOWN for c in r["campaigns"]), "campaign uuids must resolve to names"
        assert r["instruments"] and r["instruments"][0]["name"] != UNKNOWN
        assert r["platforms"]
        assert r["aoi_wkt"] != UNKNOWN, "deployments carry spatial_bounds -> AOI expected"
        assert r["aoi_source"] == "deployment_union"
        assert r["deployment_windows"]
        assert r["focus_areas"]


def test_sparse_record_stays_unknown_nothing_invented():
    records = normalize(cache_dir=FIXTURES)
    sparse = next(r for r in records if r["product_id"] == "sparse-0000")
    assert sparse["doi"] == UNKNOWN
    assert sparse["concept_id"] == UNKNOWN
    assert sparse["cmr_abstract"] == UNKNOWN
    assert sparse["cmr_science_keywords"] == UNKNOWN  # literal "null" cleaned
    assert sparse["cmr_data_formats"] == UNKNOWN
    assert sparse["aoi_wkt"] == UNKNOWN
    assert sparse["aoi_source"] == UNKNOWN
    assert sparse["campaigns"] == []
    assert sparse["campaign_start"] == UNKNOWN
    # the one real value survives untouched
    assert sparse["product_name"] == "Sparse Test Product"
