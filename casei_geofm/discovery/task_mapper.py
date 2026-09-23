"""Stage 2 — fan each supervision opportunity out into Candidate rows,
one per Campaign x Product x Target x Task tuple."""

import hashlib
import json
from pathlib import Path

import yaml

from casei_geofm.llm import call_stage
from casei_geofm.schemas.candidate import Candidate, CaseiRef, Evidence, Label, UseCase
from casei_geofm.schemas.llm_io import TaskMapperResponse

CONFIG_DIR = Path(__file__).parent.parent / "config"
STAGE2_DIR = Path("data/cache/stage2")

UNKNOWN = "UNKNOWN"


def _task_vocabulary() -> list[str]:
    return yaml.safe_load((CONFIG_DIR / "task_taxonomy.yaml").read_text())["task_families"]


def map_tasks(record: dict, opportunity: dict, api=None,
              cache_dir: Path | None = None) -> list[Candidate]:
    payload = {
        "task_vocabulary": _task_vocabulary(),
        "opportunity": opportunity,
        "product": {
            "product_name": record["product_name"],
            "campaigns": record["campaigns"],
            "platforms": record["platforms"],
            "focus_areas": record["focus_areas"],
        },
    }
    target_hash = hashlib.sha256(opportunity["target_variable"].encode()).hexdigest()[:8]
    uid = f"{record['product_id']}-{target_hash}"
    kwargs = {"cache_dir": cache_dir} if cache_dir else {}
    if api:
        kwargs["api"] = api
    resp: TaskMapperResponse = call_stage("task_mapper", uid, payload, TaskMapperResponse, **kwargs)

    candidates = []
    for task in resp.tasks:
        c = Candidate(
            casei=CaseiRef(
                campaign=record["campaigns"][0] if record["campaigns"] else UNKNOWN,
                campaign_id=record["campaign_ids"][0] if record["campaign_ids"] else UNKNOWN,
                product=record["product_name"],
                product_id=record["product_id"],
                doi=record["doi"],
                platform="; ".join(record["platforms"]) or UNKNOWN,
                instrument="; ".join(i["name"] for i in record["instruments"]) or UNKNOWN,
            ),
            label=Label(
                target_variable=opportunity["target_variable"],
                label_description=opportunity["label_description"],
                label_type=opportunity["label_type"],
                label_provenance=opportunity["label_provenance"],
                geometry=record["aoi_wkt"],
                spatial_resolution=opportunity.get("spatial_resolution", UNKNOWN),
                temporal_resolution=opportunity.get("temporal_resolution", UNKNOWN),
            ),
            use_case=UseCase(
                phenomenon=task.phenomenon,
                proposed_task=task.proposed_task,
                task_description=task.task_description,
                potential_science_question=task.potential_science_question,
            ),
            evidence=Evidence(
                evidence_level=1,
                metadata_evidence="; ".join(opportunity.get("evidence_quotes", [])) or UNKNOWN,
                reasoning=resp.reasoning,
                urls=[f"https://doi.org/{record['doi']}"] if record["doi"] != UNKNOWN else [],
            ),
        )
        candidates.append(c)
    return candidates


def run(records_by_id: dict[str, dict], stage1_results: list[dict],
        api=None, checkpoint_every: int = 25,
        out_dir: Path | str = STAGE2_DIR) -> list[Candidate]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[Candidate] = []
    with_opps = [r for r in stage1_results if r["opportunities"]]
    for n, result in enumerate(with_opps, 1):
        record = records_by_id[result["product_id"]]
        for opp in result["opportunities"]:
            candidates.extend(map_tasks(record, opp, api=api))
        if n % checkpoint_every == 0 or n == len(with_opps):
            (out_dir / "candidates.json").write_text(
                json.dumps([c.model_dump() for c in candidates]))
            print(f"  stage2: {n}/{len(with_opps)} products -> {len(candidates)} candidates")
    return candidates
