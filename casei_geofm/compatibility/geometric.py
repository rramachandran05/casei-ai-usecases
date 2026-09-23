"""Geometric compatibility: georeferencable / reprojectable / rasterizable?"""

from casei_geofm.compatibility.types import RASTER_TYPES, SPARSE_TYPES, UNKNOWN, VECTOR_TYPES
from casei_geofm.schemas.candidate import Candidate, Rating


def geometric_fit(candidate: Candidate) -> Rating:
    if candidate.label.geometry == UNKNOWN:
        return Rating.LOW
    ltype = candidate.label.label_type
    if ltype in RASTER_TYPES or ltype in VECTOR_TYPES:
        return Rating.HIGH
    if ltype in SPARSE_TYPES:
        return Rating.MEDIUM
    return Rating.UNKNOWN
