"""Sinusoidal trajectory.

    x(t) = cx + amplitude_x * sin(omega_x * t + phase_x)
    y(t) = cy + amplitude_y * sin(omega_y * t + phase_y)

Independent sinusoidal motion on each axis.
"""

from __future__ import annotations

import math
from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class SinusoidalTrajectory(Trajectory):
    """Independent sinusoidal motion on each axis.

    Args:
        cx, cy, cz: Center position.
        amplitude_x, amplitude_y, amplitude_z: Amplitude per axis.
        freq_x, freq_y, freq_z: Frequency in Hz per axis.
        phase_x_rad, phase_y_rad, phase_z_rad: Phase offset per axis.
        duration: Total duration in seconds.
    """

    def __init__(
        self,
        cx: float = 1000.0,
        cy: float = 1000.0,
        cz: float = 50.0,
        amplitude_x: float = 100.0,
        amplitude_y: float = 80.0,
        amplitude_z: float = 0.0,
        freq_x: float = 0.1,
        freq_y: float = 0.15,
        freq_z: float = 0.0,
        phase_x_rad: float = 0.0,
        phase_y_rad: float = 0.0,
        phase_z_rad: float = 0.0,
        duration: float | None = None,
    ) -> None:
        self._cx = cx
        self._cy = cy
        self._cz = cz
        self._ax = amplitude_x
        self._ay = amplitude_y
        self._az = amplitude_z
        self._fx = freq_x
        self._fy = freq_y
        self._fz = freq_z
        self._px = phase_x_rad
        self._py = phase_y_rad
        self._pz = phase_z_rad
        self._duration = duration

    def position(self, t: float) -> tuple[float, float, float]:
        return (
            self._cx + self._ax * math.sin(2 * math.pi * self._fx * t + self._px),
            self._cy + self._ay * math.sin(2 * math.pi * self._fy * t + self._py),
            self._cz + self._az * math.sin(2 * math.pi * self._fz * t + self._pz),
        )

    def velocity(self, t: float) -> tuple[float, float, float]:
        return (
            self._ax * 2 * math.pi * self._fx * math.cos(2 * math.pi * self._fx * t + self._px),
            self._ay * 2 * math.pi * self._fy * math.cos(2 * math.pi * self._fy * t + self._py),
            self._az * 2 * math.pi * self._fz * math.cos(2 * math.pi * self._fz * t + self._pz),
        )

    def acceleration(self, t: float) -> tuple[float, float, float]:
        return (
            -self._ax * (2 * math.pi * self._fx) ** 2 * math.sin(2 * math.pi * self._fx * t + self._px),
            -self._ay * (2 * math.pi * self._fy) ** 2 * math.sin(2 * math.pi * self._fy * t + self._py),
            -self._az * (2 * math.pi * self._fz) ** 2 * math.sin(2 * math.pi * self._fz * t + self._pz),
        )

    @property
    def duration(self) -> float | None:
        return self._duration

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "sinusoidal",
            "cx": self._cx,
            "cy": self._cy,
            "cz": self._cz,
            "amplitude_x": self._ax,
            "amplitude_y": self._ay,
            "amplitude_z": self._az,
            "freq_x": self._fx,
            "freq_y": self._fy,
            "freq_z": self._fz,
            "phase_x_rad": self._px,
            "phase_y_rad": self._py,
            "phase_z_rad": self._pz,
            "duration": self._duration,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SinusoidalTrajectory:
        return cls(**{k: v for k, v in d.items() if k != "type"})
