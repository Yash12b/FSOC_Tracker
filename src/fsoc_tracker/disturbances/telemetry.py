"""Disturbance telemetry and performance tracking.

Structured metadata for each disturbed frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DisturbanceTelemetry:
    """Structured telemetry record for one disturbed frame."""

    timestamp_s: float = 0.0
    frame_index: int = 0

    active_disturbances: list[str] = field(default_factory=list)

    # Noise
    noise_gaussian_sigma: float = 0.0
    noise_salt_pepper_density: float = 0.0
    noise_poisson_enabled: bool = False

    # Atmosphere
    atmosphere_mode: str = "clear"
    atmosphere_haze_strength: float = 0.0
    atmosphere_fog_strength: float = 0.0
    atmosphere_rain_density: float = 0.0
    atmosphere_low_light_factor: float = 1.0

    # Motion
    jitter_x_px: float = 0.0
    jitter_y_px: float = 0.0
    platform_offset_x_px: float = 0.0
    platform_offset_y_px: float = 0.0

    # Turbulence
    turbulence_strength: float = 0.0

    # Effective camera offset (jitter + platform combined)
    effective_camera_offset_x_px: float = 0.0
    effective_camera_offset_y_px: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_s": self.timestamp_s,
            "frame_index": self.frame_index,
            "active_disturbances": self.active_disturbances,
            "noise": {
                "gaussian_sigma": self.noise_gaussian_sigma,
                "salt_pepper_density": self.noise_salt_pepper_density,
                "poisson_enabled": self.noise_poisson_enabled,
            },
            "atmosphere": {
                "mode": self.atmosphere_mode,
                "haze_strength": self.atmosphere_haze_strength,
                "fog_strength": self.atmosphere_fog_strength,
                "rain_density": self.atmosphere_rain_density,
                "low_light_factor": self.atmosphere_low_light_factor,
            },
            "motion": {
                "jitter_x_px": self.jitter_x_px,
                "jitter_y_px": self.jitter_y_px,
                "platform_offset_x_px": self.platform_offset_x_px,
                "platform_offset_y_px": self.platform_offset_y_px,
            },
            "turbulence_strength": self.turbulence_strength,
            "effective_camera_offset_x_px": self.effective_camera_offset_x_px,
            "effective_camera_offset_y_px": self.effective_camera_offset_y_px,
        }


@dataclass
class DisturbancePerformance:
    """Performance metrics for disturbance pipeline processing."""

    total_ms: float = 0.0
    geometry_ms: float = 0.0
    atmosphere_ms: float = 0.0
    noise_ms: float = 0.0
    turbulence_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_ms": self.total_ms,
            "geometry_ms": self.geometry_ms,
            "atmosphere_ms": self.atmosphere_ms,
            "noise_ms": self.noise_ms,
            "turbulence_ms": self.turbulence_ms,
        }
