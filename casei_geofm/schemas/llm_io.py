"""Per-stage LLM I/O schemas and the invented-metadata guardrail."""

import re

from pydantic import BaseModel

from casei_geofm.schemas.candidate import Provenance, Rating

UNKNOWN = "UNKNOWN"


class InventedMetadataError(ValueError):
    """LLM supplied a value for a field the input marked UNKNOWN."""


def _traceable(value: str, input_text: str) -> bool:
    """A value is traceable when it appears verbatim in the input, or when
    every number in it does (e.g. copied from nested instrument metadata)."""
    if value in input_text:
        return True
    numbers = re.findall(r"\d+(?:\.\d+)?", value)
    return bool(numbers) and all(n in input_text for n in numbers)


def reject_unknown_overrides(input_record: dict, response: dict,
                             protected_fields: list[str],
                             input_text: str = "") -> None:
    """Raise if the response fills in a protected metadata field the input
    marked UNKNOWN — unless the value is traceable to somewhere else in the
    input (pass the full serialized payload as `input_text`). Protected fields
    are factual metadata (resolutions, dates, formats, geometry) the LLM must
    never invent — as opposed to the semantic judgments (ratings, tasks,
    reasoning) it is asked to produce."""
    for field in protected_fields:
        if input_record.get(field, UNKNOWN) == UNKNOWN:
            value = response.get(field)
            if value in (None, "", UNKNOWN):
                continue
            if input_text and _traceable(str(value), input_text):
                continue
            raise InventedMetadataError(
                f"LLM invented '{field}'={value!r} but input marked it UNKNOWN"
            )


# ---- Stage 1: label opportunity detection ----

class LabelOpportunity(BaseModel):
    target_variable: str
    label_type: str
    label_provenance: Provenance
    label_description: str = UNKNOWN
    evidence_quotes: list[str] = []
    spatial_resolution: str = UNKNOWN
    temporal_resolution: str = UNKNOWN


class LabelDetectorResponse(BaseModel):
    opportunities: list[LabelOpportunity]
    reasoning: str


# ---- Stage 2: task mapping ----

class TaskProposal(BaseModel):
    proposed_task: str
    task_description: str
    phenomenon: str
    potential_science_question: str = UNKNOWN


class TaskMapperResponse(BaseModel):
    tasks: list[TaskProposal]
    reasoning: str


# ---- Stage 3: science fit ----

class ScienceFitResponse(BaseModel):
    science_fit: Rating
    reasoning: str


# ---- Stage 5: transformation proposal ----

class TransformResponse(BaseModel):
    required_steps: list[str]
    estimated_complexity: Rating
    scientific_validity: Rating
    reasoning: str


# ---- Stage 7: ranking ----

class RankingResponse(BaseModel):
    label_value: Rating
    label_value_reasoning: str
    prithvi_readiness: Rating
    prithvi_readiness_reasoning: str
    novelty: Rating
    overall_priority: Rating
