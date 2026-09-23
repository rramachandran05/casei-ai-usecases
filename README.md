# CASEI-to-Prithvi-EO Labeled Data Discovery Pilot

Mines NASA's [CASEI](https://impact.earthdata.nasa.gov/casei/) airborne/field campaign
catalog for supervision opportunities usable to adapt Earth-observation foundation
models, using Prithvi-EO-2.0 as the reference model. Full design: `specs/casei-geofm-discovery-pilot/`
(Spec → Acceptance Criteria → Plan → Tasks) and `resources/project-context.txt`.

Pipeline: **model card → CASEI harvest → label opportunity detection → task inference →
satellite coincidence (CMR) → compatibility → dual ranking → searchable candidate inventory.**

## Run

```bash
uv sync
uv run pytest                          # unit tests (network tests deselected)
uv run pytest -m network               # live API smoke tests
uv run python run_pipeline.py harvest  # full CASEI catalog -> data/cache/
uv run python run_pipeline.py discover --limit 25   # LLM stages (needs ANTHROPIC_API_KEY)
uv run python run_pipeline.py coincide
uv run python run_pipeline.py assess
uv run python run_pipeline.py rank
uv run python run_pipeline.py export   # -> outputs/candidates.{csv,parquet,json}
uv run python run_pipeline.py report   # -> outputs/pilot_metrics.md + review packet
```

Stages are resumable: every CASEI/CMR/LLM call is cached under `data/cache/` and
reruns are free. `--limit N` runs any stage on a slice.

## Querying the inventory

```python
from casei_geofm.inventory import load, filter_candidates
df = load("outputs/candidates.parquet")
filter_candidates(df, phenomenon="flood", label_provenance="DIRECT_LABEL",
                  prithvi_readiness="HIGH")
```
