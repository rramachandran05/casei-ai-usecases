"""Stage 7 — dual independent rankings with written rationale.
Label-value and Prithvi-readiness are never collapsed into one score."""

import json
import re
from pathlib import Path

import yaml

from casei_geofm.llm import call_stage
from casei_geofm.schemas.llm_io import RankingResponse
from casei_geofm.schemas.candidate import Candidate

CONFIG_DIR = Path(__file__).parent.parent / "config"
STAGE7_DIR = Path("data/cache/stage7")

# Confirmatory phrasing forbidden on Level-1 (metadata-inference) candidates.
LEVEL1_FORBIDDEN = re.compile(
    r"\b(confirmed|verified|proven|validated|is a training dataset|"
    r"ready[- ]to[- ]use training)\b", re.IGNORECASE)


class Level1PhrasingError(ValueError):
    """Level-1 rationale claimed confirmation it does not have."""


def lint_level1_phrasing(candidate: Candidate) -> None:
    if candidate.evidence.evidence_level > 1:
        return
    for text in (candidate.ranking.label_value_reasoning,
                 candidate.ranking.prithvi_readiness_reasoning,
                 candidate.evidence.reasoning):
        m = LEVEL1_FORBIDDEN.search(text or "")
        if m:
            raise Level1PhrasingError(
                f"Level-1 candidate {candidate.candidate_id} uses confirmatory "
                f"phrasing: {m.group(0)!r}")


def rank(candidate: Candidate, api=None, cache_dir: Path | None = None) -> Candidate:
    examples = yaml.safe_load((CONFIG_DIR / "examples.yaml").read_text()) or {}
    payload = {
        "example_use_cases_novelty_reference": examples.get("examples", []),
        "candidate": {
            "target_variable": candidate.label.target_variable,
            "label_type": candidate.label.label_type,
            "label_provenance": candidate.label.label_provenance,
            "phenomenon": candidate.use_case.phenomenon,
            "proposed_task": candidate.use_case.proposed_task,
            "science_fit": candidate.compatibility.science_fit,
            "compatibility_axes": candidate.compatibility.model_dump(),
            "native_or_transformable": candidate.compatibility.native_or_transformable,
            "transformation": candidate.transformation.model_dump(),
            "satellite": candidate.satellite.model_dump(),
            "evidence_level": candidate.evidence.evidence_level,
        },
    }
    kwargs = {"cache_dir": cache_dir} if cache_dir else {}
    if api:
        kwargs["api"] = api
    resp: RankingResponse = call_stage(
        "ranker", candidate.candidate_id, payload, RankingResponse, **kwargs)
    r = candidate.ranking
    r.label_value = resp.label_value
    r.label_value_reasoning = resp.label_value_reasoning
    r.prithvi_readiness = resp.prithvi_readiness
    r.prithvi_readiness_reasoning = resp.prithvi_readiness_reasoning
    r.novelty = resp.novelty
    r.overall_priority = resp.overall_priority
    lint_level1_phrasing(candidate)
    return candidate


def run(candidates: list[Candidate], api=None, checkpoint_every: int = 50,
        out_dir: Path | str = STAGE7_DIR) -> list[Candidate]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for n, c in enumerate(candidates, 1):
        rank(c, api=api)
        if n % checkpoint_every == 0 or n == len(candidates):
            (out_dir / "candidates.json").write_text(
                json.dumps([x.model_dump() for x in candidates]))
            print(f"  stage7: {n}/{len(candidates)} ranked")
    return candidates
