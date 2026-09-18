"""Tracker debug visualization overlay.

Renders tracking state on a copy of the image.
Never contaminates the raw input image.
"""

from __future__ import annotations

import numpy as np

from fsoc_tracker.tracking.state import TrackingState, TrackState


def render_tracking_debug(
    image: np.ndarray,
    state: TrackingState,
    image_width: int = 640,
    image_height: int = 480,
) -> np.ndarray:
    """Render a debug overlay on a copy of the input image.

    Args:
        image: Input grayscale or BGR image.
        state: Current tracking state.
        image_width: Image width for coordinate calculations.
        image_height: Image height for coordinate calculations.

    Returns:
        New image with debug overlay (never modifies input).
    """
    try:
        import cv2
    except ImportError:
        return image.copy()

    if len(image.shape) == 2:
        vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        vis = image.copy()

    cx, cy = image_width // 2, image_height // 2

    # Camera center crosshair
    cv2.drawMarker(vis, (cx, cy), (100, 100, 100), cv2.MARKER_CROSS, 15, 1)

    # Raw detection
    if state.has_detection:
        dx, dy = int(state.detection_x), int(state.detection_y)
        cv2.circle(vis, (dx, dy), 6, (0, 255, 255), 2)  # yellow ring
        cv2.putText(vis, "RAW", (dx + 10, dy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

    # Filtered/estimated position
    ex, ey = int(state.estimated_x), int(state.estimated_y)
    if state.state not in (TrackState.NO_TRACK, TrackState.SEARCHING):
        cv2.circle(vis, (ex, ey), 4, (0, 255, 0), -1)  # green dot

        # Velocity arrow
        if abs(state.velocity_x) > 0.1 or abs(state.velocity_y) > 0.1:
            arrow_scale = 0.1
            vx_end = int(ex + state.velocity_x * arrow_scale)
            vy_end = int(ey + state.velocity_y * arrow_scale)
            cv2.arrowedLine(vis, (ex, ey), (vx_end, vy_end), (0, 200, 0), 2, tipLength=0.3)

        # Uncertainty ellipse
        if state.uncertainty_x > 0 and state.uncertainty_y > 0:
            ux, uy = int(state.uncertainty_x * 2), int(state.uncertainty_y * 2)
            cv2.ellipse(vis, (ex, ey), (ux, uy), 0, 0, 360, (100, 100, 255), 1)

        # Predicted position
        px, py = int(state.predicted_x), int(state.predicted_y)
        cv2.drawMarker(vis, (px, py), (255, 150, 0), cv2.MARKER_DIAMOND, 8, 1)

    # Status text
    y_offset = 20
    line_h = 18

    state_text = state.state.name
    color = (0, 255, 0) if state.state == TrackState.TRACKING else \
            (0, 255, 255) if state.state in (TrackState.ACQUIRING, TrackState.REACQUIRING) else \
            (0, 0, 255) if state.state == TrackState.LOST else (150, 150, 150)

    cv2.putText(vis, f"STATE: {state_text}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    y_offset += line_h

    lock_text = "YES" if state.locked else "NO"
    lock_color = (0, 255, 0) if state.locked else (0, 0, 255)
    cv2.putText(vis, f"LOCK: {lock_text}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, lock_color, 1)
    y_offset += line_h

    cv2.putText(vis, f"VX: {state.velocity_x:.1f} px/s", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    y_offset += line_h
    cv2.putText(vis, f"VY: {state.velocity_y:.1f} px/s", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    y_offset += line_h

    miss_ms = state.consecutive_misses
    cv2.putText(vis, f"MISS: {miss_ms}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    y_offset += line_h

    cv2.putText(vis, f"AGE: {state.track_age_s:.2f}s", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    y_offset += line_h

    cv2.putText(vis, f"Q: {state.quality:.2f}", (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    return vis
