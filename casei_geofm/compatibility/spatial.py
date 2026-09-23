"""Spatial compatibility: can the label align with the model's grid?"""

import re

from casei_geofm.compatibility.types import RASTER_TYPES, SPARSE_TYPES, UNKNOWN, VECTOR_TYPES
from casei_geofm.schemas.candidate import Candidate, Rating
from casei_geofm.schemas.model import ModelCard


def resolution_meters(text: str) -> float | None:
    """Parse resolutions like '30m', '1 m', '0.5 km'; None when unparseable."""
    if not text or text == UNKNOWN:
        return None
    m = re.search(r"([\d.]+)\s*(km|m)\b", text.lower())
    if not m:
        return None
    val = float(m.group(1))
    return val * 1000 if m.group(2) == "km" else val


def spatial_fit(candidate: Candidate, card: ModelCard) -> Rating:
    target = card.input.spatial_resolution_m
    res = resolution_meters(candidate.label.spatial_resolution)
    ltype = candidate.label.label_type
    if res is not None:
        if res > 10 * target:
            return Rating.LOW           # far coarser than the model grid
        if 0.5 * target <= res <= 2 * target:
            return Rating.HIGH          # near-native
        return Rating.MEDIUM            # finer -> aggregable
    if ltype in RASTER_TYPES or ltype in VECTOR_TYPES:
        return Rating.MEDIUM            # rasterizable/aggregable, resolution unstated
    if ltype in SPARSE_TYPES:
        return Rating.MEDIUM if candidate.label.geometry != UNKNOWN else Rating.LOW
    return Rating.UNKNOWN
