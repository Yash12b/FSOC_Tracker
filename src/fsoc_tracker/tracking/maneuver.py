"""Maneuver detection for adaptive tracking.

Detects when target motion departs from the constant-velocity model
and classifies motion as SMOOTH, MANEUVERING, or UNPREDICTABLE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto


class MotionClass(Enum):
    SMOOTH = auto()
    MANEUVERING = auto()
    UNPREDICTABLE = auto()


@dataclass
class ManeuverState:
    """Current maneuver classification and diagnostics."""

    motion_class: MotionClass = MotionClass.SMOOTH
    innovation_magnitude: float = 0.0
    innovation_history: list[float] = field(default_factory=list)
    velocity_change_rate: float = 0.0
    acceleration_estimate: float = 0.0
    sustained_maneuver_frames: int = 0

    def to_dict(self) -> dict:
        return {
            "motion_class": self.motion_class.name,
            "innovation_magnitude": round(self.innovation_magnitude, 2),
            "velocity_change_rate": round(self.velocity_change_rate, 3),
            "acceleration_estimate": round(self.acceleration_estimate, 3),
            "sustained_maneuver_frames": self.sustained_maneuver_frames,
        }


@dataclass
class ManeuverConfig:
    """Configuration for maneuver detection."""

    innovation_threshold: float = 15.0
    sustained_maneuver_threshold: int = 3
    velocity_change_threshold: float = 50.0
    acceleration_threshold: float = 100.0
    history_length: int = 10
    unpredictable_innovation_threshold: float = 40.0


class ManeuverDetector:
    """Detects target maneuvering from innovation and velocity history.

    Logic:
    - Track innovation (residual) magnitude over recent frames
    - Estimate velocity change rate
    - When innovations are consistently large -> MANEUVERING
    - When innovations are extreme -> UNPREDICTABLE
    - Otherwise -> SMOOTH
    """

    def __init__(self, config: ManeuverConfig | None = None) -> None:
        self._config = config or ManeuverConfig()
        self._innovation_history: list[float] = []
        self._velocity_history: list[tuple[float, float]] = []
        self._sustained_count: int = 0

    def update(
        self,
        innovation_x: float,
        innovation_y: float,
        velocity_x: float,
        velocity_y: float,
        dt: float,
    ) -> ManeuverState:
        """Update maneuver detection with new frame data.

        Args:
            innovation_x: Measurement residual x (px).
            innovation_y: Measurement residual y (px).
            velocity_x: Current estimated velocity x (px/s).
            velocity_y: Current estimated velocity y (px/s).
            dt: Time step (s).

        Returns:
            ManeuverState with classification.
        """
        innov_mag = math.sqrt(innovation_x ** 2 + innovation_y ** 2)
        self._innovation_history.append(innov_mag)
        if len(self._innovation_history) > self._config.history_length:
            self._innovation_history.pop(0)

        self._velocity_history.append((velocity_x, velocity_y))
        if len(self._velocity_history) > self._config.history_length:
            self._velocity_history.pop(0)

        vel_change = self._compute_velocity_change(dt)
        accel = self._compute_acceleration(dt)

        state = ManeuverState(
            innovation_magnitude=innov_mag,
            innovation_history=list(self._innovation_history),
            velocity_change_rate=vel_change,
            acceleration_estimate=accel,
        )

        state.motion_class = self._classify(state)
        state.sustained_maneuver_frames = self._sustained_count

        return state

    def _compute_velocity_change(self, dt: float) -> float:
        if len(self._velocity_history) < 2 or dt <= 0:
            return 0.0
        v1 = self._velocity_history[-2]
        v2 = self._velocity_history[-1]
        dvx = (v2[0] - v1[0]) / dt
        dvy = (v2[1] - v1[1]) / dt
        return math.sqrt(dvx * dvx + dvy * dvy)

    def _compute_acceleration(self, dt: float) -> float:
        if len(self._velocity_history) < 3 or dt <= 0:
            return 0.0
        v0 = self._velocity_history[-3]
        v1 = self._velocity_history[-2]
        v2 = self._velocity_history[-1]
        a1x = (v1[0] - v0[0]) / dt
        a1y = (v1[1] - v0[1]) / dt
        a2x = (v2[0] - v1[0]) / dt
        a2y = (v2[1] - v1[1]) / dt
        dax = a2x - a1x
        day = a2y - a1y
        return math.sqrt(dax * dax + day * day) / dt

    def _classify(self, state: ManeuverState) -> MotionClass:
        cfg = self._config

        if state.innovation_magnitude > cfg.unpredictable_innovation_threshold:
            self._sustained_count = 0
            return MotionClass.UNPREDICTABLE

        if (
            state.innovation_magnitude > cfg.innovation_threshold
            or state.velocity_change_rate > cfg.velocity_change_threshold
            or state.acceleration_estimate > cfg.acceleration_threshold
        ):
            self._sustained_count += 1
            if self._sustained_count >= cfg.sustained_maneuver_threshold:
                return MotionClass.MANEUVERING
        else:
            self._sustained_count = max(0, self._sustained_count - 1)

        if self._sustained_count > 0:
            return MotionClass.MANEUVERING
        return MotionClass.SMOOTH

    def reset(self) -> None:
        self._innovation_history.clear()
        self._velocity_history.clear()
        self._sustained_count = 0
