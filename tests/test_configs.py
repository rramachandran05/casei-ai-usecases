from pathlib import Path

import yaml

CONFIG = Path(__file__).parent.parent / "casei_geofm" / "config"


def load(name):
    return yaml.safe_load((CONFIG / name).read_text())


def test_all_configs_parse():
    for name in [
        "model_card.yaml",
        "task_taxonomy.yaml",
        "phenomena_windows.yaml",
        "satellites.yaml",
        "examples.yaml",
    ]:
        assert load(name), f"{name} empty or unparseable"


def test_model_card_required_fields():
    card = load("model_card.yaml")
    assert card["input"]["bands"] == ["Blue", "Green", "Red", "NIR", "SWIR1", "SWIR2"]
    assert card["input"]["spatial_resolution_m"] == 30
    assert card["input"]["temporal_context"]["timestamps"] == 4
    assert set(card["input"]["supported_satellites"]) == {"HLS", "Sentinel-2", "Landsat"}
    assert "segmentation" in card["adaptation"]["possible_tasks"]
    assert "modalities" in card["constraints"]


def test_taxonomy_counts_and_provenance():
    tax = load("task_taxonomy.yaml")
    assert len(tax["task_families"]) == 19
    assert len(tax["label_types"]) == 21
    assert tax["provenance_classes"] == [
        "DIRECT_LABEL",
        "DERIVED_LABEL",
        "WEAK_OR_PROXY_LABEL",
        "MULTIMODAL_PAIR",
        "NO_OBVIOUS_LABEL",
    ]


def test_phenomena_windows_differ_and_have_default():
    w = load("phenomena_windows.yaml")["windows_days"]
    assert "default" in w
    assert w["flood"] != w["land_cover"], "windows must be phenomenon-dependent"
    assert w["flood"] < w["vegetation_structure"] < w["land_cover"]


def test_satellites_ordered_with_backends():
    sat = load("satellites.yaml")
    assert sat["search_order"] == ["HLS", "Sentinel-2", "Landsat"]
    for m in sat["search_order"]:
        mission = sat["missions"][m]
        assert mission["backend"] in ("cmr", "stac")
        assert mission["collections"] and "TBD" not in mission["collections"]
        assert mission["start_date"]
