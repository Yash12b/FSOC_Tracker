"""Subpixel centroid estimation.

Provides geometric and intensity-weighted centroid methods
with robust fallback for edge cases.
"""

from __future__ import annotations

import numpy as np

from fsoc_tracker.perception.config import CentroidMethod


def compute_centroid(
    image: np.ndarray,
    mask: np.ndarray,
    method: CentroidMethod = CentroidMethod.INTENSITY_WEIGHTED,
) -> tuple[float, float]:
    """Compute the centroid of a candidate region.

    Args:
        image: Grayscale image.
        mask: Binary mask for the candidate.
        method: Centroid estimation method.

    Returns:
        (centroid_x, centroid_y) in pixel coordinates.
    """
    if mask is None or not np.any(mask):
        return (0.0, 0.0)

    img = image.astype(np.float64)
    m = mask.astype(bool)

    if method == CentroidMethod.INTENSITY_WEIGHTED:
        result = _weighted_centroid(img, m)
        if result is not None:
            return result

    return _geometric_centroid(m)


def _weighted_centroid(image: np.ndarray, mask: np.ndarray) -> tuple[float, float] | None:
    """Compute intensity-weighted centroid.

    x_c = sum(w_i * x_i) / sum(w_i)
    y_c = sum(w_i * y_i) / sum(w_i)

    Falls back to None if weights sum to zero or invalid.
    """
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None

    weights = image[mask]

    if np.any(np.isnan(weights)) or np.any(np.isinf(weights)):
        weights = np.nan_to_num(weights, nan=0.0, posinf=0.0, neginf=0.0)

    weights = np.maximum(weights, 0.0)
    total_weight = np.sum(weights)

    if total_weight <= 0 or not np.isfinite(total_weight):
        return None

    cx = float(np.sum(xs * weights) / total_weight)
    cy = float(np.sum(ys * weights) / total_weight)

    if not (np.isfinite(cx) and np.isfinite(cy)):
        return None

    return (cx, cy)


def _geometric_centroid(mask: np.ndarray) -> tuple[float, float]:
    """Compute simple geometric centroid (mean of pixel coordinates)."""
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return (0.0, 0.0)
    return (float(np.mean(xs)), float(np.mean(ys)))
