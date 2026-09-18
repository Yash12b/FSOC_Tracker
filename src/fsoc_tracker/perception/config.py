"""Perception configuration.

Strongly typed Pydantic model for detection parameters.
Defaults align with SIH26169 beacon specifications.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ThresholdMode(str, Enum):
    GLOBAL = "global"
    ADAPTIVE = "adaptive"
    PERCENTILE = "percentile"


class CentroidMethod(str, Enum):
    GEOMETRIC = "geometric"
    INTENSITY_WEIGHTED = "intensity_weighted"


class PerceptionConfig(BaseModel):
    """Configuration for the perception/detection subsystem.

    Reference from SIH26169 PS:
        - beacon ~10x10 px default
        - range 5x5 to 20x20
        - one primary target
    """

    enabled: bool = True
    algorithm: str = "classical_bright_spot"

    threshold_mode: ThresholdMode = ThresholdMode.PERCENTILE
    threshold_value: float = Field(default=180.0, ge=0)
    percentile_value: float = Field(default=95.0, ge=0, le=100)
    adaptive_block_size: int = Field(default=11, ge=3)
    adaptive_constant: float = Field(default=2.0, ge=0)

    min_candidate_area: float = Field(default=5.0, gt=0)
    max_candidate_area: float = Field(default=2000.0, gt=0)
    min_width: float = Field(default=2.0, gt=0)
    max_width: float = Field(default=50.0, gt=0)
    min_height: float = Field(default=2.0, gt=0)
    max_height: float = Field(default=50.0, gt=0)

    expected_size_px: float = Field(default=10.0, gt=0)
    size_tolerance_px: float = Field(default=8.0, ge=0)

    min_confidence: float = Field(default=0.3, ge=0, le=1)

    blur_sigma: float = Field(default=0.0, ge=0)
    # Salt-and-pepper/Gaussian robustness (PS disturbances): the median
    # applies only when measured noise exceeds 1.0, so clean frames pass
    # through unchanged.
    denoise_enabled: bool = True

    use_weighted_centroid: bool = True
    centroid_method: CentroidMethod = CentroidMethod.INTENSITY_WEIGHTED

    morphology_enabled: bool = False
    morphology_kernel_size: int = Field(default=3, ge=1)

    w_intensity: float = Field(default=0.3, ge=0)
    w_size: float = Field(default=0.25, ge=0)
    w_shape: float = Field(default=0.25, ge=0)
    w_contrast: float = Field(default=0.2, ge=0)

    background_estimate_method: str = "percentile"
    background_percentile: float = Field(default=10.0, ge=0, le=100)

    normalize_contrast_enabled: bool = False
