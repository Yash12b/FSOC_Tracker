"""Debug visualization for perception results.

Creates visualization copies showing candidates, detections,
and metadata. Never contaminates the raw image.
"""

from __future__ import annotations

import numpy as np

from fsoc_tracker.perception.models import PerceptionResult


def render_perception_debug(
    image: np.ndarray,
    result: PerceptionResult,
    show_candidates: bool = True,
    show_primary: bool = True,
    show_center: bool = True,
    show_info: bool = True,
) -> np.ndarray:
    """Create a debug visualization copy of the perception result.

    Args:
        image: Original grayscale image.
        result: PerceptionResult to visualize.
        show_candidates: Draw all candidate regions.
        show_primary: Draw primary detection highlight.
        show_center: Draw image center crosshair.
        show_info: Draw text info overlay.

    Returns:
        BGR numpy array for display.
    """
    if image is None or image.size == 0:
        return np.zeros((1, 1, 3), dtype=np.uint8)

    if image.ndim == 2:
        vis = np.stack([image, image, image], axis=-1)
    else:
        vis = image.copy()

    vis = vis.astype(np.uint8)
    h, w = vis.shape[:2]

    cx, cy = w // 2, h // 2

    if show_center:
        _draw_crosshair(vis, cx, cy, color=(0, 255, 0), size=10)

    for det in result.detections:
        if not det.detected and not show_candidates:
            continue
        x1, y1, x2, y2 = det.bbox
        color = (0, 165, 255) if det.detected else (128, 128, 128)
        _draw_rect(vis, x1, y1, x2, y2, color)

    if result.primary_detection and show_primary:
        pd = result.primary_detection
        x1, y1, x2, y2 = pd.bbox
        _draw_rect(vis, x1, y1, x2, y2, color=(0, 0, 255), thickness=2)

        px = int(round(pd.center_x))
        py = int(round(pd.center_y))
        _draw_crosshair(vis, px, py, color=(0, 0, 255), size=5)

    if show_info:
        _draw_info(vis, result, cx, cy)

    return vis


def _draw_crosshair(img: np.ndarray, cx: int, cy: int, color: tuple, size: int = 10) -> None:
    h, w = img.shape[:2]
    x1 = max(0, cx - size)
    x2 = min(w, cx + size)
    y1 = max(0, cy - size)
    y2 = min(h, cy + size)
    img[cy, x1:x2] = color
    img[y1:y2, cx] = color


def _draw_rect(img: np.ndarray, x1: int, y1: int, x2: int, y2: int, color: tuple, thickness: int = 1) -> None:
    h, w = img.shape[:2]
    x1c = max(0, min(w - 1, x1))
    x2c = max(0, min(w, x2))
    y1c = max(0, min(h - 1, y1))
    y2c = max(0, min(h, y2))
    img[y1c, x1c:x2c] = color
    img[y2c - 1, x1c:x2c] = color
    img[y1c:y2c, x1c] = color
    img[y1c:y2c, x2c - 1] = color


def _draw_info(img: np.ndarray, result: PerceptionResult, cx: int, cy: int) -> None:
    h, w = img.shape[:2]
    y0 = 15
    dy = 16

    texts = [
        f"detected: {result.detected}",
        f"status: {result.status.name}",
        f"candidates: {result.num_candidates}",
        f"time: {result.processing_time_ms:.1f}ms",
    ]

    if result.primary_detection:
        pd = result.primary_detection
        texts.append(f"conf: {pd.confidence:.3f}")
        texts.append(f"pos: ({pd.center_x:.1f}, {pd.center_y:.1f})")
        dx = pd.center_x - cx
        dy_err = pd.center_y - cy
        texts.append(f"err: ({dx:+.1f}, {dy_err:+.1f})")

    for i, txt in enumerate(texts):
        y_pos = y0 + i * dy
        if y_pos < h - 5:
            try:
                import cv2
                cv2.putText(img, txt, (5, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)
            except ImportError:
                pass
