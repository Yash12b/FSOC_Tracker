"""User-controlled trajectory.

Position is set externally by the user (e.g., via drag in the 3D view).
The trajectory returns the last user-set position.
"""

from __future__ import annotations

from typing import Any

from fsoc_tracker.simulation.trajectory.base import Trajectory


class UserControlledTrajectory(Trajectory):
    """Position is set externally by the user.

    The trajectory holds the last user-set position and returns it
    for all time queries.  Call ``set_position(x, y, z)`` to update.

    Args:
        x0, y0, z0: Initial position.
    """

    def __init__(
        self,
        x0: float = 1000.0, y0: float = 1000.0, z0: float = 500.0,
    ) -> None:
        self._x, self._y, self._z = x0, y0, z0
        self._prev_x, self._prev_y, self._prev_z = x0, y0, z0
        self._vx, self._vy, self._vz = 0.0, 0.0, 0.0
        self._last_t = 0.0

    def set_position(self, x: float, y: float, z: float) -> None:
        """Update the beacon position (called by user interaction)."""
        self._prev_x, self._prev_y, self._prev_z = self._x, self._y, self._z
        self._x, self._y, self._z = x, y, z

    def position(self, t: float) -> tuple[float, float, float]:
        return (self._x, self._y, self._z)

    def velocity(self, t: float) -> tuple[float, float, float]:
        if t > self._last_t and t - self._last_t > 1e-10:
            dt = t - self._last_t
            self._vx = (self._x - self._prev_x) / dt
            self._vy = (self._y - self._prev_y) / dt
            self._vz = (self._z - self._prev_z) / dt
        self._last_t = t
        return (self._vx, self._vy, self._vz)

    def acceleration(self, t: float) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "user_controlled",
            "x0": self._x, "y0": self._y, "z0": self._z,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UserControlledTrajectory:
        return cls(x0=d.get("x0", 1000.0), y0=d.get("y0", 1000.0), z0=d.get("z0", 500.0))
