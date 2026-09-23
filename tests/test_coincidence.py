import pytest

from casei_geofm.satellite import cmr as backends
from casei_geofm.satellite.coincidence import assess_coincidence, load_config

AOI = "POLYGON ((-105 39, -104 39, -104 40, -105 40, -105 39))"


@pytest.fixture
def mock_backends(monkeypatch, tmp_path):
    """Mock both granule backends and record the call order."""
    monkeypatch.setattr(backends, "CACHE_DIR", tmp_path / "granules")
    calls = []

    def fake_cmr(endpoint, collection, bbox, start, end, page_size=200):
        calls.append(("cmr", collection))
        return [{"id": "HLS.X", "time_start": start[:10] + "T12:00:00Z", "cloud_cover": 10.0}]

    def fake_stac(endpoint, collection, bbox, start, end, limit=200):
        calls.append(("stac", collection))
        return [{"id": f"{collection}-scene", "time_start": start[:10] + "T12:00:00Z",
                 "cloud_cover": 5.0}]

    monkeypatch.setattr("casei_geofm.satellite.coincidence.backends.search_cmr", fake_cmr)
    monkeypatch.setattr("casei_geofm.satellite.coincidence.backends.search_stac", fake_stac)
    return calls


def test_ordered_search_hls_then_s2_then_landsat(mock_backends):
    sat = assess_coincidence(AOI, "2022-06-01", "2022-06-30")
    collections = [c for _, c in mock_backends]
    assert collections == ["HLSL30", "HLSS30", "sentinel-2-l2a", "landsat-c2l2-sr"]
    assert sat.HLS.overlap == "YES" and sat.Sentinel2.overlap == "YES" and sat.Landsat.overlap == "YES"
    assert sat.HLS.min_temporal_offset_days is not None


def test_pre_hls_campaign_falls_through_to_landsat_not_rejected(mock_backends):
    sat = assess_coincidence(AOI, "1995-06-01", "1995-08-31")
    # HLS and Sentinel-2 records start after 1995: skipped as NO, never queried
    assert sat.HLS.overlap == "NO" and sat.HLS.scene_count == 0
    assert sat.Sentinel2.overlap == "NO"
    # Landsat (from 1972) is searched and found
    assert sat.Landsat.overlap == "YES"
    assert [c for _, c in mock_backends] == ["landsat-c2l2-sr"]


def test_missing_geometry_yields_unknown_with_named_prerequisite(mock_backends):
    sat = assess_coincidence("UNKNOWN", "2022-06-01", "2022-06-30")
    assert sat.HLS.overlap == "UNKNOWN"
    assert "geometry" in sat.missing_prerequisite
    assert mock_backends == [], "no search attempted without geometry"


def test_missing_dates_yields_unknown_with_named_prerequisite(mock_backends):
    sat = assess_coincidence(AOI, "UNKNOWN", "UNKNOWN")
    assert "observation dates" in sat.missing_prerequisite
    assert mock_backends == []


def test_sequence_availability_threshold(monkeypatch, tmp_path):
    monkeypatch.setattr(backends, "CACHE_DIR", tmp_path / "granules")
    many = [{"id": f"s{i}", "time_start": "2022-06-05T12:00:00Z", "cloud_cover": 1.0}
            for i in range(5)]
    monkeypatch.setattr("casei_geofm.satellite.coincidence.backends.search_cmr",
                        lambda *a, **k: many)
    monkeypatch.setattr("casei_geofm.satellite.coincidence.backends.search_stac",
                        lambda *a, **k: [])
    sat = assess_coincidence(AOI, "2022-06-01", "2022-06-30")
    assert sat.HLS.sequence_available == "YES"  # 10 scenes across 2 HLS collections
    assert sat.Sentinel2.sequence_available == "NO"


@pytest.mark.network
def test_live_hls_query_colorado_june_2022():
    cfg = load_config()
    sat = assess_coincidence(AOI, "2022-06-01", "2022-06-30", config=cfg)
    assert sat.HLS.overlap == "YES" and sat.HLS.scene_count >= 1
    assert sat.HLS.cloud_cover_min is not None
