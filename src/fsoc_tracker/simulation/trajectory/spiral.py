"""Spiral trajectory.

    x(t) = cx + (r0 + growth*t) * cos(omega*t)
    y(t) = cy + (r0 + growth*t) * sin(omega*t)

An expanding or contracting spiral.
"""

from __future__ import annotations

import math
from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class SpiralTrajectory(Trajectory):
    """Expanding/contracting spiral in 3D.

    Args:
        cx, cy, cz: Center of the spiral.
        radius_start: Initial radius.
        radius_growth: Rate of radius change per second.
        angular_speed_rad_s: Angular speed in radians/second.
        plane: Plane of rotation ("xy", "xz", or "yz").
        duration: Total duration in seconds.
    """

    def __init__(
        self,
        cx: float = 1000.0,
        cy: float = 1000.0,
        cz: float = 50.0,
        radius_start: float = 50.0,
        radius_growth: float = 10.0,
        angular_speed_rad_s: float = math.pi / 3.0,
        plane: str = "xy",
        duration: float = 20.0,
    ) -> None:
        self._cx = cx
        self._cy = cy
        self._cz = cz
        self._r0 = radius_start
        self._growth = radius_growth
        self._omega = angular_speed_rad_s
        self._plane = plane
        self._duration = duration

    def _radius(self, t: float) -> float:
        return max(0.0, self._r0 + self._growth * t)

    def position(self, t: float) -> tuple[float, float, float]:
        theta = self._omega * t
        r = self._radius(t)
        cos_t = r * math.cos(theta)
        sin_t = r * math.sin(theta)
        if self._plane == "xz":
            return (self._cx + cos_t, self._cy, self._cz + sin_t)
        if self._plane == "yz":
            return (self._cx, self._cy + cos_t, self._cz + sin_t)
        return (self._cx + cos_t, self._cy + sin_t, self._cz)

    def velocity(self, t: float) -> tuple[float, float, float]:
        theta = self._omega * t
        r = self._radius(t)
        dr = self._growth
        vx = dr * math.cos(theta) - r * self._omega * math.sin(theta)
        vy = dr * math.sin(theta) + r * self._omega * math.cos(theta)
        if self._plane == "xz":
            return (vx, 0.0, vy)
        if self._plane == "yz":
            return (0.0, vx, vy)
        return (vx, vy, 0.0)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        dt = 1e-4
        v0 = self.velocity(t - dt)
        v1 = self.velocity(t + dt)
        return (
            (v1[0] - v0[0]) / (2 * dt),
            (v1[1] - v0[1]) / (2 * dt),
            (v1[2] - v0[2]) / (2 * dt),
        )

    @property
    def duration(self) -> float | None:
        return self._duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "spiral",
            "cx": self._cx,
            "cy": self._cy,
            "cz": self._cz,
            "radius_start": self._r0,
            "radius_growth": self._growth,
            "angular_speed_rad_s": self._omega,
            "plane": self._plane,
            "duration": self._duration,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpiralTrajectory:
        return cls(**{k: v for k, v in d.items() if k != "type"})
