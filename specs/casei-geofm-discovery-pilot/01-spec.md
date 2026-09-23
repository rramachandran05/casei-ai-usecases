Status: Draft

# Spec: CASEI-to-Prithvi-EO Labeled Data Discovery Pilot

## What this feature should do

Build a pipeline (`casei_geofm/`) that mines NASA's CASEI airborne/field campaign catalog for supervision opportunities usable to adapt Earth-observation foundation models, using **Prithvi-EO-2.0 as the reference model**. The pilot tests two hypotheses:

- **H1 (data opportunity):** CASEI contains scientifically valuable, underused supervision for GeoFM adaptation — direct labels, continuous measurements, field observations, airborne products, and derivable labels.
- **H2 (automated discovery):** Given a machine-readable GeoFM model card, an automated system can search the full CASEI catalog and identify, characterize, filter, and prioritize candidate labeled datasets.

The end-to-end concept: **model specification → CASEI search → supervision opportunities → use-case inference → satellite coincidence → compatibility assessment → ranked candidates.**

### Deliverables

1. **A searchable candidate dataset inventory** — exportable to CSV, Parquet, and JSON, with the full field schema in §Output below; eventually browsable through a lightweight searchable UI.
2. **A prototype specification for a GeoFM–CASEI Dataset Matching Agent** (Mode B, targeted search). *Note: when this agent spec is authored, it must go through the `akd_care_design_process` skill per workspace policy.*

### Inputs

1. **Model card** (`config/model_card.yaml`) — a machine-readable compatibility specification, not descriptive documentation. Grounded in [resources/prithvi-eo-2.0.yaml](../../resources/prithvi-eo-2.0.yaml), which resolves the TBDs in the project-context template:
   - Input: HLS (Sentinel-2 + Landsat), six bands (Blue, Green, Red, NIR, SWIR1, SWIR2), 30 m, multi-temporal (4 timestamps, 1–6 months apart), 224×224 input tiles; optional lat/lon and date metadata encodings (model tolerates missing metadata).
   - Pretraining: global HLS 2014–2023, masked autoencoding; optical/multispectral only (no SAR); cloud-sensitive (<20% cloud filter).
   - Adaptation surface: semantic segmentation, classification, regression, multi-temporal analysis, change detection, object detection (via adapter necks); full fine-tuning, frozen backbone, PEFT — all available through TerraTorch, single-GPU feasible.
2. **Optional example use cases** (flood mapping, burn scars, land cover, biomass, vegetation classification) — supplied to aid semantic reasoning but **must not constrain discovery**. The two adaptation case studies in `resources/` (landslide segmentation, fallow-field detection) serve as calibration references for what a viable adaptation looks like, including label-noise and band-adapter considerations.

### Design principles (binding)

- **Discover first → infer use cases → evaluate compatibility → rank.** No predefined use-case whitelist; novelty is a desired outcome.
- **Unit of discovery** is *not* a campaign. A candidate is the tuple: **Campaign × Data Product × Measurement/Target × Proposed Learning Task × Satellite Input** (e.g. `ABoVE × canopy-height product × canopy height × pixel regression × HLS`). One product may yield many candidates.
- **Hybrid deterministic + LLM architecture.** Deterministic code handles API retrieval, relationship traversal, coordinates, dates, satellite intersection, band/resolution/format comparison, thresholds, filtering, persistence. LLM reasoning handles measurement semantics, label identification, task proposal, EO-observability judgment, transformation suggestions, and ranking rationale.
- **The LLM never invents missing metadata.** Missing values remain `UNKNOWN`.
- **Progressive evidence model.** Every claim is tagged Level 1 (CASEI metadata inference), Level 2 (DOI/CMR/product metadata confirmed), or Level 3 (representative files opened and verified). A Level-1 inference is never described as a confirmed training dataset. This is the system's most important guardrail.
- **Qualitative ratings only** (HIGH/MEDIUM/LOW) with explicit reasoning — no false-precision numeric scores in the pilot.

### Pipeline stages

1. **Harvest** — retrieve the *entire* published CASEI catalog via its API (not keyword search): campaigns (~194), platforms (~153), instruments (~605), data products (~2,607), plus deployments, geography, dates, science concepts, measurement characteristics, formats, DOIs, and the campaign↔platform↔instrument↔product relationships. Persist to a local normalized cache so repeated runs don't re-query the API or LLM.
2. **Label Opportunity Detector** — for every data product, ask whether it could provide a target, reference observation, weak label, or paired measurement. Classify against the ~21-type label taxonomy (raster categorical/continuous, polygon, point, plot, transect, object, event, airborne imagery/retrieval, hyperspectral, LiDAR, radar, temporal, before/after, spectral, instrument retrieval, annotation, proxy, derived, multimodal pairing) and assign provenance: `DIRECT_LABEL / DERIVED_LABEL / WEAK_OR_PROXY_LABEL / MULTIMODAL_PAIR / NO_OBVIOUS_LABEL`.
3. **Task / Use-Case Mapper** — infer *all* plausible learning tasks per candidate from the canonical task vocabulary (19 task families, from semantic segmentation through cross-modal prediction and weak supervision). Tasks need not exist in published GeoFM benchmarks.
4. **Science-fit assessment** — rate whether the measured target is plausibly observable/inferable from Prithvi-EO inputs: HIGH / MEDIUM / LOW. **LOW is retained, not discarded** (relevant to future SAR/hyperspectral/multimodal FMs and VLMs).
5. **Satellite Coincidence Tool** — for each candidate's geometry × time, search HLS → Sentinel-2 → Landsat (in that order) and record satellite, acquisition times, temporal offset, spatial intersection, cloud cover, usable scene count, and temporal-sequence availability. Campaigns predating HLS are not rejected if Landsat coverage exists.
6. **Compatibility Engine** — assess independently along five axes: spatial, temporal (**phenomenon-dependent** windows: flood hours–days; vegetation structure days–months; land cover months), spectral/input, geometric, and label compatibility. Classify each candidate `NATIVE / TRANSFORMABLE / INCOMPATIBLE`, recording **transformation cost and scientific validity separately** (an easy transformation can still be invalid).
7. **Ranking Agent** — assign HIGH/MEDIUM/LOW with explicit reasoning across ten factors (science fit, label strength, spatial/temporal match, satellite coverage, transformation, scale, diversity, accessibility, novelty). **Maintain two separate rankings**: (A) label-value (scientific worth of the supervision) and (B) Prithvi-readiness (ease of use with this specific model). Never collapse them — the divergence is itself a study result.
8. **Human review** — stratified sample across HIGH/MEDIUM/LOW, label provenance types, and task families; use findings to improve prompts/rules before building the operational agent.

### Output

The candidate table with the field groups defined in project-context §14: `candidate_id`, CASEI provenance (campaign, product, DOI, platform, instrument), LABEL (variable, type, provenance, geometry, resolutions), USE_CASE (phenomenon, task, science question), MODEL, SATELLITE (per-mission overlap, scene counts, offsets), COMPATIBILITY (per-axis fits, native/transformable), TRANSFORMATION (steps, complexity), RANKING (label value, Prithvi readiness, novelty, priority), and EVIDENCE (metadata evidence, reasoning, assumptions, uncertainties, URLs, evidence level).

### Success measures (pilot evaluation)

Catalog coverage (% of CASEI products examined), opportunity yield, task diversity, label diversity, native-vs-transformable split, satellite-coincidence rate, **novel-discovery count** (credible use cases not among the supplied examples), and human agreement with the agent's label interpretation and compatibility reasoning. The research question is not "can CASEI feed Prithvi" but: *can metadata describing NASA's historical field and airborne observations be systematically transformed into an inventory of supervision opportunities for EO foundation models?*

### Proposed repo layout

Per project-context §18: `casei_geofm/` with `config/` (model card, task taxonomy), `casei/` (client, harvest, normalize), `discovery/` (label detector, task mapper, science mapper), `satellite/` (hls, sentinel2, landsat), `compatibility/` (spatial, temporal, spectral, label, transform), `ranking/`, `schemas/` (candidate, model), `outputs/`, `run_pipeline.py`. Python with tests built in (workspace default; no repo signal contradicts it). Modularity is deliberate — satellite matching, CASEI retrieval, semantic reasoning, and compatibility logic will evolve independently.

## Why

CASEI relationally organizes decades of NASA airborne/field campaign metadata that is currently underused for GeoFM adaptation. Published Prithvi adaptations (landslide mapping, fallow detection — see `resources/`) show GeoFMs deliver their biggest advantage precisely in the low-label regime, so surfacing new supervision sources is high-leverage. A validated CASEI→supervision-inventory framework generalizes beyond Prithvi to future SAR, hyperspectral, weather, multimodal, and VLM foundation models.

## Out of scope

- **Fine-tuning Prithvi** on any discovered dataset (explicitly a follow-on experiment; outputs should merely make it straightforward).
- Building the operational **Mode B** targeted-search agent (the pilot delivers only its prototype specification).
- A production-grade UI — only a lightweight searchable presentation of the candidate table.
- Bulk downloading of the underlying science data (Level 3 evidence opens *representative* files only).
- Extending discovery to non-CASEI catalogs (CMR-wide, non-NASA archives).
- Numeric ranking scores (qualitative HIGH/MEDIUM/LOW with rationale only).

## Open questions / TBD

- **CASEI API specifics:** exact base URL, endpoint list, pagination, auth, and rate limits — must be confirmed against the live API before the harvester design is final (documented as Django/PostgreSQL with table-mapped endpoints).
- **Geometry availability:** how many CASEI records carry usable geometry/bounding regions, and the fallback when only a named region exists (gazetteer lookup? deployment-level bounds? mark `UNKNOWN`?).
- **Satellite search backend:** which service performs coincidence queries — NASA CMR, Earthdata STAC, or per-mission APIs — and whether cloud-cover metadata is uniformly available (TBD at Plan stage).
- **LLM provider/model and prompting harness** for the semantic stages, plus per-stage caching/budget strategy for ~2,607 products × multiple stages.
- **Level 2/3 evidence scope in the pilot:** run Levels 2–3 for all candidates or only the HIGH tier? (Suggested default: Level 1 for all; Level 2 for HIGH+MEDIUM; Level 3 for a HIGH-tier sample.)
- **Human-review sample size** and who reviews (EO scientist availability).
- **Model card version pin:** Prithvi-EO-2.0 300M vs 600M (compatibility logic is size-agnostic; suggest recording family-level card with variants listed).
- Repo is not yet git-initialized — should be, before implementation, with the workspace `.gitignore` conventions.
