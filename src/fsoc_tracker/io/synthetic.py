"""Minimal synthetic frame source for testing and development.

Generates frames with a simple beacon dot that can be moved in
a straight line, allowing end-to-end pipeline validation without
any external dependencies (no OpenCV video, no 3D renderer).

This source is intentionally simple.  The full virtual simulation
environment will be implemented in Stage 2-4.
"""

from __future__ import annotations

import math
import time

import numpy as np

from fsoc_tracker.core.exceptions import FrameSourceError
from fsoc_tracker.core.interfaces import FrameSource
from fsoc_tracker.core.models import ColorModel, Frame, SourceType


class SyntheticFrameSource(FrameSource):
    """Generates synthetic frames with a moving beacon dot.

    The beacon moves in a configurable pattern within a virtual canvas
    that is then cropped to the camera's field of view.

    Args:
        canvas_width: Width of the virtual canvas in pixels.
        canvas_height: Height of the virtual canvas in pixels.
        camera_width: Output frame width (camera resolution).
        camera_height: Output frame height (camera resolution).
        target_size_px: Diameter of the beacon dot in pixels.
        fps: Nominal frame rate for timestamp generation.
        total_frames: Number of frames to generate before exhaustion.
        motion_type: One of ``"straight_line"``, ``"circular"``,
            ``"figure_8"``, or ``"random"``.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        canvas_width: int = 2000,
        canvas_height: int = 2000,
        camera_width: int = 640,
        camera_height: int = 480,
        target_size_px: int = 10,
        fps: float = 30.0,
        total_frames: int = 300,
        motion_type: str = "straight_line",
        seed: int = 42,
    ) -> None:
        self._canvas_w = canvas_width
        self._canvas_h = canvas_height
        self._cam_w = camera_width
        self._cam_h = camera_height
        self._target_size = target_size_px
        self._fps = fps
        self._total_frames = total_frames
        self._motion_type = motion_type
        self._rng = np.random.default_rng(seed)

        self._frame_index = 0
        self._open = False
        self._start_time = 0.0
        self._source_id = f"synthetic-{motion_type}-{seed}"

        # Camera position in canvas coordinates (center of FOV)
        self._cam_x = canvas_width / 2.0
        self._cam_y = canvas_height / 2.0

    def open(self) -> None:
        self._frame_index = 0
        self._start_time = time.monotonic()
        self._open = True

    def is_open(self) -> bool:
        return self._open

    def release(self) -> None:
        self._open = False

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def nominal_fps(self) -> float | None:
        return self._fps

    @property
    def frame_count(self) -> int | None:
        return self._total_frames

    @property
    def width(self) -> int | None:
        return self._cam_w

    @property
    def height(self) -> int | None:
        return self._cam_h

    def _beacon_position(self, t: float) -> tuple[float, float]:
        """Compute beacon position in canvas coordinates at time *t*.

        Motion is always centered on the camera viewport so the beacon
        remains visible during normal test durations.
        """
        # Use camera center as the reference point, not canvas center.
        # This ensures the beacon is always within or near the FOV.
        cx = self._cam_x
        cy = self._cam_y
        # Amplitude: 80% of the smaller camera half-dimension, so the
        # beacon sweeps within the camera viewport.
        amplitude = min(self._cam_w, self._cam_h) * 0.4

        if self._motion_type == "circular":
            angle = 2.0 * math.pi * t * 0.1
            x = cx + amplitude * math.cos(angle)
            y = cy + amplitude * math.sin(angle)

        elif self._motion_type == "figure_8":
            angle = 2.0 * math.pi * t * 0.1
            x = cx + amplitude * 0.8 * math.sin(angle)
            y = cy + amplitude * 0.4 * math.sin(2.0 * angle)

        elif self._motion_type == "random":
            x = cx + self._rng.uniform(-amplitude, amplitude)
            y = cy + self._rng.uniform(-amplitude, amplitude)

        else:
            # straight_line: sweep horizontally across the camera viewport
            progress = (t * 0.5) % 2.0  # 0 -> 2 -> 0 -> ...
            if progress > 1.0:
                progress = 2.0 - progress
            x = cx - amplitude + 2.0 * amplitude * progress
            y = cy + amplitude * 0.3 * math.sin(2.0 * math.pi * t * 0.2)

        return x, y

    def _render_frame(self, beacon_x: float, beacon_y: float) -> np.ndarray:
        """Render a single frame with the beacon visible in the camera FOV."""
        frame = np.zeros((self._cam_h, self._cam_w, 3), dtype=np.uint8)

        # Camera viewport in canvas coords
        cam_left = self._cam_x - self._cam_w / 2.0
        cam_top = self._cam_y - self._cam_h / 2.0

        # Beacon position relative to camera viewport
        rel_x = beacon_x - cam_left
        rel_y = beacon_y - cam_top

        # Draw beacon (bright circle)
        r = self._target_size // 2
        ix, iy = int(rel_x), int(rel_y)

        # Check if beacon is within camera FOV
        if -r <= ix < self._cam_w + r and -r <= iy < self._cam_h + r:
            y_lo = max(0, iy - r)
            y_hi = min(self._cam_h, iy + r + 1)
            x_lo = max(0, ix - r)
            x_hi = min(self._cam_w, ix + r + 1)
            frame[y_lo:y_hi, x_lo:x_hi] = (255, 255, 255)  # white beacon

        return frame

    def read(self) -> Frame | None:
        if not self._open:
            raise FrameSourceError("Source is not open. Call open() first.")

        if self._frame_index >= self._total_frames:
            return None

        t = self._frame_index / self._fps
        beacon_x, beacon_y = self._beacon_position(t)
        image = self._render_frame(beacon_x, beacon_y)

        timestamp_s = self._frame_index / self._fps
        monotonic_s = self._start_time + t

        frame = Frame(
            image=image,
            width=self._cam_w,
            height=self._cam_h,
            channels=3,
            color_model=ColorModel.BGR,
            source_id=self._source_id,
            source_type=SourceType.SYNTHETIC,
            frame_index=self._frame_index,
            timestamp_s=timestamp_s,
            monotonic_time_s=monotonic_s,
            nominal_fps=self._fps,
            metadata={
                "beacon_x_canvas": beacon_x,
                "beacon_y_canvas": beacon_y,
                "cam_x_canvas": self._cam_x,
                "cam_y_canvas": self._cam_y,
            },
        )

        self._frame_index += 1
        return frame
