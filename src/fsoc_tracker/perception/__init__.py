"""Perception subsystem — target detection and recognition.

Provides the PerceptionEngine ABC, classical bright-spot detector,
data models, preprocessing, candidate generation, scoring, centroid
estimation, evaluation, and debug visualization.
"""

from fsoc_tracker.perception.base import PerceptionEngine
from fsoc_tracker.perception.classical import detect_beacon
from fsoc_tracker.perception.classical_engine import ClassicalBeaconDetector
from fsoc_tracker.perception.config import (
    CentroidMethod,
    PerceptionConfig,
    ThresholdMode,
)
from fsoc_tracker.perception.evaluation import (
    EvaluationMetrics,
    compare_detection_to_ground_truth,
    compute_centroid_error,
    compute_rmse,
)
from fsoc_tracker.perception.models import (
    BeaconDetection,
    CandidateFeatures,
    PerceptionResult,
    PerceptionStatus,
    TargetClass,
)
from fsoc_tracker.perception.visualization import render_perception_debug

__all__ = [
    "BeaconDetection",
    "CandidateFeatures",
    "CentroidMethod",
    "ClassicalBeaconDetector",
    "EvaluationMetrics",
    "PerceptionConfig",
    "PerceptionEngine",
    "PerceptionResult",
    "PerceptionStatus",
    "TargetClass",
    "ThresholdMode",
    "compare_detection_to_ground_truth",
    "compute_centroid_error",
    "compute_rmse",
    "detect_beacon",
    "render_perception_debug",
]
