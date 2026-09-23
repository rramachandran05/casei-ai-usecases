"""Stage 3 — EO-observability (science fit) against the model card.
LOW candidates are flagged for future models, never filtered."""

import json
from pathlib import Path

from casei_geofm.llm import call_stage
from casei_geofm.schemas.candidate import Candidate, Rating
from casei_geofm.schemas.llm_io import ScienceFitResponse
from casei_geofm.schemas.model import ModelCard

STAGE3_DIR = Path("data/cache/stage3")


def assess(candidate: Candidate, card: ModelCard, api=None,
           cache_dir: Path | None = None) -> Candidate:
    payload = {
        "model_card": {
            "name": card.name,
            "bands": card.input.bands,
            "spatial_resolution_m": card.input.spatial_resolution_m,
            "temporal_context": card.input.temporal_context.model_dump(),
            "constraints": card.constraints,
        },
        "candidate": {
            "target_variable": candidate.label.target_variable,
            "label_type": candidate.label.label_type,
            "proposed_task": candidate.use_case.proposed_task,
            "phenomenon": candidate.use_case.phenomenon,
            "task_description": candidate.use_case.task_description,
        },
    }
    kwargs = {"cache_dir": cache_dir} if cache_dir else {}
    if api:
        kwargs["api"] = api
    resp: ScienceFitResponse = call_stage(
        "science_mapper", candidate.candidate_id, payload, ScienceFitResponse, **kwargs)
    candidate.compatibility.science_fit = resp.science_fit
    candidate.evidence.reasoning += f"\nScience fit: {resp.reasoning}"
    if resp.science_fit == Rating.LOW:
        candidate.retained_for_future_models = True
    return candidate


def run(candidates: list[Candidate], api=None, checkpoint_every: int = 50,
        out_dir: Path | str = STAGE3_DIR) -> list[Candidate]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    card = ModelCard.load()
    for n, c in enumerate(candidates, 1):
        assess(c, card, api=api)
        if n % checkpoint_every == 0 or n == len(candidates):
            (out_dir / "candidates.json").write_text(
                json.dumps([x.model_dump() for x in candidates]))
            print(f"  stage3: {n}/{len(candidates)} assessed")
    return candidates
