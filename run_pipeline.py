"""CLI entry for the CASEI-GeoFM discovery pipeline.

Stages: harvest | discover | coincide | assess | rank | export | report
Every stage resumes from its cache/checkpoints; --limit N runs a slice.
"""

import argparse
import json
from pathlib import Path

from casei_geofm.schemas.candidate import Candidate

STAGE2_CANDIDATES = Path("data/cache/stage2/candidates.json")
STAGE4_CANDIDATES = Path("data/cache/stage4/candidates.json")
STAGE5_CANDIDATES = Path("data/cache/stage5/candidates.json")
STAGE7_CANDIDATES = Path("data/cache/stage7/candidates.json")


def load_candidates(path: Path) -> list[Candidate]:
    if not path.exists():
        raise SystemExit(f"{path} missing — run the previous stage first")
    return [Candidate(**c) for c in json.loads(path.read_text())]


def save_candidates(candidates: list[Candidate], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([c.model_dump() for c in candidates]))


def load_normalized() -> list[dict]:
    normalized = Path("data/cache/normalized.json")
    if not normalized.exists():
        raise SystemExit("normalized cache missing — run `harvest` first")
    return json.loads(normalized.read_text())


def cmd_harvest(args) -> None:
    from casei_geofm.casei.harvest import harvest_all
    from casei_geofm.casei.normalize import run as normalize_run
    harvest_all()
    normalize_run()


def cmd_discover(args) -> None:
    from casei_geofm.discovery import label_detector, task_mapper
    records = load_normalized()
    results = label_detector.run(records, limit=args.limit)
    records_by_id = {r["product_id"]: r for r in records}
    candidates = task_mapper.run(records_by_id, results)
    print(f"discover: {len(results)} products -> {len(candidates)} candidates")


def cmd_coincide(args) -> None:
    from casei_geofm.satellite.coincidence import assess_coincidence
    candidates = load_candidates(STAGE2_CANDIDATES)
    if args.limit:
        candidates = candidates[: args.limit]
    records_by_id = {r["product_id"]: r for r in load_normalized()}
    for n, c in enumerate(candidates, 1):
        record = records_by_id.get(c.casei.product_id, {})
        windows = record.get("deployment_windows") or []
        starts = sorted(w["start"] for w in windows if w["start"] != "UNKNOWN")
        ends = sorted(w["end"] for w in windows if w["end"] != "UNKNOWN")
        c.satellite = assess_coincidence(
            c.label.geometry,
            starts[0] if starts else "UNKNOWN",
            ends[-1] if ends else "UNKNOWN",
        )
        if n % 25 == 0 or n == len(candidates):
            save_candidates(candidates, STAGE4_CANDIDATES)
            print(f"  stage4: {n}/{len(candidates)}")
    save_candidates(candidates, STAGE4_CANDIDATES)


def cmd_assess(args) -> None:
    from casei_geofm.discovery import science_mapper
    from casei_geofm.compatibility import transform
    candidates = load_candidates(STAGE4_CANDIDATES)
    if args.limit:
        candidates = candidates[: args.limit]
    candidates = science_mapper.run(candidates)
    candidates = transform.run(candidates)
    save_candidates(candidates, STAGE5_CANDIDATES)


def cmd_rank(args) -> None:
    from casei_geofm.ranking import ranker
    candidates = load_candidates(STAGE5_CANDIDATES)
    if args.limit:
        candidates = candidates[: args.limit]
    candidates = ranker.run(candidates)
    save_candidates(candidates, STAGE7_CANDIDATES)


def cmd_export(args) -> None:
    from casei_geofm.inventory import export
    export(load_candidates(STAGE7_CANDIDATES))


def cmd_report(args) -> None:
    from casei_geofm.report import pilot_metrics, review_packet
    candidates = load_candidates(STAGE7_CANDIDATES)
    # "examined" = products that actually went through Stage 1, not the whole cache
    stage1 = Path("data/cache/stage1/results.json")
    n_examined = len(json.loads(stage1.read_text())) if stage1.exists() else 0
    pilot_metrics(candidates, n_examined)
    review_packet(candidates)


COMMANDS = {
    "harvest": cmd_harvest,
    "discover": cmd_discover,
    "coincide": cmd_coincide,
    "assess": cmd_assess,
    "rank": cmd_rank,
    "export": cmd_export,
    "report": cmd_report,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="CASEI-GeoFM discovery pipeline")
    parser.add_argument("stage", choices=COMMANDS)
    parser.add_argument("--limit", type=int, default=None, help="run on a slice of N records")
    args = parser.parse_args()
    COMMANDS[args.stage](args)


if __name__ == "__main__":
    main()
