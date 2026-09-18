"""Figure-of-8 (Lissajous) trajectory.

    x(t) = cx + Ax * sin(omega * t + phase_x)
    y(t) = cy + Ay * sin(2 * omega * t + phase_y)

The 2:1 frequency ratio produces a clean figure-8 pattern.
"""

from __future__ import annotations

import math
from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class FigureEightTrajectory(Trajectory):
    """Figure-of-8 / Lissajous trajectory in 3D.

    The figure-8 is produced by a 2:1 frequency ratio between Y and X.

    Args:
        cx, cy, cz: Center of the figure-8.
        amplitude_x: Half-width of the figure-8.
        amplitude_y: Half-height of the figure-8.
        angular_speed_rad_s: Base angular frequency.
        phase_x_rad: Phase offset for X axis.
        phase_y_rad: Phase offset for Y axis.
        duration: If set, trajectory ends after this many seconds.
    """

    def __init__(
        self,
        cx: float = 1000.0,
        cy: float = 1000.0,
        cz: float = 50.0,
        amplitude_x: float = 150.0,
        amplitude_y: float = 80.0,
        angular_speed_rad_s: float = math.pi / 4.0,
        phase_x_rad: float = 0.0,
        phase_y_rad: float = 0.0,
        duration: float | None = None,
    ) -> None:
        self._cx = cx
        self._cy = cy
        self._cz = cz
        self._ax = amplitude_x
        self._ay = amplitude_y
        self._omega = angular_speed_rad_s
        self._phase_x = phase_x_rad
        self._phase_y = phase_y_rad
        self._duration = duration

    def position(self, t: float) -> tuple[float, float, float]:
        x = self._cx + self._ax * math.sin(self._omega * t + self._phase_x)
        y = self._cy + self._ay * math.sin(2.0 * self._omega * t + self._phase_y)
        return (x, y, self._cz)

    def velocity(self, t: float) -> tuple[float, float, float]:
        vx = self._ax * self._omega * math.cos(self._omega * t + self._phase_x)
        vy = (
            self._ay
            * 2.0
            * self._omega
            * math.cos(2.0 * self._omega * t + self._phase_y)
        )
        return (vx, vy, 0.0)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        ax = -self._ax * self._omega**2 * math.sin(self._omega * t + self._phase_x)
        ay = (
            -self._ay
            * (2.0 * self._omega) ** 2
            * math.sin(2.0 * self._omega * t + self._phase_y)
        )
        return (ax, ay, 0.0)

    @property
    def duration(self) -> float | None:
        return self._duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "figure_8",
            "cx": self._cx,
            "cy": self._cy,
            "cz": self._cz,
            "amplitude_x": self._ax,
            "amplitude_y": self._ay,
            "angular_speed_rad_s": self._omega,
            "phase_x_rad": self._phase_x,
            "phase_y_rad": self._phase_y,
            "duration": self._duration,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FigureEightTrajectory:
        return cls(
            cx=d.get("cx", 1000.0),
            cy=d.get("cy", 1000.0),
            cz=d.get("cz", 50.0),
            amplitude_x=d.get("amplitude_x", 150.0),
            amplitude_y=d.get("amplitude_y", 80.0),
            angular_speed_rad_s=d.get("angular_speed_rad_s", math.pi / 4.0),
            phase_x_rad=d.get("phase_x_rad", 0.0),
            phase_y_rad=d.get("phase_y_rad", 0.0),
            duration=d.get("duration"),
        )
