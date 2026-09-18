"""Adaptive Kalman filter enhancements.

Adds Q/R adaptation based on image quality, maneuver state,
and detection confidence. Conservative bounded adaptation —
no unstable feedback.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fsoc_tracker.perception.quality import QualityState
from fsoc_tracker.perception.uncertainty import UncertaintyLevel, UncertaintyState
from fsoc_tracker.tracking.maneuver import ManeuverState, MotionClass


@dataclass
class AdaptiveKalmanConfig:
    """Configuration for adaptive Kalman filter."""

    enabled: bool = True

    q_scale_min: float = 0.3
    q_scale_max: float = 5.0
    r_scale_min: float = 0.5
    r_scale_max: float = 10.0

    quality_q_map: dict = None
    quality_r_map: dict = None
    maneuver_q_scale: float = 3.0
    uncertainty_r_scale: float = 2.0

    smoothing_alpha: float = 0.3

    def __post_init__(self):
        if self.quality_q_map is None:
            self.quality_q_map = {
                "EXCELLENT": 0.5,
                "GOOD": 0.8,
                "DEGRADED": 1.5,
                "POOR": 2.5,
                "CRITICAL": 4.0,
            }
        if self.quality_r_map is None:
            self.quality_r_map = {
                "EXCELLENT": 0.6,
                "GOOD": 1.0,
                "DEGRADED": 2.0,
                "POOR": 4.0,
                "CRITICAL": 8.0,
            }


class AdaptiveKalmanManager:
    """Manages adaptive Q/R scaling for the Kalman filter.

    Adaptation strategy:
    - Measurement noise R increases with poor image quality
    - Process noise Q increases during target maneuvering
    - Both are bounded and smoothed to prevent instability
    """

    def __init__(self, config: AdaptiveKalmanConfig | None = None) -> None:
        self._config = config or AdaptiveKalmanConfig()
        self._current_q_scale: float = 1.0
        self._current_r_scale: float = 1.0

    @property
    def q_scale(self) -> float:
        return self._current_q_scale

    @property
    def r_scale(self) -> float:
        return self._current_r_scale

    def update(
        self,
        quality: QualityState | None = None,
        maneuver: ManeuverState | None = None,
        uncertainty: UncertaintyState | None = None,
        detection_confidence: float = 0.0,
        has_detection: bool = True,
    ) -> tuple[float, float]:
        """Compute adaptive Q and R scale factors.

        Returns:
            (q_scale, r_scale) — multipliers for base Q and R matrices.
        """
        if not self._config.enabled:
            return 1.0, 1.0

        target_q = 1.0
        target_r = 1.0

        if quality is not None:
            level_name = quality.level.name
            q_map = self._config.quality_q_map
            r_map = self._config.quality_r_map
            target_q *= q_map.get(level_name, 1.0)
            target_r *= r_map.get(level_name, 1.0)

        if maneuver is not None:
            if maneuver.motion_class == MotionClass.MANEUVERING:
                target_q *= self._config.maneuver_q_scale
            elif maneuver.motion_class == MotionClass.UNPREDICTABLE:
                target_q *= self._config.maneuver_q_scale * 2.0

        if uncertainty is not None:
            if uncertainty.level in (UncertaintyLevel.HIGH, UncertaintyLevel.VERY_HIGH):
                target_r *= self._config.uncertainty_r_scale
            elif uncertainty.level == UncertaintyLevel.MODERATE:
                target_r *= 1.3

        if has_detection and detection_confidence > 0.7:
            target_r *= 0.8

        target_q = max(self._config.q_scale_min, min(self._config.q_scale_max, target_q))
        target_r = max(self._config.r_scale_min, min(self._config.r_scale_max, target_r))

        alpha = self._config.smoothing_alpha
        self._current_q_scale = alpha * target_q + (1.0 - alpha) * self._current_q_scale
        self._current_r_scale = alpha * target_r + (1.0 - alpha) * self._current_r_scale

        return self._current_q_scale, self._current_r_scale

    def apply_to_matrices(
        self,
        Q: np.ndarray,
        R: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Apply adaptive scaling to Q and R matrices.

        Args:
            Q: Process noise covariance (4x4).
            R: Measurement noise covariance (2x2).

        Returns:
            (Q_scaled, R_scaled) with adaptive scaling applied.
        """
        return Q * self._current_q_scale, R * self._current_r_scale

    def reset(self) -> None:
        self._current_q_scale = 1.0
        self._current_r_scale = 1.0
