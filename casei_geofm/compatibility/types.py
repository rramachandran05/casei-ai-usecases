"""Shared label-type groupings used by the compatibility axes."""

UNKNOWN = "UNKNOWN"

RASTER_TYPES = {"raster_categorical", "raster_continuous", "airborne_imagery",
                "airborne_retrieval", "lidar", "radar", "hyperspectral_measurement"}
VECTOR_TYPES = {"polygon", "object_location", "event", "before_after_observation"}
SPARSE_TYPES = {"point_observation", "field_plot", "transect", "spectral_measurements",
                "human_campaign_annotation", "instrument_retrieval", "proxy_label",
                "derived_label", "temporal_observations", "multimodal_pairing"}
