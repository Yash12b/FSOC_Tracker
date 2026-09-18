"""Straight-line trajectory.

    p(t) = p0 + v * t

Velocity is constant.  Acceleration is zero.
"""

from __future__ import annotations

import math
from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class StraightLineTrajectory(Trajectory):
    """Constant-velocity straight-line motion in 3D.

    Args:
        x0, y0, z0: Starting position.
        vx, vy, vz: Constant velocity components.
        duration: If set, trajectory ends after this many seconds.
    """

    def __init__(
        self,
        x0: float = 0.0,
        y0: float = 0.0,
        z0: float = 0.0,
        vx: float = 10.0,
        vy: float = 0.0,
        vz: float = 0.0,
        duration: float | None = None,
    ) -> None:
        self._x0 = x0
        self._y0 = y0
        self._z0 = z0
        self._vx = vx
        self._vy = vy
        self._vz = vz
        self._duration = duration

    def position(self, t: float) -> tuple[float, float, float]:
        return (
            self._x0 + self._vx * t,
            self._y0 + self._vy * t,
            self._z0 + self._vz * t,
        )

    def velocity(self, t: float) -> tuple[float, float, float]:
        return (self._vx, self._vy, self._vz)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    @property
    def duration(self) -> float | None:
        return self._duration

    def speed(self) -> float:
        """Constant speed magnitude."""
        return math.sqrt(self._vx**2 + self._vy**2 + self._vz**2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "straight_line",
            "x0": self._x0,
            "y0": self._y0,
            "z0": self._z0,
            "vx": self._vx,
            "vy": self._vy,
            "vz": self._vz,
            "duration": self._duration,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StraightLineTrajectory:
        return cls(
            x0=d.get("x0", 0.0),
            y0=d.get("y0", 0.0),
            z0=d.get("z0", 0.0),
            vx=d.get("vx", 10.0),
            vy=d.get("vy", 0.0),
            vz=d.get("vz", 0.0),
            duration=d.get("duration"),
        )
