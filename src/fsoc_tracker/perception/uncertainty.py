"""Uncertainty estimation for perception and tracking.

Provides structured uncertainty state that captures position uncertainty,
confidence, and quality from multiple sources. NOT an arbitrary percentage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto


class UncertaintyLevel(Enum):
    VERY_LOW = auto()
    LOW = auto()
    MODERATE = auto()
    HIGH = auto()
    VERY_HIGH = auto()


@dataclass
class UncertaintyState:
    """Structured uncertainty for one frame.

    Combines detector confidence, Kalman covariance, measurement
    residual, image quality, and missed-detection history into a
    single coherent uncertainty estimate.
    """

    position_uncertainty_x: float = 0.0
    position_uncertainty_y: float = 0.0
    position_uncertainty_total: float = 0.0

    velocity_uncertainty_x: float = 0.0
    velocity_uncertainty_y: float = 0.0

    covariance_trace: float = 0.0
    covariance_determinant: float = 0.0

    detection_confidence: float = 0.0
    measurement_residual: float = 0.0
    quality_factor: float = 1.0

    missed_detection_count: int = 0
    time_since_detection_s: float = 0.0

    level: UncertaintyLevel = UncertaintyLevel.MODERATE

    def to_dict(self) -> dict:
        return {
            "position_uncertainty_x": round(self.position_uncertainty_x, 3),
            "position_uncertainty_y": round(self.position_uncertainty_y, 3),
            "position_uncertainty_total": round(self.position_uncertainty_total, 3),
            "covariance_trace": round(self.covariance_trace, 1),
            "detection_confidence": round(self.detection_confidence, 3),
            "measurement_residual": round(self.measurement_residual, 2),
            "quality_factor": round(self.quality_factor, 3),
            "missed_detection_count": self.missed_detection_count,
            "level": self.level.name,
        }


class UncertaintyEstimator:
    """Computes uncertainty state from filter and perception data.

    Sources of uncertainty:
    - Kalman filter covariance (position)
    - Detection confidence (inverse relationship)
    - Measurement residual (innovation)
    - Image quality (via quality factor)
    - Missed detection history (accumulating uncertainty)
    """

    def estimate(
        self,
        kalman_covariance: object | None = None,
        detection_confidence: float = 0.0,
        measurement_residual: float = 0.0,
        quality_factor: float = 1.0,
        missed_detections: int = 0,
        time_since_detection_s: float = 0.0,
        kalman_position_uncertainty: tuple[float, float] | None = None,
        kalman_velocity_uncertainty: tuple[float, float] | None = None,
    ) -> UncertaintyState:
        """Estimate combined uncertainty from multiple sources.

        Args:
            kalman_covariance: 4x4 state covariance matrix (numpy array).
            detection_confidence: Detector output confidence [0, 1].
            measurement_residual: Last measurement residual magnitude (px).
            quality_factor: Image quality factor [0, 1] (1=excellent).
            missed_detections: Consecutive missed detection count.
            time_since_detection_s: Time since last valid detection (s).
            kalman_position_uncertainty: (sigma_x, sigma_y) from Kalman.
            kalman_velocity_uncertainty: (sigma_vx, sigma_vy) from Kalman.

        Returns:
            UncertaintyState with all fields computed.
        """
        state = UncertaintyState()

        if kalman_position_uncertainty is not None:
            state.position_uncertainty_x = kalman_position_uncertainty[0]
            state.position_uncertainty_y = kalman_position_uncertainty[1]
            state.position_uncertainty_total = math.sqrt(
                state.position_uncertainty_x ** 2 + state.position_uncertainty_y ** 2
            )
        elif kalman_covariance is not None:
            try:
                import numpy as np
                cov = np.asarray(kalman_covariance)
                state.position_uncertainty_x = float(np.sqrt(max(0.0, cov[0, 0])))
                state.position_uncertainty_y = float(np.sqrt(max(0.0, cov[1, 1])))
                state.position_uncertainty_total = math.sqrt(
                    state.position_uncertainty_x ** 2 + state.position_uncertainty_y ** 2
                )
                state.covariance_trace = float(np.trace(cov))
                state.covariance_determinant = float(np.linalg.det(cov))
            except Exception:
                state.position_uncertainty_total = 100.0

        if kalman_velocity_uncertainty is not None:
            state.velocity_uncertainty_x = kalman_velocity_uncertainty[0]
            state.velocity_uncertainty_y = kalman_velocity_uncertainty[1]

        state.detection_confidence = max(0.0, min(1.0, detection_confidence))
        state.measurement_residual = abs(measurement_residual)
        state.quality_factor = max(0.0, min(1.0, quality_factor))
        state.missed_detection_count = max(0, missed_detections)
        state.time_since_detection_s = max(0.0, time_since_detection_s)

        state.level = self._classify(state)

        return state

    def _classify(self, state: UncertaintyState) -> UncertaintyLevel:
        """Classify uncertainty level from combined metrics."""
        score = 0.0

        score += min(1.0, state.position_uncertainty_total / 50.0) * 0.30
        score += (1.0 - state.detection_confidence) * 0.20
        score += min(1.0, state.measurement_residual / 30.0) * 0.15
        score += (1.0 - state.quality_factor) * 0.15
        score += min(1.0, state.missed_detection_count / 5.0) * 0.10
        score += min(1.0, state.time_since_detection_s / 2.0) * 0.10

        if score < 0.15:
            return UncertaintyLevel.VERY_LOW
        elif score < 0.30:
            return UncertaintyLevel.LOW
        elif score < 0.55:
            return UncertaintyLevel.MODERATE
        elif score < 0.80:
            return UncertaintyLevel.HIGH
        else:
            return UncertaintyLevel.VERY_HIGH
