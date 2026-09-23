"""Stage 4 — satellite coincidence: for a candidate's AOI x time window, search
missions in configured order (HLS -> Sentinel-2 -> Landsat) and record overlap.

A campaign is never rejected for predating HLS: missions whose record starts
after the observation window are skipped, later missions still searched.
Candidates without geometry/dates get UNKNOWN plus the named missing
prerequisite — they are retained, not dropped.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from shapely import wkt

from casei_geofm.satellite import cmr as backends
from casei_geofm.schemas.candidate import MissionOverlap, Satellite

CONFIG = Path(__file__).parent.parent / "config" / "satellites.yaml"
UNKNOWN = "UNKNOWN"

FIELD_BY_MISSION = {"HLS": "HLS", "Sentinel-2": "Sentinel2", "Landsat": "Landsat"}


def load_config(path: Path | None = None) -> dict:
    return yaml.safe_load((path or CONFIG).read_text())


def _parse_date(value: str) -> date | None:
    if not value or value == UNKNOWN:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _offset_days(scene_time: str, window_start: date, window_end: date) -> float | None:
    t = _parse_date(scene_time)
    if t is None:
        return None
    if window_start <= t <= window_end:
        return 0.0
    return min(abs((t - window_start).days), abs((t - window_end).days))


def search_mission(mission_cfg: dict, bbox: list[float], start: str, end: str) -> list[dict]:
    scenes: list[dict] = []
    for collection in mission_cfg["collections"]:
        if mission_cfg["backend"] == "cmr":
            scenes += backends.search_cmr(mission_cfg["endpoint"], collection, bbox, start, end)
        else:
            scenes += backends.search_stac(mission_cfg["endpoint"], collection, bbox, start, end)
    return scenes


def assess_coincidence(aoi_wkt: str, obs_start: str, obs_end: str,
                       config: dict | None = None,
                       search_pad_days: int = 14) -> Satellite:
    cfg = config or load_config()
    sat = Satellite()

    start_d, end_d = _parse_date(obs_start), _parse_date(obs_end)
    missing = []
    if not aoi_wkt or aoi_wkt == UNKNOWN:
        missing.append("geometry")
    if start_d is None or end_d is None:
        missing.append("observation dates")
    if missing:
        sat.missing_prerequisite = f"missing {' and '.join(missing)}; coincidence not assessable"
        return sat

    geom = wkt.loads(aoi_wkt)
    bbox = list(geom.bounds)
    sat.aoi_source = "provided"

    pad = timedelta(days=search_pad_days)
    q_start = (start_d - pad).isoformat() + "T00:00:00Z"
    q_end = (end_d + pad).isoformat() + "T23:59:59Z"

    seq_min = cfg.get("sequence_min_scenes", 4)
    for mission in cfg["search_order"]:
        mcfg = cfg["missions"][mission]
        field = FIELD_BY_MISSION[mission]
        mission_start = _parse_date(mcfg["start_date"])
        if mission_start and end_d < mission_start:
            # observation predates this mission entirely; skip, do NOT reject
            setattr(sat, field, MissionOverlap(overlap="NO", scene_count=0))
            continue
        try:
            scenes = search_mission(mcfg, bbox, q_start, q_end)
        except Exception as e:  # noqa: BLE001 — record failure, keep going
            setattr(sat, field, MissionOverlap(overlap=UNKNOWN))
            sat.missing_prerequisite += f" [{mission} search failed: {type(e).__name__}]"
            continue
        offsets = [o for o in (_offset_days(s["time_start"], start_d, end_d) for s in scenes) if o is not None]
        clouds = [s["cloud_cover"] for s in scenes if s.get("cloud_cover") is not None]
        setattr(sat, field, MissionOverlap(
            overlap="YES" if scenes else "NO",
            scene_count=len(scenes),
            min_temporal_offset_days=min(offsets) if offsets else None,
            cloud_cover_min=min(clouds) if clouds else None,
            sequence_available="YES" if len(scenes) >= seq_min else "NO",
        ))
    return sat
