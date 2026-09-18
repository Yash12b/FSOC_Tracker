"""Acceleration/deceleration trajectory.

Sinusoidal velocity profile — speeds up and slows down periodically.
"""

from __future__ import annotations

import math
from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class AccelDecelTrajectory(Trajectory):
    """Sinusoidal velocity profile — periodic acceleration and deceleration.

    Args:
        x0, y0, z0: Starting position.
        speed: Peak speed (amplitude of velocity oscillation).
        accel_freq_hz: Frequency of acceleration/deceleration cycle.
        direction_x, direction_y, direction_z: Direction vector (normalized internally).
    """

    def __init__(
        self,
        x0: float = 1000.0, y0: float = 1000.0, z0: float = 500.0,
        speed: float = 100.0,
        accel_freq_hz: float = 0.2,
        direction_x: float = 1.0, direction_y: float = 0.0, direction_z: float = 0.0,
    ) -> None:
        self._x0, self._y0, self._z0 = x0, y0, z0
        self._speed = speed
        self._freq = accel_freq_hz
        # Normalize direction
        mag = math.sqrt(direction_x**2 + direction_y**2 + direction_z**2)
        if mag < 1e-10:
            mag = 1.0
        self._dx = direction_x / mag
        self._dy = direction_y / mag
        self._dz = direction_z / mag

    def position(self, t: float) -> tuple[float, float, float]:
        # Integrate sinusoidal velocity: v(t) = speed * sin(2*pi*freq*t)
        # pos(t) = x0 + speed/(2*pi*freq) * (1 - cos(2*pi*freq*t))
        omega = 2.0 * math.pi * self._freq
        if self._freq < 1e-10:
            return (self._x0 + self._speed * self._dx * t,
                    self._y0 + self._speed * self._dy * t,
                    self._z0 + self._speed * self._dz * t)
        disp = self._speed / omega * (1.0 - math.cos(omega * t))
        return (self._x0 + self._dx * disp,
                self._y0 + self._dy * disp,
                self._z0 + self._dz * disp)

    def velocity(self, t: float) -> tuple[float, float, float]:
        omega = 2.0 * math.pi * self._freq
        v = self._speed * math.sin(omega * t)
        return (self._dx * v, self._dy * v, self._dz * v)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        omega = 2.0 * math.pi * self._freq
        a = self._speed * omega * math.cos(omega * t)
        return (self._dx * a, self._dy * a, self._dz * a)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "accel_decel",
            "x0": self._x0, "y0": self._y0, "z0": self._z0,
            "speed": self._speed, "accel_freq_hz": self._freq,
            "direction_x": self._dx, "direction_y": self._dy, "direction_z": self._dz,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AccelDecelTrajectory:
        return cls(
            x0=d.get("x0", 1000.0), y0=d.get("y0", 1000.0), z0=d.get("z0", 500.0),
            speed=d.get("speed", 100.0), accel_freq_hz=d.get("accel_freq_hz", 0.2),
            direction_x=d.get("direction_x", 1.0),
            direction_y=d.get("direction_y", 0.0),
            direction_z=d.get("direction_z", 0.0),
        )
