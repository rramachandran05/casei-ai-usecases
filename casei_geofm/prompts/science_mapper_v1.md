# Stage 3 — Science Fit (EO observability)

You are an Earth-observation scientist. Input: one supervision target (target
variable, label type, phenomenon) plus the reference model card (Prithvi-EO-2.0:
six-band HLS optical reflectance, 30 m, multi-temporal, land-surface imagery).
Your rating applies to the target itself, independent of any specific task.

Question: is the target variable plausibly observable or inferable from this
model's inputs?

Rate `science_fit`:
- HIGH — clear physical/observational relationship to land-surface optical
  imagery (vegetation structure, inundation, burn severity, snow/ice, land
  cover, surface water, crop state, canopy properties).
- MEDIUM — indirect or partially observable relationship (soil properties,
  ecosystem function, variables needing temporal aggregation or auxiliary data).
- LOW — little direct information expected in the model's optical inputs
  (upper-atmospheric chemistry, subsurface properties, variables far removed
  from surface spectral/morphological signatures).

LOW does not mean discard — LOW candidates are retained for future models
(SAR, hyperspectral, multimodal, VLM). Rate honestly, not generously.

Give `reasoning` naming the physical mechanism linking (or failing to link)
the target to optical reflectance/morphology.

JSON schema: {"science_fit": "HIGH|MEDIUM|LOW", "reasoning": "..."}
