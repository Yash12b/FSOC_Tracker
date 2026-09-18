"""Minimal debug visualization for the simulation.

Uses OpenCV to draw a simple top-down view of the world,
targets, and their trajectory paths.

This is NOT the final aerospace GUI.
"""

from __future__ import annotations

import numpy as np

try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

from fsoc_tracker.simulation.world import WorldState


def render_world(
    state: WorldState,
    canvas_size: int = 800,
    show_path: bool = True,
    path_history: list[tuple[float, float]] | None = None,
) -> np.ndarray | None:
    """Render a top-down debug view of the world.

    Args:
        state: Current world state.
        canvas_size: Output image size in pixels.
        show_path: Whether to draw the trajectory path.
        path_history: List of (x, y) past positions for path drawing.

    Returns:
        BGR numpy array, or None if OpenCV is not available.
    """
    if not _HAS_CV2:
        return None

    img = np.zeros((canvas_size, canvas_size, 3), dtype=np.uint8)

    cfg = state.config
    world_w = cfg.x_max - cfg.x_min
    world_h = cfg.y_max - cfg.y_min
    scale = canvas_size / max(world_w, world_h)

    def to_px(x: float, y: float) -> tuple[int, int]:
        px = int((x - cfg.x_min) * scale)
        py = int((cfg.y_max - y) * scale)  # flip Y
        return (px, py)

    # Draw world boundary
    tl = to_px(cfg.x_min, cfg.y_max)
    br = to_px(cfg.x_max, cfg.y_min)
    cv2.rectangle(img, tl, br, (60, 60, 60), 2)

    # Draw path history
    if show_path and path_history and len(path_history) > 1:
        pts = [to_px(x, y) for x, y in path_history]
        for i in range(1, len(pts)):
            cv2.line(img, pts[i - 1], pts[i], (0, 100, 200), 1)

    # Draw targets
    colors = [(0, 255, 0), (255, 0, 0), (0, 255, 255), (255, 0, 255)]
    for i, target in enumerate(state.targets):
        if not target.active:
            continue
        px, py = to_px(target.x, target.y)
        color = colors[i % len(colors)]
        r = max(4, int(10 * scale * target.width))
        cv2.circle(img, (px, py), r, color, -1)
        cv2.circle(img, (px, py), r + 2, (255, 255, 255), 1)

        label = f"T{target.target_id}"
        cv2.putText(
            img, label, (px + r + 4, py - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1,
        )

    # Draw info text
    info = f"t={state.simulation_time_s:.2f}s  steps={state.step_count}"
    cv2.putText(img, info, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    n_active = len(state.get_active_targets())
    cv2.putText(
        img, f"targets: {n_active}/{len(state.targets)}",
        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1,
    )

    return img


def show_debug(
    state: WorldState,
    canvas_size: int = 800,
    path_history: list[tuple[float, float]] | None = None,
    window_name: str = "FSOC Simulation Debug",
    wait_ms: int = 1,
) -> bool:
    """Render and display the debug view.

    Returns:
        True if the window is still open, False if the user closed it.
    """
    if not _HAS_CV2:
        return False

    img = render_world(state, canvas_size, path_history=path_history)
    if img is None:
        return False

    cv2.imshow(window_name, img)
    key = cv2.waitKey(wait_ms) & 0xFF
    return key != 27  # ESC closes
