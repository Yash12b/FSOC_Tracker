"""Sudden reversal trajectory.

Moves in one direction, then abruptly reverses at configurable intervals.
"""

from __future__ import annotations

from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class SuddenReversalTrajectory(Trajectory):
    """Moves in one direction, then abruptly reverses.

    Args:
        x0, y0, z0: Starting position.
        vx, vy, vz: Initial velocity.
        reversal_interval_s: Seconds between reversals.
    """

    def __init__(
        self,
        x0: float = 1000.0, y0: float = 1000.0, z0: float = 500.0,
        vx: float = 100.0, vy: float = 0.0, vz: float = 0.0,
        reversal_interval_s: float = 3.0,
    ) -> None:
        self._x0, self._y0, self._z0 = x0, y0, z0
        self._vx0, self._vy0, self._vz0 = vx, vy, vz
        self._interval = reversal_interval_s

    def _sign(self, t: float) -> float:
        n = int(t / self._interval)
        return 1.0 if n % 2 == 0 else -1.0

    def position(self, t: float) -> tuple[float, float, float]:
        # Analytical integration of piecewise constant velocity
        sign = self._sign(t)
        n = int(t / self._interval)
        partial = t - n * self._interval

        # Distance covered in complete intervals
        n * self._interval
        # Each pair of intervals cancels out, so net displacement per pair = 0
        # Odd interval means one extra forward interval
        net_time = self._interval if n % 2 == 1 else 0.0
        # Add partial interval with current sign
        net_time += partial * sign

        return (
            self._x0 + self._vx0 * net_time,
            self._y0 + self._vy0 * net_time,
            self._z0 + self._vz0 * net_time,
        )

    def velocity(self, t: float) -> tuple[float, float, float]:
        sign = self._sign(t)
        return (self._vx0 * sign, self._vy0 * sign, self._vz0 * sign)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "sudden_reversal",
            "x0": self._x0, "y0": self._y0, "z0": self._z0,
            "vx": self._vx0, "vy": self._vy0, "vz": self._vz0,
            "reversal_interval_s": self._interval,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SuddenReversalTrajectory:
        return cls(
            x0=d.get("x0", 1000.0), y0=d.get("y0", 1000.0), z0=d.get("z0", 500.0),
            vx=d.get("vx", 100.0), vy=d.get("vy", 0.0), vz=d.get("vz", 0.0),
            reversal_interval_s=d.get("reversal_interval_s", 3.0),
        )
