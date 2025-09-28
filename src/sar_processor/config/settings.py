"""Configuration settings for SAR processor."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import os


@dataclass
class ProcessingConfig:
    """Configuration for SAR processing operations."""
    utm_projection: str = "EPSG:32643"
    dem_name: str = "SRTM 3Sec"
    pixel_spacing: float = 10.0
    subswath: str = "IW2"
    polarizations: List[str] = None
    slope_calculation_method: str = "degrees"
    output_format: str = "GeoTIFF"

    def __post_init__(self):
        if self.polarizations is None:
            self.polarizations = ["VV", "VH"]


@dataclass
class ProjectPaths:
    """Project directory paths configuration."""
    base_dir: Path = Path(__file__).parent.parent.parent.parent
    inputs_dir: Path = None
    outputs_dir: Path = None
    logs_dir: Path = None

    def __post_init__(self):
        if self.inputs_dir is None:
            self.inputs_dir = self.base_dir / "data" / "inputs"
        if self.outputs_dir is None:
            self.outputs_dir = self.base_dir / "data" / "outputs"
        if self.logs_dir is None:
            self.logs_dir = self.base_dir / "logs"

        # Create directories if they don't exist
        for path in [self.inputs_dir, self.outputs_dir, self.logs_dir]:
            path.mkdir(parents=True, exist_ok=True)
