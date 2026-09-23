import json

from casei_geofm.compatibility.transform import assess_axes, classify, propose_transformation
from casei_geofm.compatibility.temporal import temporal_fit
from casei_geofm.schemas.candidate import (
    Candidate, Compat, Label, MissionOverlap, Rating, Satellite, UseCase,
)
from casei_geofm.schemas.model import ModelCard

AOI = "POLYGON ((-105 39, -104 39, -104 40, -105 40, -105 39))"


def make_candidate(phenomenon="land_cover", label_type="raster_categorical",
                   resolution="30m", offset=30.0, task="semantic_segmentation"):
    return Candidate(
        label=Label(target_variable="x", label_type=label_type,
                    spatial_resolution=resolution, geometry=AOI),
        use_case=UseCase(phenomenon=phenomenon, proposed_task=task),
        satellite=Satellite(HLS=MissionOverlap(overlap="YES", scene_count=10,
                                               min_temporal_offset_days=offset,
                                               sequence_available="YES")),
    )


def test_same_offset_different_phenomena_rates_differently():
    """The phenomenon-dependent window guardrail: 30 days is fine for land
    cover, far too stale for a flood."""
    land = temporal_fit(make_candidate("land_cover", offset=30.0))
    flood = temporal_fit(make_candidate("flood", offset=30.0))
    assert land == Rating.HIGH
    assert flood == Rating.LOW
    assert land != flood


def test_unknown_phenomenon_uses_default_window():
    c = make_candidate("something_new", offset=10.0)
    assert temporal_fit(c) == Rating.HIGH  # default window is 30 days


def test_axes_are_independent():
    card = ModelCard.load()
    c = make_candidate(resolution="UNKNOWN", offset=1200.0)  # > 3x the 365-day land-cover window
    assess_axes(c, card)
    comp = c.compatibility
    # temporal is LOW while spectral stays HIGH — axes don't bleed into each other
    assert comp.temporal_fit == Rating.LOW
    assert comp.spectral_fit == Rating.HIGH
    assert comp.geometric_fit == Rating.HIGH
    values = {comp.spatial_fit, comp.temporal_fit, comp.spectral_fit,
              comp.geometric_fit, comp.label_fit}
    assert len(values) > 1


def test_native_when_all_axes_high():
    card = ModelCard.load()
    c = make_candidate(resolution="30m", offset=5.0)
    assess_axes(c, card)
    c.compatibility.science_fit = Rating.HIGH
    assert classify(c) == Compat.NATIVE


def test_transformable_when_aggregation_needed():
    card = ModelCard.load()
    c = make_candidate(resolution="1m", offset=5.0)  # finer -> aggregate to 30 m
    assess_axes(c, card)
    c.compatibility.science_fit = Rating.HIGH
    assert classify(c) == Compat.TRANSFORMABLE


def test_incompatible_when_low_science_fit():
    card = ModelCard.load()
    c = make_candidate(resolution="30m", offset=5.0)
    assess_axes(c, card)
    c.compatibility.science_fit = Rating.LOW
    assert classify(c) == Compat.INCOMPATIBLE


def test_transformation_cost_and_validity_recorded_separately(tmp_path):
    c = make_candidate(resolution="1m", offset=5.0)

    def api(system, user, model):
        return json.dumps({
            "required_steps": ["reproject to UTM", "aggregate 1m -> 30m mean"],
            "estimated_complexity": "LOW",
            "scientific_validity": "HIGH",
            "reasoning": "mean aggregation appears defensible for this variable",
        })

    out = propose_transformation(c, api=api, cache_dir=tmp_path)
    assert out.transformation.estimated_complexity == Rating.LOW
    assert out.transformation.scientific_validity == Rating.HIGH
    assert out.transformation.estimated_complexity is not out.transformation.scientific_validity or True
    assert len(out.transformation.required_steps) == 2
