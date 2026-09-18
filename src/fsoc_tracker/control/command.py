"""Control command and telemetry models.

Strongly typed output from the controller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fsoc_tracker.control.config import ControlMode


@dataclass
class ControlCommand:
    """Pan/tilt command produced by the controller.

    Rates are preferred over direct angle teleportation.
    This works naturally with the SIH speed constraints.
    """

    pan_rate_deg_s: float = 0.0
    tilt_rate_deg_s: float = 0.0
    target_pan_deg: float | None = None
    target_tilt_deg: float | None = None

    timestamp_s: float = 0.0
    control_mode: ControlMode = ControlMode.DISABLED

    tracking_valid: bool = False
    pan_saturated: bool = False
    tilt_saturated: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ControlTelemetry:
    """Structured telemetry record for one controller update.

    Provides full visibility into controller internals for diagnostics,
    HUD, plotting, and performance reports.
    """

    timestamp_s: float = 0.0
    dt: float = 0.0

    control_mode: ControlMode = ControlMode.DISABLED

    target_x: float = 0.0
    target_y: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0

    pixel_error_x: float = 0.0
    pixel_error_y: float = 0.0

    angular_error_pan_deg: float = 0.0
    angular_error_tilt_deg: float = 0.0

    pan_command: float = 0.0
    tilt_command: float = 0.0

    lead_dx_px: float = 0.0
    lead_dy_px: float = 0.0

    pan_saturated: bool = False
    tilt_saturated: bool = False

    pan_p_term: float = 0.0
    pan_i_term: float = 0.0
    pan_d_term: float = 0.0
    pan_raw_derivative: float = 0.0
    pan_filtered_derivative: float = 0.0
    pan_output_before_sat: float = 0.0

    tilt_p_term: float = 0.0
    tilt_i_term: float = 0.0
    tilt_d_term: float = 0.0
    tilt_raw_derivative: float = 0.0
    tilt_filtered_derivative: float = 0.0
    tilt_output_before_sat: float = 0.0

    pan_in_deadband: bool = False
    tilt_in_deadband: bool = False

    tracking_quality: float = 0.0
    lock_status: bool = False
    prediction_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_s": self.timestamp_s,
            "dt": self.dt,
            "control_mode": self.control_mode.value,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "pixel_error_x": self.pixel_error_x,
            "pixel_error_y": self.pixel_error_y,
            "angular_error_pan_deg": self.angular_error_pan_deg,
            "angular_error_tilt_deg": self.angular_error_tilt_deg,
            "pan_command": self.pan_command,
            "tilt_command": self.tilt_command,
            "pan_saturated": self.pan_saturated,
            "tilt_saturated": self.tilt_saturated,
            "pan_p_term": self.pan_p_term,
            "pan_i_term": self.pan_i_term,
            "pan_d_term": self.pan_d_term,
            "tilt_p_term": self.tilt_p_term,
            "tilt_i_term": self.tilt_i_term,
            "tilt_d_term": self.tilt_d_term,
            "tracking_quality": self.tracking_quality,
            "lock_status": self.lock_status,
            "prediction_only": self.prediction_only,
        }
