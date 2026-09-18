"""Ground-truth comparison helper for evaluation.

Compares detections against ground truth to compute centroid error,
RMSE, and accuracy metrics. Ground truth is ONLY used by evaluation code;
detectors never see it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from fsoc_tracker.perception.models import BeaconDetection
from fsoc_tracker.simulation.sensor.models import GroundTruth


@dataclass
class EvaluationMetrics:
    """Metrics comparing a detection against ground truth."""

    error_x: float = 0.0
    error_y: float = 0.0
    absolute_x_error: float = 0.0
    absolute_y_error: float = 0.0
    euclidean_error: float = 0.0
    detected: bool = False
    ground_truth_visible: bool = False

    def to_dict(self) -> dict:
        return {
            "error_x": self.error_x,
            "error_y": self.error_y,
            "absolute_x_error": self.absolute_x_error,
            "absolute_y_error": self.absolute_y_error,
            "euclidean_error": self.euclidean_error,
            "detected": self.detected,
            "ground_truth_visible": self.ground_truth_visible,
        }


def compare_detection_to_ground_truth(
    detection: BeaconDetection | None,
    ground_truth: GroundTruth,
) -> EvaluationMetrics:
    """Compare a single detection against ground truth.

    Args:
        detection: The detected beacon (may be None if not detected).
        ground_truth: The ground-truth target state.

    Returns:
        EvaluationMetrics with error measurements.
    """
    metrics = EvaluationMetrics()
    metrics.ground_truth_visible = ground_truth.target_visible

    if detection is None or not detection.detected:
        metrics.detected = False
        if ground_truth.target_visible:
            metrics.error_x = 0.0
            metrics.error_y = 0.0
            metrics.absolute_x_error = 0.0
            metrics.absolute_y_error = 0.0
            metrics.euclidean_error = float("inf")
        return metrics

    metrics.detected = True
    metrics.error_x = detection.center_x - ground_truth.target_pixel_x
    metrics.error_y = detection.center_y - ground_truth.target_pixel_y
    metrics.absolute_x_error = abs(metrics.error_x)
    metrics.absolute_y_error = abs(metrics.error_y)
    metrics.euclidean_error = math.sqrt(metrics.error_x**2 + metrics.error_y**2)

    return metrics


def compute_rmse(errors: list[float]) -> float:
    """Compute root mean square error from a list of errors."""
    if not errors:
        return 0.0
    mean_sq = sum(e**2 for e in errors) / len(errors)
    return math.sqrt(mean_sq)


def compute_centroid_error(
    detected_x: float,
    detected_y: float,
    true_x: float,
    true_y: float,
) -> tuple[float, float, float]:
    """Compute centroid error between detected and true positions.

    Returns:
        (error_x, error_y, euclidean_error)
    """
    ex = detected_x - true_x
    ey = detected_y - true_y
    return (ex, ey, math.sqrt(ex**2 + ey**2))
