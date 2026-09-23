Status: Draft

# Plan: CASEI-to-Prithvi-EO Labeled Data Discovery Pilot

## Repo conventions used

- **Greenfield repo.** `Projects/casei-ai-usecases/` contains only `resources/` (project context, Prithvi-EO-2.0 model card, two adaptation case studies) and `specs/`. No code, no README, no project CLAUDE.md, not git-initialized. **No test suite found** — nothing to run as a sanity check.
- **Language/tooling (workspace default, no repo signal to override it):** Python with tests built in. Machine has Python 3.12.7 and `uv` (probed). Plan: `uv`-managed project (`pyproject.toml`), `pytest` for tests, `pydantic` for schemas, `httpx` for API calls, `shapely` for geometry, `pandas` + `pyarrow` for the inventory exports.
- **Git:** initialize the repo with the workspace `.gitignore` conventions (exclude `outputs/`, `data/cache/`, `.env`) before implementation is called done (per acceptance criteria).

## Probe findings the Plan is grounded in (verified 2026-09-23)

- **CASEI API confirmed live:** `https://admg.nasa-impact.net/api/<table>` returns full-table JSON in an `{success, message, data}` envelope — no pagination or auth observed. Endpoints verified (HTTP 200): `campaign` (194 records), `platform` (153), `instrument` (605), `deployment` (488), `doi` (2,607 — this *is* the data-product table), `collection_period`, `measurement_type`, `measurement_style`, `focus_area`, `geophysical_concept`, `season`, `repository`, `platform_type`, `gcmd_phenomenon`, `iop`, `significant_event`. Counts match the Spec's Explore figures exactly. Relationships are UUID references between tables.
- **The `doi` table already embeds CMR metadata:** every one of the 2,607 records has a CMR `concept_id`, plus `cmr_abstract`, `cmr_entry_title`, `cmr_data_formats`, `cmr_dates` (temporal ranges), `cmr_science_keywords`, `cmr_plats_and_insts`, and `date_queried`. Level-2 evidence therefore has a direct, deterministic path (concept_id → CMR collection lookup) with much of it pre-cached in CASEI itself.
- **Geometry is better than feared:** all 488/488 deployments carry `spatial_bounds` as EWKT polygons (`SRID=4326;POLYGON (...)`), plus start/end dates and `geographical_regions`. Candidate AOIs derive from deployment bounds; campaign-level fallback is the union of its deployments' bounds.
- **Satellite coincidence backend: NASA CMR granule search.** Verified: `https://cmr.earthdata.nasa.gov/search/granules.json?short_name=HLSL30&bounding_box=...&temporal=...` returns granules with `time_start` and `cloud_cover`. HLS short names `HLSL30`/`HLSS30` confirmed for HLSL30; the exact CMR short names for Landsat Collection 2 and Sentinel-2 are **TBD — confirm during implementation** (config-driven, so a pure config change).
- **Performance note:** the `doi` table download is slow (minutes); the raw JSON must be cached to disk and the first candidate-generation runs should work entirely from cache.
- **LLM backend (Spec TBD, resolved here):** Anthropic API, `claude-sonnet-5` default (config-switchable), with JSON-schema-constrained outputs validated by the pydantic candidate schemas. Every LLM call cached on `(stage, input_uuid, prompt_version)` so reruns are free and prompt revisions invalidate cleanly.

## ⚠️ Test suite risk

None pre-existing — the repo has no test suite at all. All tests are new; any failure found later is from this feature's own code, not inherited.

## Files/components to create

All paths are new (greenfield); the layout traces to the approved Spec §Proposed repo layout, adjusted only to add `tests/`, `data/cache/`, and packaging at repo root.

### Repo root
- `pyproject.toml` — uv project; deps: httpx, pydantic, shapely, pandas, pyarrow, anthropic, pytest, python-dotenv. Pytest configured as the single test command (`uv run pytest`).
- `README.md` — pipeline overview, run commands, link to `specs/`.
- `.gitignore` — workspace conventions + `data/cache/`, `outputs/`, `.env`.

### `casei_geofm/config/`
- `model_card.yaml` — Prithvi-EO-2.0 machine-readable compatibility spec, transcribed from [resources/prithvi-eo-2.0.yaml](../../resources/prithvi-eo-2.0.yaml) into the fields the compatibility engine consumes (bands, resolution, temporal context, supported satellites, task families, limitations).
- `task_taxonomy.yaml` — the 19 task families and ~21 label types + 5 provenance classes from the Spec.
- `phenomena_windows.yaml` — phenomenon-dependent temporal-compatibility windows (flood: hours–days; vegetation structure: days–months; land cover: months; extensible).
- `satellites.yaml` — CMR short names per mission (`HLSL30`, `HLSS30` verified; Landsat/Sentinel-2 entries marked TBD-confirm), mission date ranges, search order HLS → Sentinel-2 → Landsat.
- `examples.yaml` — optional example use cases (flood, burn scar, land cover, biomass, vegetation); loaded only into LLM prompt context, never into filters.

### `casei_geofm/casei/`
- `client.py` — thin ADMG API client: `fetch_table(name)` against the verified endpoint list, long timeouts + retry for `doi`, raw JSON persisted to `data/cache/casei/<table>.json`.
- `harvest.py` — orchestrates full-catalog download of all verified tables; emits a harvest summary (count per entity vs. expected figures).
- `normalize.py` — resolves UUID references into normalized linked records (campaign ↔ deployment ↔ platform ↔ instrument ↔ doi, with vocab tables joined in); parses EWKT `spatial_bounds` via shapely; missing values → `UNKNOWN`. Output: `data/cache/normalized.parquet` (+ JSON).

### `casei_geofm/schemas/`
- `model.py` — pydantic model for the model card.
- `candidate.py` — pydantic Candidate with the §14 field groups (CASEI, LABEL, USE_CASE, MODEL, SATELLITE, COMPATIBILITY, TRANSFORMATION, RANKING, EVIDENCE) + `evidence_level` (1/2/3) and `candidate_id` (deterministic hash of the defining tuple). Enums for provenance classes, NATIVE/TRANSFORMABLE/INCOMPATIBLE, HIGH/MEDIUM/LOW — no numeric score fields exist, by construction.
- `llm_io.py` — per-stage LLM request/response schemas; validators reject responses that supply values for fields the input marked `UNKNOWN`.

### `casei_geofm/llm.py`
- Anthropic client wrapper: schema-constrained calls, retry, and the `(stage, input_uuid, prompt_version)` disk cache under `data/cache/llm/`. Prompts live alongside as versioned templates (`casei_geofm/prompts/*.md`).

### `casei_geofm/discovery/`
- `label_detector.py` — Stage 1. Per data product (using CASEI description + `cmr_abstract`/`cmr_science_keywords`): label-opportunity judgment, label-taxonomy type, provenance class. Products with no opportunity retained as `NO_OBVIOUS_LABEL`.
- `task_mapper.py` — Stage 2. All plausible task-family mappings per opportunity; one Candidate row per Campaign × Product × Target × Task tuple.
- `science_mapper.py` — Stage 3. EO-observability rating (HIGH/MEDIUM/LOW) + rationale against the model card; LOW retained.

### `casei_geofm/satellite/`
- `cmr.py` — shared CMR granule-search client (verified endpoint), bbox + temporal query, returns scene count, times, cloud cover.
- `hls.py`, `sentinel2.py`, `landsat.py` — per-mission adapters over `cmr.py` using `satellites.yaml`; each records overlap, temporal offset, usable scenes, sequence availability. Pre-HLS candidates fall through to Landsat by mission date range, not rejection.
- `coincidence.py` — Stage 4 orchestrator: derives AOI (deployment `spatial_bounds`; campaign union fallback; else `UNKNOWN` + named missing prerequisite) and runs the ordered search.

### `casei_geofm/compatibility/`
- `spatial.py`, `temporal.py`, `spectral.py`, `geometric.py`, `label.py` — five independent axis assessments (temporal uses `phenomena_windows.yaml`; spectral checks constructibility of the six-band HLS input from found scenes).
- `transform.py` — NATIVE/TRANSFORMABLE/INCOMPATIBLE classification; for TRANSFORMABLE, records steps, complexity, and scientific validity as separate fields (LLM proposes steps; deterministic code stores/validates structure).

### `casei_geofm/ranking/`
- `ranker.py` — Stage 7: two independent LLM-reasoned rankings (label-value, Prithvi-readiness) + novelty + overall priority, each with written rationale referencing the ten Spec factors; Level-1 phrasing lint applied to rationale text.

### `casei_geofm/evidence.py`
- Evidence-level tracker: all candidates start Level 1; `promote_level2(candidate)` fetches the CMR collection by `concept_id` and confirms/corrects variables, formats, resolution, geography, temporal coverage; `promote_level3(candidate)` opens a representative granule (HIGH-tier sample only) and verifies coordinates/dimensions/ranges. Promotions record what changed.

### `casei_geofm/inventory.py`
- Export to CSV/Parquet/JSON in `outputs/`; round-trip row-count check; documented query interface (pandas/DuckDB filter helpers by campaign, phenomenon, task family, provenance, compatibility, evidence level, rankings).

### `casei_geofm/report.py`
- Pilot metrics report (all eight §20 measures) + stratified human-review packet generator (sampling across priority tiers, provenance classes, task families).

### `run_pipeline.py`
- CLI entry: `harvest | discover | coincide | assess | rank | export | report`, each stage resumable from cache/checkpoints; `--limit N` for smoke runs.

## Implementation phases

1. **Phase 0 — scaffolding:** git init, pyproject, package skeleton, configs, schemas. Smoke test: schemas instantiate.
2. **Phase 1 — harvest + normalize** (pure deterministic; no LLM): full catalog cached and normalized; harvest summary matches expected counts.
3. **Phase 2 — satellite coincidence** (deterministic; independently testable against cached deployments before any candidates exist).
4. **Phase 3 — LLM discovery stages** (label detector → task mapper → science mapper), first on a `--limit 25` stratified slice to tune prompts, then full catalog.
5. **Phase 4 — compatibility + ranking + evidence promotion.**
6. **Phase 5 — exports, metrics report, human-review packet.**
7. **Phase 6 — Mode B agent prototype spec** (written deliverable, authored via `akd_care_design_process`; lives in `specs/` or `outputs/`, not code).

## Tests to add (all new, under `tests/`; each maps to an Acceptance Criterion)

- `tests/test_configs.py` — model card and taxonomy files parse and contain required fields (AC: inputs & configuration).
- `tests/test_normalize.py` — UUID relationship resolution on fixture records; EWKT parsing (verified sample format); metadata-sparse record flows through with `UNKNOWN`, nothing fabricated (AC: harvest & cache).
- `tests/test_cache.py` — second run issues zero API calls with network mocked off (AC: cache hit).
- `tests/test_candidates.py` — tuple-level `candidate_id` stability; one product → multiple candidates; `NO_OBVIOUS_LABEL` retention; empty-examples run completes (AC: candidate generation).
- `tests/test_coincidence.py` — mocked CMR responses: ordered HLS→S2→Landsat search; pre-2013 campaign resolves to Landsat, not rejection; missing geometry → `UNKNOWN` + named prerequisite (AC: satellite coincidence).
- `tests/test_compatibility.py` — five axes independent; identical temporal offset under different phenomena yields different ratings; TRANSFORMABLE records cost and validity separately (AC: compatibility).
- `tests/test_ranking.py` — two rankings present and independent; no numeric score fields; rationale references ranking factors (schema-level checks; mocked LLM) (AC: ranking).
- `tests/test_evidence.py` — Level-1 phrasing lint rejects "confirmed/verified" claims; promotion records changes (AC: evidence guardrails).
- `tests/test_llm_guardrails.py` — mocked LLM response inventing a value for an `UNKNOWN` input field is rejected/flagged (AC: engineering quality).
- `tests/test_inventory.py` — CSV/Parquet/JSON round-trip with equal row counts; filter helpers work on all required dimensions (AC: outputs).
- **Live smoke tests** (marked `@pytest.mark.network`, excluded from default run): one real CASEI table fetch, one real CMR HLSL30 query — the two probed calls this Plan is grounded in.

## Risks / notes

- **LLM cost/scale:** ~2,607 products × 3–4 semantic stages. The `--limit` slice + per-stage caching keeps iteration cheap; a full run is a deliberate, budgeted action.
- **CMR short names for Landsat C2 / Sentinel-2 not yet confirmed** — config-only fix; flagged as TBD in `satellites.yaml` and in the harvest phase of Tasks.
- **CASEI API has no observed pagination/auth** — if either appears at scale, it's confined to `client.py`.
- **Human review** requires an EO-scientist pass (per Spec open question) — the pipeline produces the packet; scheduling the review is outside the code.
