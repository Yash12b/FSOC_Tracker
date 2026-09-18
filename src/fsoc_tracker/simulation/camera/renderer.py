"""Minimal software renderer for camera view debug visualization.

Renders projected beacons and camera frame border onto an OpenCV image.
No hardware GPU required.
"""

from __future__ import annotations

import numpy as np

from fsoc_tracker.simulation.camera.state import CameraIntrinsics, ProjectionResult


def render_camera_view(
    intrinsics: CameraIntrinsics,
    projections: list[ProjectionResult],
    background_color: tuple[int, int, int] = (20, 20, 20),
    target_color: tuple[int, int, int] = (0, 255, 0),
    target_size: int = 8,
) -> np.ndarray:
    """Render a minimal camera view with projected targets.

    Args:
        intrinsics: Camera intrinsic parameters for image dimensions.
        projections: List of projection results to draw.
        background_color: BGR background color.
        target_color: BGR color for visible targets.
        target_size: Half-size of the target marker in pixels.

    Returns:
        BGR numpy array of shape (height, width, 3).
    """
    img = np.full(
        (intrinsics.height, intrinsics.width, 3),
        background_color,
        dtype=np.uint8,
    )

    for proj in projections:
        if not proj.visible:
            continue

        px = int(round(proj.pixel_x))
        py = int(round(proj.pixel_y))

        x1 = max(0, px - target_size)
        y1 = max(0, py - target_size)
        x2 = min(intrinsics.width - 1, px + target_size)
        y2 = min(intrinsics.height - 1, py + target_size)

        img[y1:y2 + 1, x1:x2 + 1] = target_color

    return img
