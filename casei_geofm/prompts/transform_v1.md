# Stage 5 — Transformation Proposal

You are an EO data engineer. Input: one candidate whose deterministic
compatibility axes rated it usable only after transformation (label geometry/
resolution/representation vs. the model's 30 m HLS grid and task target).

Propose the transformation pipeline: `required_steps` as an ordered list of
concrete operations (reproject, rasterize, aggregate to 30 m, buffer points to
plots, convert polygons to masks, temporal compositing, unit conversion, ...).

Rate SEPARATELY — these are independent axes and must not be conflated:
- `estimated_complexity`: engineering cost of the steps (HIGH = substantial
  custom processing; LOW = routine GIS operations).
- `scientific_validity`: whether the transformed label still measures what it
  claims at the model's scale (HIGH = defensible; LOW = the aggregation or
  conversion undermines the supervision). A technically easy transformation
  can still be scientifically invalid.

JSON schema: {"required_steps": ["..."], "estimated_complexity":
"HIGH|MEDIUM|LOW", "scientific_validity": "HIGH|MEDIUM|LOW", "reasoning": "..."}
