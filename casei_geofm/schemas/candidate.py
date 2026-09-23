"""Candidate schema — one row per Campaign x Product x Target x Task x Satellite.

Ratings are qualitative enums by construction: no numeric score field exists
anywhere in this schema (pilot guardrail, 01-spec.md).
"""

import hashlib
from enum import StrEnum

from pydantic import BaseModel, Field

UNKNOWN = "UNKNOWN"


class Provenance(StrEnum):
    DIRECT_LABEL = "DIRECT_LABEL"
    DERIVED_LABEL = "DERIVED_LABEL"
    WEAK_OR_PROXY_LABEL = "WEAK_OR_PROXY_LABEL"
    MULTIMODAL_PAIR = "MULTIMODAL_PAIR"
    NO_OBVIOUS_LABEL = "NO_OBVIOUS_LABEL"


class Compat(StrEnum):
    NATIVE = "NATIVE"
    TRANSFORMABLE = "TRANSFORMABLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class Rating(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class CaseiRef(BaseModel):
    campaign: str = UNKNOWN
    campaign_id: str = UNKNOWN
    product: str = UNKNOWN
    product_id: str = UNKNOWN
    doi: str = UNKNOWN
    platform: str = UNKNOWN
    instrument: str = UNKNOWN


class Label(BaseModel):
    target_variable: str = UNKNOWN
    label_description: str = UNKNOWN
    label_type: str = UNKNOWN
    label_provenance: Provenance = Provenance.NO_OBVIOUS_LABEL
    geometry: str = UNKNOWN  # WKT or UNKNOWN
    spatial_resolution: str = UNKNOWN
    temporal_resolution: str = UNKNOWN


class UseCase(BaseModel):
    phenomenon: str = UNKNOWN
    proposed_task: str = UNKNOWN
    task_description: str = UNKNOWN
    potential_science_question: str = UNKNOWN


class ModelRef(BaseModel):
    model_name: str = "Prithvi-EO-2.0"
    model_version: str = "2.0"


class MissionOverlap(BaseModel):
    overlap: str = UNKNOWN  # "YES" / "NO" / UNKNOWN
    scene_count: int | None = None
    min_temporal_offset_days: float | None = None
    cloud_cover_min: float | None = None
    sequence_available: str = UNKNOWN


class Satellite(BaseModel):
    HLS: MissionOverlap = Field(default_factory=MissionOverlap)
    Sentinel2: MissionOverlap = Field(default_factory=MissionOverlap)
    Landsat: MissionOverlap = Field(default_factory=MissionOverlap)
    aoi_source: str = UNKNOWN  # deployment / campaign_union / UNKNOWN
    missing_prerequisite: str = ""


class Compatibility(BaseModel):
    science_fit: Rating = Rating.UNKNOWN
    spatial_fit: Rating = Rating.UNKNOWN
    temporal_fit: Rating = Rating.UNKNOWN
    spectral_fit: Rating = Rating.UNKNOWN
    geometric_fit: Rating = Rating.UNKNOWN
    label_fit: Rating = Rating.UNKNOWN
    overall_compatibility: Rating = Rating.UNKNOWN
    native_or_transformable: Compat = Compat.UNKNOWN


class Transformation(BaseModel):
    required_steps: list[str] = []
    estimated_complexity: Rating = Rating.UNKNOWN  # cost, recorded separately from…
    scientific_validity: Rating = Rating.UNKNOWN   # …validity (01-spec.md guardrail)


class Ranking(BaseModel):
    label_value: Rating = Rating.UNKNOWN
    prithvi_readiness: Rating = Rating.UNKNOWN
    novelty: Rating = Rating.UNKNOWN
    overall_priority: Rating = Rating.UNKNOWN
    label_value_reasoning: str = UNKNOWN
    prithvi_readiness_reasoning: str = UNKNOWN


class Evidence(BaseModel):
    evidence_level: int = 1  # 1 metadata inference / 2 archive confirmed / 3 data inspected
    metadata_evidence: str = UNKNOWN
    reasoning: str = UNKNOWN
    assumptions: str = UNKNOWN
    uncertainties: str = UNKNOWN
    urls: list[str] = []
    promotion_log: list[str] = []


class Candidate(BaseModel):
    candidate_id: str = ""
    casei: CaseiRef = Field(default_factory=CaseiRef)
    label: Label = Field(default_factory=Label)
    use_case: UseCase = Field(default_factory=UseCase)
    model: ModelRef = Field(default_factory=ModelRef)
    satellite: Satellite = Field(default_factory=Satellite)
    compatibility: Compatibility = Field(default_factory=Compatibility)
    transformation: Transformation = Field(default_factory=Transformation)
    ranking: Ranking = Field(default_factory=Ranking)
    evidence: Evidence = Field(default_factory=Evidence)
    retained_for_future_models: bool = False

    def model_post_init(self, __context) -> None:
        if not self.candidate_id:
            self.candidate_id = make_candidate_id(
                self.casei.campaign_id,
                self.casei.product_id,
                self.label.target_variable,
                self.use_case.proposed_task,
                self.satellite.aoi_source and primary_satellite(self.satellite) or UNKNOWN,
            )


def primary_satellite(sat: Satellite) -> str:
    for name, mission in [("HLS", sat.HLS), ("Sentinel-2", sat.Sentinel2), ("Landsat", sat.Landsat)]:
        if mission.overlap == "YES":
            return name
    return UNKNOWN


def make_candidate_id(campaign_id: str, product_id: str, target_variable: str,
                      proposed_task: str, satellite: str) -> str:
    key = "|".join([campaign_id, product_id, target_variable, proposed_task, satellite])
    return hashlib.sha256(key.encode()).hexdigest()[:16]
