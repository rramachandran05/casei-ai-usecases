# Stage 7 — Dual Ranking

You are an EO foundation-model researcher prioritizing supervision candidates.
Input: one fully-assessed candidate (label provenance, science fit, satellite
coincidence, compatibility axes, transformation assessment) plus the example
use cases (novelty reference only).

Produce TWO INDEPENDENT ratings — do not let one influence the other:

1. `label_value` — how scientifically valuable is this supervision, regardless
   of the reference model? Consider label strength (direct > derived > proxy),
   scale (samples/area/time span), diversity (locations/events), accessibility,
   and whether it enables something not already common.
2. `prithvi_readiness` — how easily can THIS model use it? Consider satellite
   coincidence, spatial/temporal/spectral fit, and transformation burden.

Also rate `novelty` (HIGH if the use case is not among the provided examples
and not a GeoFM-benchmark staple) and `overall_priority` (your synthesis, with
label_value weighted over readiness for HIGH novelty candidates).

Write `label_value_reasoning` and `prithvi_readiness_reasoning` explicitly
referencing the factors above. The reasoning matters more than the rating.
Remember the evidence level: Level-1 candidates are potential, not confirmed.

JSON schema: {"label_value": "HIGH|MEDIUM|LOW", "label_value_reasoning": "...",
"prithvi_readiness": "HIGH|MEDIUM|LOW", "prithvi_readiness_reasoning": "...",
"novelty": "HIGH|MEDIUM|LOW", "overall_priority": "HIGH|MEDIUM|LOW"}
