"""Detection-to-track association and gating.

Provides nearest-neighbor association with Euclidean and Mahalanobis gating.
The tracker uses this to match incoming detections to existing tracks.
"""

from __future__ import annotations

import math


from fsoc_tracker.perception.models import BeaconDetection
from fsoc_tracker.tracking.config import AssociationMethod, TrackerConfig


def euclidean_distance(
    det_x: float, det_y: float,
    pred_x: float, pred_y: float,
) -> float:
    """Euclidean distance between detection and predicted position."""
    dx = det_x - pred_x
    dy = det_y - pred_y
    return math.sqrt(dx * dx + dy * dy)


def associate_nearest(
    detections: list[BeaconDetection],
    predicted_position: tuple[float, float],
    config: TrackerConfig,
    kalman_mahal_fn: object | None = None,
) -> BeaconDetection | None:
    """Associate the best detection to the predicted position.

    Uses gating to reject implausible associations.

    Args:
        detections: List of candidate detections from perception.
        predicted_position: Kalman filter predicted position (px, py).
        config: Tracker configuration.
        kalman_mahal_fn: Optional callable(measurement) -> Mahalanobis distance.

    Returns:
        The best associated detection, or None if no detection passes the gate.
    """
    if not detections:
        return None

    pred_x, pred_y = predicted_position
    gate_px = config.association_gate_px
    use_mahal = config.association_method == AssociationMethod.MAHALANOBIS
    gate_mahal = config.association_gate_mahal

    best_det: BeaconDetection | None = None
    best_score = float("inf")

    for det in detections:
        if not det.detected:
            continue
        if det.confidence < config.minimum_detection_confidence:
            continue

        det_x, det_y = det.center_x, det.center_y
        euc_dist = euclidean_distance(det_x, det_y, pred_x, pred_y)

        # Euclidean gate
        if euc_dist > gate_px:
            continue

        # Mahalanobis gate with a Euclidean floor: early in a track the
        # covariance is tiny, which would reject valid measurements, so
        # anything very close is always accepted.
        if use_mahal and kalman_mahal_fn is not None:
            mahal = kalman_mahal_fn((det_x, det_y))
            floor = getattr(config, "association_gate_floor_px", 0.0) or 0.0
            if mahal > gate_mahal and euc_dist > floor:
                continue
            score = mahal
        else:
            score = euc_dist

        if score < best_score:
            best_score = score
            best_det = det

    return best_det
