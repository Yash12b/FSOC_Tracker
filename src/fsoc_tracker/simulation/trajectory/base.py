"""Abstract trajectory interface.

All trajectories implement a common interface for position, velocity,
and acceleration as continuous functions of time.  This ensures
FPS-independent motion: position is evaluated at simulation time,
not per-frame increments.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Trajectory(ABC):
    """Abstract base class for all trajectory types.

    A trajectory is a parametric curve in 3D space:
        position(t) -> (x, y, z)
        velocity(t) -> (vx, vy, vz)
        acceleration(t) -> (ax, ay, az)

    The trajectory is fully determined by its configuration and
    the simulation time.  No frame-rate dependence exists.
    """

    @abstractmethod
    def position(self, t: float) -> tuple[float, float, float]:
        """Return (x, y, z) at time *t*."""

    @abstractmethod
    def velocity(self, t: float) -> tuple[float, float, float]:
        """Return (vx, vy, vz) at time *t*."""

    @abstractmethod
    def acceleration(self, t: float) -> tuple[float, float, float]:
        """Return (ax, ay, az) at time *t*."""

    def reset(self) -> None:
        """Reset internal state if any (default: no-op)."""

    @property
    def duration(self) -> float | None:
        """Total duration of the trajectory, or None if infinite."""
        return None

    def is_finished(self, t: float) -> bool:
        """Return True if the trajectory has ended at time *t*."""
        d = self.duration
        if d is None:
            return False
        return t >= d

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize trajectory configuration to a dictionary."""

    @classmethod
    @abstractmethod
    def from_dict(cls, d: dict[str, Any]) -> Trajectory:
        """Deserialize a trajectory from a dictionary."""
