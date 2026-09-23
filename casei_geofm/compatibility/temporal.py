"""Temporal compatibility: phenomenon-dependent windows, never one threshold."""

from pathlib import Path

import yaml

from casei_geofm.schemas.candidate import Candidate, Rating

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_windows() -> dict:
    return yaml.safe_load((CONFIG_DIR / "phenomena_windows.yaml").read_text())["windows_days"]


def temporal_fit(candidate: Candidate, windows: dict | None = None) -> Rating:
    """The same offset can pass for land cover and fail for flood."""
    windows = windows or load_windows()
    window = windows.get(candidate.use_case.phenomenon, windows["default"])

    offsets = [m.min_temporal_offset_days
               for m in (candidate.satellite.HLS, candidate.satellite.Sentinel2,
                         candidate.satellite.Landsat)
               if m.min_temporal_offset_days is not None]
    if not offsets:
        return Rating.UNKNOWN
    best = min(offsets)
    if best <= window:
        return Rating.HIGH
    if best <= 3 * window:
        return Rating.MEDIUM
    return Rating.LOW
