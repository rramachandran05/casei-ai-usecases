import json

import httpx
import pytest

from casei_geofm.casei.client import fetch_table


def test_cache_hit_makes_zero_network_calls(tmp_path, monkeypatch):
    cache = tmp_path / "casei"
    cache.mkdir()
    (cache / "campaign.json").write_text(json.dumps(
        {"success": True, "message": "", "data": [{"uuid": "u1", "short_name": "TEST"}]}
    ))

    def explode(*args, **kwargs):
        raise AssertionError("network call attempted despite cache hit")

    monkeypatch.setattr(httpx, "get", explode)
    data = fetch_table("campaign", cache_dir=cache)
    assert data == [{"uuid": "u1", "short_name": "TEST"}]


def test_miss_fetches_writes_cache_then_hits(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_get(url, **kwargs):
        calls["n"] += 1
        return httpx.Response(
            200, json={"success": True, "message": "", "data": [{"uuid": "x"}]},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    cache = tmp_path / "casei"
    assert fetch_table("focus_area", cache_dir=cache) == [{"uuid": "x"}]
    assert fetch_table("focus_area", cache_dir=cache) == [{"uuid": "x"}]
    assert calls["n"] == 1, "second call must be served from cache"


def test_api_failure_envelope_raises(tmp_path, monkeypatch):
    def fake_get(url, **kwargs):
        return httpx.Response(
            200, json={"success": False, "message": "nope", "data": []},
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(RuntimeError):
        fetch_table("campaign", cache_dir=tmp_path, retries=1)


@pytest.mark.network
def test_live_focus_area_fetch(tmp_path):
    data = fetch_table("focus_area", cache_dir=tmp_path)
    assert len(data) > 0 and "uuid" in data[0]
