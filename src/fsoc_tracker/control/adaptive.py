"""Adaptive controller with gain scheduling, feed-forward, and anti-oscillation.

Extends the baseline PID controller with adaptive behavior based on
error magnitude, target velocity, uncertainty, and oscillation detection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from fsoc_tracker.control.pid import PIDController


class GainSchedule(str, Enum):
    LOW_ERROR = "low_error"
    MEDIUM_ERROR = "medium_error"
    HIGH_ERROR = "high_error"


@dataclass
class AdaptiveControllerConfig:
    """Configuration for adaptive controller."""

    enabled: bool = True

    low_error_threshold: float = 5.0
    medium_error_threshold: float = 20.0
    high_error_threshold: float = 50.0

    low_error_kp_scale: float = 0.7
    low_error_kd_scale: float = 0.5
    medium_error_kp_scale: float = 1.0
    medium_error_kd_scale: float = 1.0
    high_error_kp_scale: float = 1.5
    high_error_kd_scale: float = 1.5

    feed_forward_enabled: bool = True
    feed_forward_gain: float = 0.15

    anti_oscillation_enabled: bool = True
    oscillation_sign_changes: int = 4
    oscillation_window_frames: int = 10
    oscillation_reduction_factor: float = 0.6

    uncertainty_scale_enabled: bool = True
    max_uncertainty_reduction: float = 0.5

    min_kp_scale: float = 0.3
    max_kp_scale: float = 2.0
    min_kd_scale: float = 0.3
    max_kd_scale: float = 2.0


@dataclass
class AdaptiveTelemetry:
    """Diagnostics from the adaptive controller."""

    gain_schedule: GainSchedule = GainSchedule.MEDIUM_ERROR
    kp_scale_pan: float = 1.0
    kp_scale_tilt: float = 1.0
    feed_forward_pan: float = 0.0
    feed_forward_tilt: float = 0.0
    oscillation_detected: bool = False
    uncertainty_scale: float = 1.0
    adaptive_active: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "gain_schedule": self.gain_schedule.name,
            "kp_scale_pan": round(self.kp_scale_pan, 3),
            "kp_scale_tilt": round(self.kp_scale_tilt, 3),
            "feed_forward_pan": round(self.feed_forward_pan, 3),
            "feed_forward_tilt": round(self.feed_forward_tilt, 3),
            "oscillation_detected": self.oscillation_detected,
            "uncertainty_scale": round(self.uncertainty_scale, 3),
            "reasons": self.reasons,
        }


class AdaptiveController:
    """Adaptive wrapper around the baseline PID controller.

    Features:
    - Gain scheduling based on error magnitude
    - Velocity feed-forward
    - Anti-oscillation detection and mitigation
    - Uncertainty-aware gain reduction
    """

    def __init__(self, config: AdaptiveControllerConfig | None = None) -> None:
        self._config = config or AdaptiveControllerConfig()
        self._error_history: list[float] = []
        self._sign_changes: int = 0
        self._last_sign: int = 0
        self._frame_count: int = 0
        self._oscillation_active: bool = False
        self._base_pan_kp: float = 0.5
        self._base_pan_kd: float = 0.1
        self._base_tilt_kp: float = 0.5
        self._base_tilt_kd: float = 0.1

    def set_baseline_gains(
        self, pan_kp: float, pan_kd: float, tilt_kp: float, tilt_kd: float
    ) -> None:
        self._base_pan_kp = pan_kp
        self._base_pan_kd = pan_kd
        self._base_tilt_kp = tilt_kp
        self._base_tilt_kd = tilt_kd

    def compute_adaptation(
        self,
        error_x: float,
        error_y: float,
        velocity_x: float,
        velocity_y: float,
        uncertainty_level: str = "MODERATE",
        image_width: int = 640,
        image_height: int = 480,
    ) -> AdaptiveTelemetry:
        """Compute adaptive controller parameters.

        Returns:
            AdaptiveTelemetry with scales and diagnostics.
        """
        if not self._config.enabled:
            return AdaptiveTelemetry()

        cfg = self._config
        self._frame_count += 1
        telemetry = AdaptiveTelemetry(adaptive_active=True)

        error_mag = math.sqrt(error_x ** 2 + error_y ** 2)
        schedule = self._select_schedule(error_mag, telemetry)
        telemetry.gain_schedule = schedule

        kp_scale, kd_scale = self._get_gain_scales(schedule)
        telemetry.kp_scale_pan = kp_scale
        telemetry.kp_scale_tilt = kp_scale
        telemetry.kd_scale_pan = kd_scale
        telemetry.kd_scale_tilt = kd_scale

        if cfg.uncertainty_scale_enabled:
            unc_scale = self._uncertainty_scale(uncertainty_level)
            telemetry.uncertainty_scale = unc_scale
            telemetry.kp_scale_pan *= unc_scale
            telemetry.kp_scale_tilt *= unc_scale

        if cfg.anti_oscillation_enabled:
            osc = self._detect_oscillation(error_x)
            telemetry.oscillation_detected = osc
            if osc:
                telemetry.kp_scale_pan *= cfg.oscillation_reduction_factor
                telemetry.kp_scale_tilt *= cfg.oscillation_reduction_factor
                telemetry.kd_scale_pan *= cfg.oscillation_reduction_factor
                telemetry.kd_scale_tilt *= cfg.oscillation_reduction_factor
                telemetry.reasons.append("oscillation_reduction")

        if cfg.feed_forward_enabled:
            ff_pan = velocity_x * cfg.feed_forward_gain / (image_width / 2.0)
            ff_tilt = velocity_y * cfg.feed_forward_gain / (image_height / 2.0)
            telemetry.feed_forward_pan = max(-1.0, min(1.0, ff_pan))
            telemetry.feed_forward_tilt = max(-1.0, min(1.0, ff_tilt))

        telemetry.kp_scale_pan = max(cfg.min_kp_scale, min(cfg.max_kp_scale, telemetry.kp_scale_pan))
        telemetry.kp_scale_tilt = max(cfg.min_kp_scale, min(cfg.max_kp_scale, telemetry.kp_scale_tilt))
        telemetry.kd_scale_pan = max(cfg.min_kd_scale, min(cfg.max_kd_scale, telemetry.kd_scale_pan))
        telemetry.kd_scale_tilt = max(cfg.min_kd_scale, min(cfg.max_kd_scale, telemetry.kd_scale_tilt))

        return telemetry

    def _select_schedule(self, error_mag: float, telemetry: AdaptiveTelemetry) -> GainSchedule:
        cfg = self._config
        if error_mag < cfg.low_error_threshold:
            telemetry.reasons.append("low_error_schedule")
            return GainSchedule.LOW_ERROR
        elif error_mag < cfg.medium_error_threshold:
            return GainSchedule.MEDIUM_ERROR
        else:
            telemetry.reasons.append("high_error_schedule")
            return GainSchedule.HIGH_ERROR

    def _get_gain_scales(self, schedule: GainSchedule) -> tuple[float, float]:
        cfg = self._config
        if schedule == GainSchedule.LOW_ERROR:
            return cfg.low_error_kp_scale, cfg.low_error_kd_scale
        elif schedule == GainSchedule.MEDIUM_ERROR:
            return cfg.medium_error_kp_scale, cfg.medium_error_kd_scale
        else:
            return cfg.high_error_kp_scale, cfg.high_error_kd_scale

    def _uncertainty_scale(self, level: str) -> float:
        cfg = self._config
        mapping = {
            "VERY_LOW": 1.0,
            "LOW": 1.0,
            "MODERATE": 0.9,
            "HIGH": 0.7,
            "VERY_HIGH": cfg.max_uncertainty_reduction,
        }
        return mapping.get(level, 1.0)

    def _detect_oscillation(self, error: float) -> bool:
        cfg = self._config
        self._error_history.append(error)
        if len(self._error_history) > cfg.oscillation_window_frames:
            self._error_history.pop(0)

        if len(self._error_history) < 3:
            return False

        sign = 1 if error > 0 else (-1 if error < 0 else 0)
        if sign != 0 and self._last_sign != 0 and sign != self._last_sign:
            self._sign_changes += 1
        self._last_sign = sign

        if self._sign_changes >= cfg.oscillation_sign_changes:
            self._oscillation_active = True
            return True
        elif self._sign_changes >= 2:
            return False
        else:
            self._oscillation_active = False
            return False

    def apply_to_pid(
        self,
        pid: PIDController,
        telemetry: AdaptiveTelemetry,
        axis: str = "pan",
    ) -> None:
        """Apply adaptive gains to a PID controller instance."""
        if axis == "pan":
            pid.kp = self._base_pan_kp * telemetry.kp_scale_pan
            pid.kd = self._base_pan_kd * telemetry.kd_scale_pan
        else:
            pid.kp = self._base_tilt_kp * telemetry.kp_scale_tilt
            pid.kd = self._base_tilt_kd * telemetry.kd_scale_tilt

    def reset(self) -> None:
        self._error_history.clear()
        self._sign_changes = 0
        self._last_sign = 0
        self._frame_count = 0
        self._oscillation_active = False
