"""Label compatibility: can the supervision convert into the target
representation the proposed task requires?"""

from casei_geofm.compatibility.types import RASTER_TYPES, SPARSE_TYPES, UNKNOWN, VECTOR_TYPES
from casei_geofm.schemas.candidate import Candidate, Rating

TASK_COMPATIBLE_TYPES = {
    "semantic_segmentation": RASTER_TYPES | {"polygon", "event"},
    "instance_segmentation": {"airborne_imagery", "object_location", "polygon"},
    "object_detection": {"object_location", "airborne_imagery", "polygon"},
    "pixel_regression": RASTER_TYPES | {"instrument_retrieval", "derived_label"},
    "patch_regression": RASTER_TYPES | SPARSE_TYPES,
    "patch_classification": RASTER_TYPES | SPARSE_TYPES | VECTOR_TYPES,
    "multi_label_classification": RASTER_TYPES | SPARSE_TYPES | VECTOR_TYPES,
    "ordinal_classification": RASTER_TYPES | SPARSE_TYPES | VECTOR_TYPES,
    "change_detection": {"before_after_observation", "event", "temporal_observations"} | RASTER_TYPES,
    "temporal_classification": {"temporal_observations", "event"} | RASTER_TYPES | SPARSE_TYPES,
    "temporal_regression": {"temporal_observations"} | RASTER_TYPES | SPARSE_TYPES,
    "anomaly_event_detection": {"event", "before_after_observation", "temporal_observations"},
    "super_resolution": {"airborne_imagery", "airborne_retrieval", "lidar"},
    "downscaling": RASTER_TYPES,
    "image_to_image_prediction": RASTER_TYPES,
    "spectral_prediction": {"hyperspectral_measurement", "spectral_measurements"},
    "cross_modal_prediction": {"lidar", "radar", "hyperspectral_measurement", "airborne_retrieval"},
    "contrastive_multimodal_learning": {"multimodal_pairing"} | RASTER_TYPES | SPARSE_TYPES,
    "weakly_supervised_learning": SPARSE_TYPES | {"proxy_label"},
}


def label_fit(candidate: Candidate) -> Rating:
    task = candidate.use_case.proposed_task
    ltype = candidate.label.label_type
    compatible = TASK_COMPATIBLE_TYPES.get(task)
    if compatible is None or ltype == UNKNOWN:
        return Rating.UNKNOWN
    if ltype in compatible:
        return Rating.HIGH
    # sparse labels can weakly supervise dense tasks after transformation
    if ltype in SPARSE_TYPES and task in ("semantic_segmentation", "pixel_regression"):
        return Rating.MEDIUM
    return Rating.LOW
