"""Lock quality score.

Engineering score from multiple tracking metrics.
NOT a probability unless explicitly calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LockQualityConfig:
    """Weights for lock quality computation."""

    w_position_error: float = 0.25
    w_confidence: float = 0.20
    w_track_age: float = 0.15
    w_consecutive_hits: float = 0.15
    w_uncertainty: float = 0.10
    w_residual: float = 0.10
    w_image_quality: float = 0.05

    max_position_error_px: float = 50.0
    max_uncertainty: float = 80.0
    max_residual: float = 40.0
    max_track_age_s: float = 10.0
    max_consecutive_hits: int = 30


class LockQualityEstimator:
    """Computes a lock quality score from tracking state.

    Score range: [0.0, 1.0]
        1.0 = perfect lock
        0.0 = no lock quality

    Components:
        - Position error (inversely proportional)
        - Detection confidence
        - Track age (longer = more stable)
        - Consecutive detection hits
        - Position uncertainty
        - Measurement residual
        - Image quality
    """

    def __init__(self, config: LockQualityConfig | None = None) -> None:
        self._config = config or LockQualityConfig()

    def estimate(
        self,
        position_error_px: float = 0.0,
        detection_confidence: float = 0.0,
        track_age_s: float = 0.0,
        consecutive_hits: int = 0,
        position_uncertainty: float = 0.0,
        measurement_residual: float = 0.0,
        image_quality_factor: float = 1.0,
        has_detection: bool = True,
    ) -> float:
        """Estimate lock quality score.

        Returns:
            Score in [0.0, 1.0].
        """
        cfg = self._config

        if not has_detection:
            return 0.0

        err_score = max(0.0, 1.0 - position_error_px / cfg.max_position_error_px)
        conf_score = detection_confidence
        age_score = min(1.0, track_age_s / cfg.max_track_age_s)
        hits_score = min(1.0, consecutive_hits / cfg.max_consecutive_hits)
        unc_score = max(0.0, 1.0 - position_uncertainty / cfg.max_uncertainty)
        res_score = max(0.0, 1.0 - measurement_residual / cfg.max_residual)
        quality_score = image_quality_factor

        score = (
            cfg.w_position_error * err_score
            + cfg.w_confidence * conf_score
            + cfg.w_track_age * age_score
            + cfg.w_consecutive_hits * hits_score
            + cfg.w_uncertainty * unc_score
            + cfg.w_residual * res_score
            + cfg.w_image_quality * quality_score
        )

        return float(max(0.0, min(1.0, score)))
