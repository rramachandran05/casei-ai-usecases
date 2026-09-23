"""Spectral/input compatibility: can the model's six-band input be built
from the coincident imagery found in Stage 4?"""

from casei_geofm.schemas.candidate import Candidate, Rating
from casei_geofm.schemas.model import ModelCard


def spectral_fit(candidate: Candidate, card: ModelCard) -> Rating:
    missions = (candidate.satellite.HLS, candidate.satellite.Sentinel2,
                candidate.satellite.Landsat)
    # all three configured missions carry the six bands common to
    # Landsat/Sentinel-2 that the model card requires
    if any(m.overlap == "YES" for m in missions):
        return Rating.HIGH
    if all(m.overlap == "NO" for m in missions):
        return Rating.LOW
    return Rating.UNKNOWN
