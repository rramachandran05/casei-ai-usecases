Status: Draft

# Acceptance Criteria: CASEI-to-Prithvi-EO Labeled Data Discovery Pilot

## Criteria

### Inputs & configuration

- [ ] `config/model_card.yaml` exists, parses as valid YAML, and encodes Prithvi-EO-2.0 as a machine-readable compatibility spec: the six HLS bands, 30 m resolution, multi-temporal context (4 timestamps), supported satellites (HLS/Sentinel-2/Landsat), supported task families, and known limitations (optical-only, cloud sensitivity). No field required by the compatibility engine is left free-text-only.
- [ ] `config/task_taxonomy.yaml` exists and contains the 19-family canonical task vocabulary and the ~21-type label taxonomy with provenance classes (`DIRECT_LABEL / DERIVED_LABEL / WEAK_OR_PROXY_LABEL / MULTIMODAL_PAIR / NO_OBVIOUS_LABEL`).
- [ ] Example use cases are supplied via config only; a run with the examples list emptied completes and still produces candidates (verifies examples do not constrain discovery).

### Harvest & cache

- [ ] A single command harvests the full published CASEI catalog via the API (not keyword search) and persists a local normalized cache; a harvest summary reports counts per entity (campaigns, platforms, instruments, data products, deployments) that can be sanity-checked against the CASEI Explore figures (~194 / ~153 / ~605 / ~2,607).
- [ ] Normalized records preserve the campaign ↔ platform ↔ instrument ↔ product relationships plus geography, dates, science concepts, measurement characteristics, formats, and DOIs; a spot-checked sample of ≥10 records matches the corresponding CASEI pages.
- [ ] A second pipeline run against an existing cache issues zero CASEI API calls for already-harvested entities (cache hit verified in logs or a test with the network mocked/disabled).
- [ ] Fields absent in CASEI are stored as `UNKNOWN` (or typed null mapped to `UNKNOWN` at export), never as fabricated values — verified by a test feeding a metadata-sparse record through the full pipeline.

### Candidate generation (Stages 1–3)

- [ ] The unit of output is the tuple Campaign × Data Product × Target × Proposed Task × Satellite Input, with a stable unique `candidate_id`; at least one CASEI product demonstrably yields multiple candidate records.
- [ ] Every harvested data product passes through the Label Opportunity Detector — catalog coverage (% of products examined) is computed and reported, and products yielding no candidate are retained with `NO_OBVIOUS_LABEL`, not silently dropped.
- [ ] Every candidate carries a label-taxonomy type, a provenance class, and at least one proposed task from the canonical vocabulary; tasks outside the supplied examples appear in the output (novelty is possible in practice, not just in principle).
- [ ] Every candidate carries a science-fit rating (HIGH/MEDIUM/LOW) with a written rationale; LOW candidates are retained in the inventory, flagged but not filtered out.

### Satellite coincidence (Stage 4)

- [ ] For candidates with usable geometry and dates, the coincidence tool queries HLS → Sentinel-2 → Landsat in that order and records per-mission overlap, scene count, temporal offset, spatial intersection, and cloud cover where available.
- [ ] A pre-2013 campaign (predating HLS) with Landsat coverage is not rejected — verified with at least one real example in the output.
- [ ] Candidates lacking geometry or dates are marked `UNKNOWN` for coincidence and retained, with the missing prerequisite named in the evidence fields.

### Compatibility & ranking (Stages 5–7)

- [ ] Each candidate is assessed independently on all five axes (spatial, temporal, spectral/input, geometric, label) and classified `NATIVE / TRANSFORMABLE / INCOMPATIBLE`; no axis value is derivable only from the overall class.
- [ ] Temporal compatibility windows are phenomenon-dependent and config-driven (flood ≠ land cover), not a single fixed threshold — verified by test cases with identical offsets but different phenomena yielding different ratings.
- [ ] For TRANSFORMABLE candidates, required transformation steps, estimated complexity, and scientific validity are recorded as separate fields.
- [ ] Every candidate carries two independent rankings — label-value and Prithvi-readiness — each HIGH/MEDIUM/LOW with explicit written reasoning; at least the review sample shows the reasoning references the ranking factors (science fit, label strength, coverage, transformation, scale, diversity, accessibility, novelty). No numeric scores appear.
- [ ] The inventory contains at least one candidate where the two rankings diverge (e.g. high label-value, low Prithvi-readiness), demonstrating the rankings are genuinely independent.

### Evidence guardrails

- [ ] Every candidate carries an evidence level (1 = CASEI metadata inference, 2 = archive/product metadata confirmed, 3 = data inspected) and evidence fields (metadata evidence, reasoning, assumptions, uncertainties, URLs).
- [ ] No Level-1 candidate is described anywhere in the output as a confirmed or verified training dataset — generated rationale text for Level-1 records uses hedged framing ("appears", "potentially"); enforced by a lint/test over the output.
- [ ] Level 2 verification runs for at least all HIGH-priority candidates, and Level 3 inspection for a sample of them, with fields confirmed/corrected at each promotion recorded.

### Outputs & deliverables

- [ ] The candidate inventory exports to CSV, Parquet, and JSON with the §14 field groups (CASEI, LABEL, USE_CASE, MODEL, SATELLITE, COMPATIBILITY, TRANSFORMATION, RANKING, EVIDENCE); all three exports round-trip-load and agree on row counts.
- [ ] The inventory is searchable/filterable at minimum by campaign, phenomenon, task family, label provenance, compatibility class, evidence level, and both rankings (a lightweight UI or documented query interface — DataFrame/DuckDB acceptable for the pilot).
- [ ] A pilot metrics report is produced covering all eight §20 measures: catalog coverage, opportunity yield, task diversity, label diversity, native-vs-transformable split, satellite-coincidence rate, novel-discovery count, and human-agreement results.
- [ ] A stratified human-review packet exists (sampled across HIGH/MEDIUM/LOW, provenance classes, and task families), and review outcomes are captured in a form that feeds prompt/rule revisions.
- [ ] The Mode B "GeoFM–CASEI Dataset Matching Agent" prototype specification exists as a written deliverable (authored via the AKD CARE process), covering both operating modes and grounded in what the pilot learned.

### Engineering quality

- [ ] Deterministic logic (API retrieval, geometry/date math, satellite intersection, band/resolution comparison, thresholds, filtering, persistence) is implemented in code with unit tests; LLM calls are confined to the semantic stages (label detection, task mapping, science fit, transformation suggestions, ranking rationale).
- [ ] LLM-stage outputs are schema-validated before persistence; a response inventing a value for a field the input marked `UNKNOWN` is rejected or flagged, verified by test.
- [ ] The pipeline is resumable per stage: rerunning after an interruption does not redo completed LLM/API work (stage-level caching or checkpoints).
- [ ] The test suite runs with a single documented command and passes; the repo is git-initialized with the workspace `.gitignore` conventions before implementation is called done.

## Out of scope for verification

- Any fine-tuning result on Prithvi — no criterion requires training a model on discovered data.
- The *correctness* of individual LLM semantic judgments (that is what the human-review measure estimates); verification covers structure, guardrails, coverage, and reproducibility, not per-candidate ground truth.
- Operational deployment of the Mode B agent — only its written specification is verified.
- UI polish beyond searchable/filterable access to the inventory.
- Bulk download or archival of the underlying science datasets.
- Satellite-search completeness beyond HLS, Sentinel-2, and Landsat.
