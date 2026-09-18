"""Controller configuration.

Strongly typed Pydantic model for all control parameters.
Defaults align with SIH26169 reference conditions.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ControlMode(str, Enum):
    DISABLED = "disabled"
    TRACK = "track"
    PREDICT = "predict"
    HOLD = "hold"
    SAFE_STOP = "safe_stop"


class ControllerConfig(BaseModel):
    """Configuration for the coarse pointing controller.

    Reference from SIH26169 PS:
        - max pan/tilt speed: 5 deg/s
        - control update >= 20 Hz
        - tracking error <= 10 px
    """

    enabled: bool = True
    mode: ControlMode = ControlMode.TRACK

    pan_kp: float = Field(default=0.5, ge=0,
        description="Pan proportional gain (deg/s per deg of angular error)")
    pan_ki: float = Field(default=0.02, ge=0,
        description="Pan integral gain")
    pan_kd: float = Field(default=0.08, ge=0,
        description="Pan derivative gain")

    tilt_kp: float = Field(default=0.5, ge=0,
        description="Tilt proportional gain (deg/s per deg of angular error)")
    tilt_ki: float = Field(default=0.02, ge=0,
        description="Tilt integral gain")
    tilt_kd: float = Field(default=0.08, ge=0,
        description="Tilt derivative gain")

    max_pan_rate_deg_s: float = Field(default=5.0, gt=0,
        description="Maximum pan rate command (deg/s)")
    max_tilt_rate_deg_s: float = Field(default=5.0, gt=0,
        description="Maximum tilt rate command (deg/s)")

    deadband_deg: float = Field(default=0.0, ge=0,
        description="Angular deadband (deg) — commands near zero within this range")

    integral_limit_pan: float = Field(default=10.0, gt=0,
        description="Maximum absolute integral accumulator for pan (deg)")
    integral_limit_tilt: float = Field(default=10.0, gt=0,
        description="Maximum absolute integral accumulator for tilt (deg)")

    derivative_filter_alpha: float = Field(default=0.5, ge=0, le=1,
        description="Low-pass filter alpha for derivative term (0=full filter, 1=no filter)")

    prediction_control_enabled: bool = True
    max_prediction_control_duration_s: float = Field(default=0.5, gt=0,
        description="Maximum duration to use predicted position for control")

    lead_compensation_enabled: bool = Field(default=False,
        description="Aim ahead of the estimate along velocity (lead angle). "
        "Off by default; enable only where measured to help.")
    lead_time_s: float = Field(default=0.1, ge=0.0, le=0.5,
        description="Lookahead horizon for lead compensation.")
    lead_max_px: float = Field(default=25.0, gt=0,
        description="Cap on lead displacement in pixels.")

    minimum_tracking_quality: float = Field(default=0.2, ge=0, le=1,
        description="Minimum quality to engage TRACK mode")

    nan_protection: bool = True
    search_enabled: bool = True
    search_pan_rate_deg_s: float = Field(default=5.0, ge=0)
    search_tilt_rate_deg_s: float = Field(default=2.5, ge=0)
    search_period_s: float = Field(default=40.0, gt=0)
