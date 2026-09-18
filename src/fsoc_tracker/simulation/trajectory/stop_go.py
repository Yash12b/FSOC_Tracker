"""Stop-and-go trajectory.

Alternates between moving and stationary phases.
"""

from __future__ import annotations

from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class StopGoTrajectory(Trajectory):
    """Alternates between moving and stationary phases.

    Args:
        x0, y0, z0: Starting position.
        vx, vy, vz: Velocity during moving phases.
        move_duration: Seconds of movement per cycle.
        stop_duration: Seconds of stop per cycle.
    """

    def __init__(
        self,
        x0: float = 1000.0, y0: float = 1000.0, z0: float = 500.0,
        vx: float = 100.0, vy: float = 0.0, vz: float = 0.0,
        move_duration: float = 2.0, stop_duration: float = 1.0,
    ) -> None:
        self._x0, self._y0, self._z0 = x0, y0, z0
        self._vx, self._vy, self._vz = vx, vy, vz
        self._move_dur = move_duration
        self._stop_dur = stop_duration
        self._cycle = move_duration + stop_duration

    def _is_moving(self, t: float) -> bool:
        cycle_pos = t % self._cycle
        return cycle_pos < self._move_dur

    def _accumulated_offset(self, t: float) -> tuple[float, float, float]:
        full_cycles = int(t / self._cycle)
        remainder = t - full_cycles * self._cycle
        move_t = min(remainder, self._move_dur)
        total_move = full_cycles * self._move_dur + move_t
        return (self._vx * total_move, self._vy * total_move, self._vz * total_move)

    def position(self, t: float) -> tuple[float, float, float]:
        ox, oy, oz = self._accumulated_offset(t)
        return (self._x0 + ox, self._y0 + oy, self._z0 + oz)

    def velocity(self, t: float) -> tuple[float, float, float]:
        if self._is_moving(t):
            return (self._vx, self._vy, self._vz)
        return (0.0, 0.0, 0.0)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "stop_go",
            "x0": self._x0, "y0": self._y0, "z0": self._z0,
            "vx": self._vx, "vy": self._vy, "vz": self._vz,
            "move_duration": self._move_dur, "stop_duration": self._stop_dur,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StopGoTrajectory:
        return cls(
            x0=d.get("x0", 1000.0), y0=d.get("y0", 1000.0), z0=d.get("z0", 500.0),
            vx=d.get("vx", 100.0), vy=d.get("vy", 0.0), vz=d.get("vz", 0.0),
            move_duration=d.get("move_duration", 2.0), stop_duration=d.get("stop_duration", 1.0),
        )
