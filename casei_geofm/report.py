"""Pilot metrics report (the eight measures from 01-spec.md §Success measures)
and the stratified human-review packet."""

import json
from collections import Counter
from pathlib import Path

import yaml

from casei_geofm.schemas.candidate import Candidate

OUTPUTS = Path("outputs")
CONFIG_DIR = Path(__file__).parent / "config"


def compute_metrics(candidates: list[Candidate], n_products_examined: int,
                    n_products_total: int = 2607) -> dict:
    products_with_opps = {c.casei.product_id for c in candidates
                          if c.label.label_provenance != "NO_OBVIOUS_LABEL"}
    examples = set((yaml.safe_load((CONFIG_DIR / "examples.yaml").read_text()) or {})
                   .get("examples", []))
    # crude but honest novelty proxy: phenomena outside the example list,
    # refined by the ranker's novelty rating when present
    novel_phenomena = {c.use_case.phenomenon for c in candidates
                       if c.use_case.phenomenon not in examples
                       and c.use_case.phenomenon != "UNKNOWN"
                       and c.ranking.novelty == "HIGH"}
    coincident = [c for c in candidates
                  if any(m.overlap == "YES" for m in
                         (c.satellite.HLS, c.satellite.Sentinel2, c.satellite.Landsat))]
    return {
        "catalog_coverage": {
            "products_examined": n_products_examined,
            "products_total": n_products_total,
            "pct": round(100 * n_products_examined / n_products_total, 1),
        },
        "opportunity_yield": {
            "products_with_at_least_one_opportunity": len(products_with_opps),
            "pct_of_examined": round(100 * len(products_with_opps) / n_products_examined, 1)
            if n_products_examined else 0,
        },
        "task_diversity": dict(Counter(c.use_case.proposed_task for c in candidates)),
        "label_diversity": {
            "by_type": dict(Counter(c.label.label_type for c in candidates)),
            "by_provenance": dict(Counter(c.label.label_provenance for c in candidates)),
        },
        "compatibility": dict(Counter(
            c.compatibility.native_or_transformable for c in candidates)),
        "satellite_coincidence": {
            "candidates_with_viable_scenes": len(coincident),
            "pct": round(100 * len(coincident) / len(candidates), 1) if candidates else 0,
        },
        "novel_discovery": {
            "high_novelty_phenomena_outside_examples": sorted(novel_phenomena),
            "count": len(novel_phenomena),
        },
        "human_agreement": "PENDING — awaits EO-scientist review of the packet",
    }


def pilot_metrics(candidates: list[Candidate], n_products_examined: int,
                  out_dir: Path | str = OUTPUTS) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    m = compute_metrics(candidates, n_products_examined)
    lines = [
        "# Pilot Metrics — CASEI-to-Prithvi-EO Discovery",
        "",
        f"- **Catalog coverage:** {m['catalog_coverage']['products_examined']}/"
        f"{m['catalog_coverage']['products_total']} products examined "
        f"({m['catalog_coverage']['pct']}%)",
        f"- **Opportunity yield:** {m['opportunity_yield']['products_with_at_least_one_opportunity']} "
        f"products with ≥1 opportunity ({m['opportunity_yield']['pct_of_examined']}% of examined)",
        f"- **Task diversity:** {len(m['task_diversity'])} task families — "
        + ", ".join(f"{k} ({v})" for k, v in
                    sorted(m["task_diversity"].items(), key=lambda kv: -kv[1])),
        f"- **Label diversity:** {len(m['label_diversity']['by_type'])} label types; provenance: "
        + ", ".join(f"{k} ({v})" for k, v in m["label_diversity"]["by_provenance"].items()),
        f"- **Compatibility:** " + ", ".join(f"{k} ({v})" for k, v in m["compatibility"].items()),
        f"- **Satellite coincidence:** {m['satellite_coincidence']['candidates_with_viable_scenes']} "
        f"candidates with viable scenes ({m['satellite_coincidence']['pct']}%)",
        f"- **Novel discovery:** {m['novel_discovery']['count']} HIGH-novelty phenomena outside "
        f"the examples: {', '.join(m['novel_discovery']['high_novelty_phenomena_outside_examples']) or 'none yet'}",
        f"- **Human agreement:** {m['human_agreement']}",
    ]
    path = out_dir / "pilot_metrics.md"
    path.write_text("\n".join(lines) + "\n")
    (out_dir / "pilot_metrics.json").write_text(json.dumps(m, indent=1))
    print(f"metrics -> {path}")
    return path


def stratified_sample(candidates: list[Candidate], per_stratum: int = 3) -> list[Candidate]:
    """Sample across priority tiers x provenance classes x task families."""
    chosen: dict[str, Candidate] = {}
    for key_fn in (
        lambda c: f"priority:{c.ranking.overall_priority}",
        lambda c: f"provenance:{c.label.label_provenance}",
        lambda c: f"task:{c.use_case.proposed_task}",
    ):
        buckets: dict[str, list[Candidate]] = {}
        for c in candidates:
            buckets.setdefault(key_fn(c), []).append(c)
        for bucket in buckets.values():
            for c in bucket[:per_stratum]:
                chosen[c.candidate_id] = c
    return list(chosen.values())


def review_packet(candidates: list[Candidate], out_dir: Path | str = OUTPUTS,
                  per_stratum: int = 3) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = stratified_sample(candidates, per_stratum)
    blocks = [
        "# Human Review Packet — stratified sample",
        "",
        f"{len(sample)} candidates sampled across priority tiers, provenance classes,",
        "and task families. For each: mark **Agree / Disagree** on (a) the label",
        "interpretation and (b) the compatibility reasoning, and add notes.",
        "",
    ]
    for c in sample:
        blocks += [
            f"## {c.candidate_id} — {c.label.target_variable} ({c.use_case.proposed_task})",
            f"- Campaign/product: {c.casei.campaign} / {c.casei.product}",
            f"- Label: {c.label.label_type}, {c.label.label_provenance}",
            f"- Phenomenon: {c.use_case.phenomenon} | Science fit: {c.compatibility.science_fit}",
            f"- Compatibility: {c.compatibility.native_or_transformable} | "
            f"Priority: {c.ranking.overall_priority} | Evidence level: {c.evidence.evidence_level}",
            f"- Evidence: {c.evidence.metadata_evidence}",
            f"- Reasoning: {c.ranking.label_value_reasoning}",
            "- **Label interpretation:** [ ] Agree  [ ] Disagree — notes:",
            "- **Compatibility reasoning:** [ ] Agree  [ ] Disagree — notes:",
            "",
        ]
    path = out_dir / "human_review_packet.md"
    path.write_text("\n".join(blocks))
    print(f"review packet ({len(sample)} candidates) -> {path}")
    return path
