"""Canonical image/model coordinate conversions for visual AI."""

from __future__ import annotations

import numpy as np


def source_to_model(
    x: float, y: float, source_width: int, source_height: int,
    model_width: int, model_height: int,
) -> tuple[float, float]:
    """Map source pixel coordinates to model pixel coordinates."""
    if min(source_width, source_height, model_width, model_height) <= 0:
        raise ValueError("image dimensions must be positive")
    return x * model_width / source_width, y * model_height / source_height


def model_to_source(
    x: float, y: float, model_width: int, model_height: int,
    source_width: int, source_height: int,
) -> tuple[float, float]:
    """Map model pixel coordinates to source pixel coordinates."""
    if min(source_width, source_height, model_width, model_height) <= 0:
        raise ValueError("image dimensions must be positive")
    return x * source_width / model_width, y * source_height / model_height


def decode_heatmap_center(
    heatmap: np.ndarray,
    source_width: int,
    source_height: int,
    *,
    window_radius: int = 1,
) -> tuple[float, float, float]:
    """Return a subpixel weighted peak and its confidence."""
    if heatmap.ndim != 2 or heatmap.size == 0:
        raise ValueError("heatmap must be a non-empty 2D array")
    height, width = heatmap.shape
    py, px = np.unravel_index(int(np.argmax(heatmap)), heatmap.shape)
    radius = max(0, window_radius)
    y0, y1 = max(0, py - radius), min(height, py + radius + 1)
    x0, x1 = max(0, px - radius), min(width, px + radius + 1)
    patch = np.maximum(heatmap[y0:y1, x0:x1], 0.0)
    total = float(np.sum(patch))
    if total <= 0.0:
        refined_x, refined_y = float(px), float(py)
    else:
        yy, xx = np.mgrid[y0:y1, x0:x1]
        refined_x = float(np.sum(xx * patch) / total)
        refined_y = float(np.sum(yy * patch) / total)
    x, y = model_to_source(refined_x, refined_y, width, height, source_width, source_height)
    return x, y, float(heatmap[py, px])
