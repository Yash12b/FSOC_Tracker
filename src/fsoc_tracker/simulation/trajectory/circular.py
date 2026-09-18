"""Circular trajectory.

    x(t) = cx + r * cos(omega * t + phi)
    y(t) = cy + r * sin(omega * t + phi)

Angular speed omega determines how fast the target orbits.
"""

from __future__ import annotations

import math
from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class CircularTrajectory(Trajectory):
    """Circular motion in 3D (default: XY plane).

    Args:
        cx, cy, cz: Center of the circle.
        radius: Radius of the circle.
        angular_speed_rad_s: Angular speed in radians/second.
        phase_rad: Initial phase offset in radians.
        plane: Plane of rotation ("xy", "xz", or "yz").
        duration: If set, trajectory ends after this many seconds.
    """

    def __init__(
        self,
        cx: float = 1000.0,
        cy: float = 1000.0,
        cz: float = 50.0,
        radius: float = 200.0,
        angular_speed_rad_s: float = math.pi / 5.0,
        phase_rad: float = 0.0,
        plane: str = "xy",
        duration: float | None = None,
    ) -> None:
        self._cx = cx
        self._cy = cy
        self._cz = cz
        self._radius = radius
        self._omega = angular_speed_rad_s
        self._phase = phase_rad
        self._plane = plane
        self._duration = duration

    def position(self, t: float) -> tuple[float, float, float]:
        theta = self._omega * t + self._phase
        cos_t = self._radius * math.cos(theta)
        sin_t = self._radius * math.sin(theta)

        if self._plane == "xz":
            return (self._cx + cos_t, self._cy, self._cz + sin_t)
        if self._plane == "yz":
            return (self._cx, self._cy + cos_t, self._cz + sin_t)
        # Default: XY plane
        return (self._cx + cos_t, self._cy + sin_t, self._cz)

    def velocity(self, t: float) -> tuple[float, float, float]:
        theta = self._omega * t + self._phase
        v_tangential = self._radius * self._omega
        sin_t = -v_tangential * math.sin(theta)
        cos_t = v_tangential * math.cos(theta)

        if self._plane == "xz":
            return (sin_t, 0.0, cos_t)
        if self._plane == "yz":
            return (0.0, sin_t, cos_t)
        return (sin_t, cos_t, 0.0)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        theta = self._omega * t + self._phase
        a_centripetal = self._radius * self._omega**2
        cos_t = -a_centripetal * math.cos(theta)
        sin_t = -a_centripetal * math.sin(theta)

        if self._plane == "xz":
            return (cos_t, 0.0, sin_t)
        if self._plane == "yz":
            return (0.0, cos_t, sin_t)
        return (cos_t, sin_t, 0.0)

    @property
    def duration(self) -> float | None:
        return self._duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "circular",
            "cx": self._cx,
            "cy": self._cy,
            "cz": self._cz,
            "radius": self._radius,
            "angular_speed_rad_s": self._omega,
            "phase_rad": self._phase,
            "plane": self._plane,
            "duration": self._duration,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CircularTrajectory:
        return cls(
            cx=d.get("cx", 1000.0),
            cy=d.get("cy", 1000.0),
            cz=d.get("cz", 50.0),
            radius=d.get("radius", 200.0),
            angular_speed_rad_s=d.get("angular_speed_rad_s", math.pi / 5.0),
            phase_rad=d.get("phase_rad", 0.0),
            plane=d.get("plane", "xy"),
            duration=d.get("duration"),
        )
