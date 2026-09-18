"""Sensor subpackage for virtual optical image formation.

Provides VirtualSensorRenderer, SensorConfig, ground truth, and PSF.
"""

from fsoc_tracker.simulation.sensor.beacon import deposit_beacon
from fsoc_tracker.simulation.sensor.config import (
    BeaconShape,
    ColorMode,
    SensorConfig,
    SizeMode,
)
from fsoc_tracker.simulation.sensor.models import (
    GroundTruth,
    RenderedFrame,
    TargetVisibility,
)
from fsoc_tracker.simulation.sensor.psf import apply_psf, gaussian_psf_2d
from fsoc_tracker.simulation.sensor.renderer import VirtualSensorRenderer, render_debug_view

__all__ = [
    "BeaconShape",
    "ColorMode",
    "GroundTruth",
    "RenderedFrame",
    "SensorConfig",
    "SizeMode",
    "TargetVisibility",
    "VirtualSensorRenderer",
    "apply_psf",
    "deposit_beacon",
    "gaussian_psf_2d",
    "render_debug_view",
]
