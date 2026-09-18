"""Observable feature extraction for AI integration.

Extracts ONLY runtime-observable features from TrackingState + camera state.
NEVER accesses ground truth, simulator internals, or future information.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fsoc_tracker.tracking.state import TrackingState


@dataclass
class ObservableFeatures:
    """Runtime-observable features for AI inference.

    All values are derived from:
    - TrackingState (tracker output)
    - Camera intrinsics + dimensions
    - Clock (timestamps, dt)
    - Pipeline counters (processing FPS, candidate count)

    NEVER from: WorldTruth, SimulationEngine, beacon config, trajectories.
    """
    # Position estimate (pixel space)
    estimated_x: float = 0.0
    estimated_y: float = 0.0

    # Velocity (pixel space)
    velocity_x: float = 0.0
    velocity_y: float = 0.0

    # Uncertainty
    uncertainty_x: float = 0.0
    uncertainty_y: float = 0.0

    # Detection state
    has_detection: bool = False
    detection_confidence: float = 0.0
    detection_age_s: float = 0.0
    miss_count: int = 0

    # Residual (innovation)
    residual_x: float = 0.0
    residual_y: float = 0.0
    residual_magnitude: float = 0.0

    # Track state
    track_state: str = "NO_TRACK"
    consecutive_hits: int = 0

    # Temporal
    dt: float = 0.0
    timestamp_s: float = 0.0

    # FOV / border margin (normalized 0..1, 0 = at edge, 1 = at center)
    fov_margin_x: float = 0.5
    fov_margin_y: float = 0.5

    # Processing pipeline
    processing_fps: float = 0.0
    processing_latency_ms: float = 0.0

    # Historical observations (last N positions)
    position_history: list[tuple[float, float]] | None = None
    velocity_history: list[tuple[float, float]] | None = None

    def to_feature_vector(self) -> np.ndarray:
        """Convert to fixed-size numpy vector for model input."""
        hist = self.position_history or []
        vel_hist = self.velocity_history or []

        # Average velocity over recent history
        if vel_hist:
            avg_vx = float(np.mean([v[0] for v in vel_hist[-5:]]))
            avg_vy = float(np.mean([v[1] for v in vel_hist[-5:]]))
        else:
            avg_vx = self.velocity_x
            avg_vy = self.velocity_y

        # Velocity acceleration (difference of recent velocities)
        if len(vel_hist) >= 2:
            accel_x = vel_hist[-1][0] - vel_hist[-2][0]
            accel_y = vel_hist[-1][1] - vel_hist[-2][1]
        else:
            accel_x = 0.0
            accel_y = 0.0

        # Position variance (spread)
        if len(hist) >= 3:
            xs = [p[0] for p in hist[-5:]]
            ys = [p[1] for p in hist[-5:]]
            pos_var_x = float(np.var(xs))
            pos_var_y = float(np.var(ys))
        else:
            pos_var_x = 0.0
            pos_var_y = 0.0

        return np.array([
            float(self.has_detection),
            self.detection_confidence,
            self.residual_magnitude,
            self.uncertainty_x,
            self.uncertainty_y,
            avg_vx,
            avg_vy,
            accel_x,
            accel_y,
            self.fov_margin_x,
            self.fov_margin_y,
            self.detection_age_s,
            pos_var_x,
            pos_var_y,
            self.processing_latency_ms / 1000.0,
        ], dtype=np.float64)

    @property
    def is_tracked(self) -> bool:
        return self.track_state in ("TRACKING", "ACQUIRING", "REACQUIRING")

    @property
    def failure_risk(self) -> float:
        """Simple heuristic failure risk score (0..1)."""
        risk = 0.0
        if not self.has_detection:
            risk += 0.4
        if self.detection_age_s > 0.5:
            risk += 0.3
        if self.fov_margin_x < 0.1 or self.fov_margin_y < 0.1:
            risk += 0.2
        if self.residual_magnitude > 50.0:
            risk += 0.1
        return min(risk, 1.0)


class RuntimeFeatureExtractor:
    """Extracts observable features from pipeline state.

    Maintains history buffer for temporal features.
    Never accesses GT, SimulationEngine, or any internal state.
    """

    def __init__(
        self,
        image_width: int = 640,
        image_height: int = 480,
        max_history: int = 20,
    ) -> None:
        self._w = image_width
        self._h = image_height
        self._max_history = max_history
        self._position_history: list[tuple[float, float]] = []
        self._velocity_history: list[tuple[float, float]] = []
        self._last_timestamp: float = 0.0
        self._last_estimated: tuple[float, float] | None = None
        self._processing_fps: float = 0.0
        self._processing_latency_ms: float = 0.0
        self._candidate_count: int = 0
        self._roi_radius_px: float = 0.0

    def update_pipeline_counters(
        self,
        processing_fps: float = 0.0,
        processing_latency_ms: float = 0.0,
        candidate_count: int = 0,
        roi_radius_px: float = 0.0,
    ) -> None:
        """Update pipeline-level counters (called each frame)."""
        self._processing_fps = processing_fps
        self._processing_latency_ms = processing_latency_ms
        self._candidate_count = candidate_count
        self._roi_radius_px = roi_radius_px

    def update_image_dimensions(self, width: int, height: int) -> None:
        self._w = width
        self._h = height

    def extract(
        self,
        state: TrackingState,
        timestamp_s: float,
        dt: float,
    ) -> ObservableFeatures:
        """Extract observable features from tracking state.

        Args:
            state: tracker output state (no GT)
            timestamp_s: current timestamp
            dt: time since last frame

        Returns:
            ObservableFeatures with all runtime-accessible quantities.
        """
        # FOV margins: how far from image edge (normalized 0..1)
        center_x = self._w / 2.0
        center_y = self._h / 2.0
        half_w = self._w / 2.0
        half_h = self._h / 2.0

        dist_x = abs(state.estimated_x - center_x)
        dist_y = abs(state.estimated_y - center_y)
        fov_margin_x = max(0.0, 1.0 - dist_x / half_w) if half_w > 0 else 0.5
        fov_margin_y = max(0.0, 1.0 - dist_y / half_h) if half_h > 0 else 0.5

        # Detection residual
        residual_x = state.residual_x if state.has_detection else 0.0
        residual_y = state.residual_y if state.has_detection else 0.0
        residual_mag = float(np.sqrt(residual_x**2 + residual_y**2))

        # Track state string
        state_str = state.state.name if hasattr(state.state, "name") else str(state.state)

        # Position / velocity history
        pos = (state.estimated_x, state.estimated_y)
        vel = (state.velocity_x, state.velocity_y)
        self._position_history.append(pos)
        self._velocity_history.append(vel)
        if len(self._position_history) > self._max_history:
            self._position_history.pop(0)
            self._velocity_history.pop(0)

        features = ObservableFeatures(
            estimated_x=state.estimated_x,
            estimated_y=state.estimated_y,
            velocity_x=state.velocity_x,
            velocity_y=state.velocity_y,
            uncertainty_x=max(0.0, state.uncertainty_x),
            uncertainty_y=max(0.0, state.uncertainty_y),
            has_detection=state.has_detection,
            detection_confidence=state.detection_confidence if state.has_detection else 0.0,
            detection_age_s=state.time_since_last_detection_s,
            miss_count=state.consecutive_misses,
            residual_x=residual_x,
            residual_y=residual_y,
            residual_magnitude=residual_mag,
            track_state=state_str,
            consecutive_hits=state.consecutive_detections,
            dt=dt,
            timestamp_s=timestamp_s,
            fov_margin_x=fov_margin_x,
            fov_margin_y=fov_margin_y,
            processing_fps=self._processing_fps,
            processing_latency_ms=self._processing_latency_ms,
            position_history=list(self._position_history),
            velocity_history=list(self._velocity_history),
        )

        self._last_timestamp = timestamp_s
        self._last_estimated = pos

        return features

    def reset(self) -> None:
        """Clear history buffers."""
        self._position_history.clear()
        self._velocity_history.clear()
        self._last_timestamp = 0.0
        self._last_estimated = None
