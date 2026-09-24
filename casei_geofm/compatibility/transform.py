"""Combine the five axes into NATIVE / TRANSFORMABLE / INCOMPATIBLE and, for
TRANSFORMABLE candidates, ask the LLM for the transformation pipeline with
cost and scientific validity recorded as SEPARATE fields."""

import json
from pathlib import Path

from casei_geofm.compatibility.geometric import geometric_fit
from casei_geofm.compatibility.label import label_fit
from casei_geofm.compatibility.spatial import spatial_fit
from casei_geofm.compatibility.spectral import spectral_fit
from casei_geofm.compatibility.temporal import temporal_fit
from casei_geofm.llm import call_stage
from casei_geofm.schemas.candidate import Candidate, Compat, Rating
from casei_geofm.schemas.llm_io import TransformResponse
from casei_geofm.schemas.model import ModelCard

STAGE5_DIR = Path("data/cache/stage5")


def assess_axes(candidate: Candidate, card: ModelCard,
                windows: dict | None = None) -> Candidate:
    comp = candidate.compatibility
    comp.spatial_fit = spatial_fit(candidate, card)
    comp.temporal_fit = temporal_fit(candidate, windows)
    comp.spectral_fit = spectral_fit(candidate, card)
    comp.geometric_fit = geometric_fit(candidate)
    comp.label_fit = label_fit(candidate)
    return candidate


def classify(candidate: Candidate) -> Compat:
    comp = candidate.compatibility
    axes = [comp.spatial_fit, comp.temporal_fit, comp.spectral_fit,
            comp.geometric_fit, comp.label_fit]
    if comp.science_fit == Rating.LOW:
        # scientifically implausible for this model's inputs
        return Compat.INCOMPATIBLE
    if any(a == Rating.LOW for a in (comp.spectral_fit, comp.geometric_fit, comp.label_fit)):
        return Compat.INCOMPATIBLE
    if all(a == Rating.HIGH for a in axes):
        return Compat.NATIVE
    if any(a == Rating.UNKNOWN for a in axes) and not any(a == Rating.MEDIUM for a in axes):
        return Compat.UNKNOWN
    return Compat.TRANSFORMABLE


def overall_rating(candidate: Candidate) -> Rating:
    comp = candidate.compatibility
    axes = [comp.science_fit, comp.spatial_fit, comp.temporal_fit,
            comp.spectral_fit, comp.geometric_fit, comp.label_fit]
    known = [a for a in axes if a != Rating.UNKNOWN]
    if not known:
        return Rating.UNKNOWN
    if any(a == Rating.LOW for a in known):
        return Rating.LOW
    if all(a == Rating.HIGH for a in known):
        return Rating.HIGH
    return Rating.MEDIUM


def propose_transformation(candidate: Candidate, api=None,
                           cache_dir: Path | None = None) -> Candidate:
    payload = {
        "candidate": {
            "target_variable": candidate.label.target_variable,
            "label_type": candidate.label.label_type,
            "label_spatial_resolution": candidate.label.spatial_resolution,
            "proposed_task": candidate.use_case.proposed_task,
            "axes": {
                "spatial": candidate.compatibility.spatial_fit,
                "temporal": candidate.compatibility.temporal_fit,
                "geometric": candidate.compatibility.geometric_fit,
                "label": candidate.compatibility.label_fit,
            },
        },
        "model_grid": "30 m HLS six-band reflectance, 224x224 tiles",
    }
    kwargs = {"cache_dir": cache_dir} if cache_dir else {}
    if api:
        kwargs["api"] = api
    resp: TransformResponse = call_stage(
        "transform", candidate.candidate_id, payload, TransformResponse, **kwargs)
    candidate.transformation.required_steps = resp.required_steps
    candidate.transformation.estimated_complexity = resp.estimated_complexity
    candidate.transformation.scientific_validity = resp.scientific_validity
    candidate.evidence.reasoning += f"\nTransformation: {resp.reasoning}"
    return candidate


def run(candidates: list[Candidate], api=None, checkpoint_every: int = 50,
        out_dir: Path | str = STAGE5_DIR) -> list[Candidate]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    card = ModelCard.load()
    failed = 0
    for n, c in enumerate(candidates, 1):
        assess_axes(c, card)
        c.compatibility.native_or_transformable = classify(c)
        c.compatibility.overall_compatibility = overall_rating(c)
        if c.compatibility.native_or_transformable == Compat.TRANSFORMABLE:
            try:
                propose_transformation(c, api=api)
            except RuntimeError as e:
                failed += 1
                c.evidence.uncertainties += f" [transform proposal failed: {e}]"
        if n % checkpoint_every == 0 or n == len(candidates):
            (out_dir / "candidates.json").write_text(
                json.dumps([x.model_dump() for x in candidates]))
            print(f"  stage5: {n}/{len(candidates)} assessed")
    return candidates
