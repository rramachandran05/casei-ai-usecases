"""Candidate inventory: flattened export to CSV/Parquet/JSON + query helpers."""

import json
from pathlib import Path

import pandas as pd

from casei_geofm.schemas.candidate import Candidate

OUTPUTS = Path("outputs")

# flattened column -> (section, field); section prefixes follow 01-spec.md §14
FILTER_COLUMNS = {
    "campaign": "casei_campaign",
    "phenomenon": "use_case_phenomenon",
    "task_family": "use_case_proposed_task",
    "label_provenance": "label_label_provenance",
    "compatibility_class": "compatibility_native_or_transformable",
    "evidence_level": "evidence_evidence_level",
    "label_value": "ranking_label_value",
    "prithvi_readiness": "ranking_prithvi_readiness",
}


def flatten(candidate: Candidate) -> dict:
    row: dict = {"candidate_id": candidate.candidate_id,
                 "retained_for_future_models": candidate.retained_for_future_models}
    for section in ("casei", "label", "use_case", "model", "satellite",
                    "compatibility", "transformation", "ranking", "evidence"):
        payload = getattr(candidate, section).model_dump()
        for key, value in payload.items():
            col = f"{section}_{key}"
            if isinstance(value, dict):
                for k2, v2 in value.items():
                    row[f"{col}_{k2}"] = v2
            elif isinstance(value, list):
                row[col] = json.dumps(value)
            else:
                row[col] = value
    return row


def to_dataframe(candidates: list[Candidate]) -> pd.DataFrame:
    return pd.DataFrame([flatten(c) for c in candidates])


def export(candidates: list[Candidate], out_dir: Path | str = OUTPUTS) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    df = to_dataframe(candidates)
    paths = {
        "csv": out_dir / "candidates.csv",
        "parquet": out_dir / "candidates.parquet",
        "json": out_dir / "candidates.json",
    }
    df.to_csv(paths["csv"], index=False)
    df.to_parquet(paths["parquet"], index=False)
    paths["json"].write_text(json.dumps([c.model_dump() for c in candidates], default=str))

    # round-trip row-count check (acceptance criterion)
    counts = {
        "csv": len(pd.read_csv(paths["csv"])) if len(df) else 0,
        "parquet": len(pd.read_parquet(paths["parquet"])),
        "json": len(json.loads(paths["json"].read_text())),
    }
    expected = len(df)
    mismatches = {k: v for k, v in counts.items() if v != expected}
    if mismatches:
        raise RuntimeError(f"export row-count mismatch vs {expected}: {mismatches}")
    print(f"exported {expected} candidates -> {out_dir}/candidates.{{csv,parquet,json}}")
    return paths


def load(path: Path | str = OUTPUTS / "candidates.parquet") -> pd.DataFrame:
    return pd.read_parquet(path)


def filter_candidates(df: pd.DataFrame, **filters) -> pd.DataFrame:
    """filter_candidates(df, phenomenon='flood', prithvi_readiness='HIGH', ...)
    Accepted keys: %s""" % ", ".join(FILTER_COLUMNS)
    out = df
    for key, value in filters.items():
        col = FILTER_COLUMNS.get(key)
        if col is None:
            raise KeyError(f"unknown filter '{key}'; use one of {sorted(FILTER_COLUMNS)}")
        out = out[out[col] == value]
    return out
