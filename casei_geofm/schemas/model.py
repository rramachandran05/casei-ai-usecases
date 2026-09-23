"""Model card schema — the machine-readable compatibility specification."""

from pathlib import Path

import yaml
from pydantic import BaseModel

CONFIG_DIR = Path(__file__).parent.parent / "config"


class TemporalContext(BaseModel):
    timestamps: int
    spacing: str
    single_timestep_supported: bool = True


class ModelInput(BaseModel):
    sensors: list[str]
    supported_satellites: list[str]
    bands: list[str]
    band_note: str = "UNKNOWN"
    spatial_resolution_m: int
    temporal_context: TemporalContext
    input_size_px: int
    optional_metadata: list[str] = []


class ModelCard(BaseModel):
    name: str
    version: str
    variants: list[str] = []
    input: ModelInput
    pretraining: dict
    adaptation: dict
    constraints: dict

    @classmethod
    def load(cls, path: Path | None = None) -> "ModelCard":
        raw = yaml.safe_load((path or CONFIG_DIR / "model_card.yaml").read_text())
        return cls(**raw["model"], input=raw["input"], pretraining=raw["pretraining"],
                   adaptation=raw["adaptation"], constraints=raw["constraints"])
