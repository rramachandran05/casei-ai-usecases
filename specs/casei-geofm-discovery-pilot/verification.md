# Verification Checklist — build session 2026-09-23

Status of each acceptance-criteria group in `02-acceptance-criteria.md` after the
initial build. Test suite: **60 passed** (`uv run pytest`), plus 3 live
`network`-marked smoke tests passed individually (CASEI table fetch, CMR HLS
granule query, CMR collection DOI lookup).

## ✅ Met (verified by passing tests / real runs)

- **Inputs & configuration** — all five config files exist, parse, and carry the
  required fields (`test_configs.py`); empty-examples run verified (`test_candidates.py`).
- **Harvest & cache** — full catalog harvested and cached (18 tables; counts match
  Explore figures exactly: 194/153/605/488/2607); zero-network cache hits verified
  (`test_cache.py`); sparse records flow through as `UNKNOWN` (`test_normalize.py`).
- **Candidate generation** — tuple-level stable `candidate_id`s, multi-candidate
  fan-out, `NO_OBVIOUS_LABEL` retention, LOW-science-fit retention (`test_candidates.py`)
  — with mocked LLM.
- **Satellite coincidence** — ordered HLS→S2→Landsat search, pre-HLS Landsat
  fallthrough, missing-prerequisite handling (`test_coincidence.py`); live HLS query
  verified.
- **Compatibility & ranking** — five independent axes, phenomenon-dependent windows
  (same offset rates differently for flood vs land cover), cost/validity separated,
  dual divergent rankings, no numeric scores (`test_compatibility.py`, `test_ranking.py`).
- **Evidence guardrails** — Level-1 phrasing lint, invented-`UNKNOWN` rejection,
  ordered promotion with logged changes (`test_evidence.py`, `test_llm_guardrails.py`).
- **Outputs machinery** — three-format round-trip export, all eight filter
  dimensions (`test_inventory.py`); metrics report + stratified review packet
  render (`test_report.py`).
- **Engineering quality** — deterministic/LLM split as specified; per-stage caching;
  single test command; repo git-initialized with workspace `.gitignore`.

## ⚠️ Deviations from the Plan (documented, verified better than planned)

- **Satellite backends:** CMR does not index USGS Landsat C2 or global Sentinel-2
  granules (verified: 0 results). Landsat uses USGS LandsatLook STAC
  (`landsat-c2l2-sr`, verified for 1995) and Sentinel-2 uses Element84 Earth Search
  (`sentinel-2-l2a`, verified for 2022). Config-driven in `satellites.yaml`; the
  per-mission `hls.py`/`sentinel2.py`/`landsat.py` files collapsed into the shared
  `cmr.py` + config (allowed by Task 6).
- **CMR concept_id staleness:** only 5/12 sampled CASEI concept_ids still resolve
  (2021-era ids; DAAC cloud migrations). `evidence.py` falls back to DOI lookup,
  which resolves the migrated records (verified live).
- Compatibility axes live in `spatial/temporal/spectral/geometric/label.py` plus a
  shared `types.py` (Plan's five files, one addition).

## ⏸ Not yet met — blocked or pending

- **Task 14 (LLM slice + full-catalog run):** BLOCKED on either an
  `ANTHROPIC_API_KEY` or a one-time `claude` CLI login (the `claude_cli` backend
  is installed and unit-tested; run `claude` then `/login` to activate it).
  Estimated full-run volume: ~2,607 Stage-1 calls, then (yield-dependent) roughly
  10,000–20,000 total calls across stages 2/3/5/7; order-of-magnitude ~40–60M
  input tokens. Run `discover --limit 25` first to tune prompts. All calls cache;
  reruns are free.
- **Level 2/3 promotion at scale** — machinery tested; real promotion runs follow
  the full discovery run (Level 2 for HIGH+MEDIUM, Level 3 for a HIGH sample).
- **Pilot metrics with real numbers, human-review outcomes** — follow Task 14 and
  the EO-scientist review (human_agreement is PENDING by design until then).
- **Task 16 (Mode B agent spec via AKD CARE)** — deliberately deferred: it must be
  grounded in actual pilot results, which require Task 14.
