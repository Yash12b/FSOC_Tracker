"""Deterministic random trajectory.

Uses seeded RNG to generate smooth random waypoints and interpolate
between them.  The same seed always produces the same trajectory.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from fsoc_tracker.simulation.trajectory.base import Trajectory


def _smooth_interpolate(
    points: list[tuple[float, float, float]],
    speeds: list[float],
    t: float,
    segment_duration: float,
) -> tuple[float, float, float]:
    """Smoothly interpolate through waypoints using cosine blending.

    Args:
        points: List of (x, y, z) waypoints.
        speeds: List of speeds between consecutive waypoints.
        t: Current time.
        segment_duration: Time per segment.

    Returns:
        Interpolated (x, y, z) position.
    """
    if len(points) < 2:
        return points[0] if points else (0.0, 0.0, 0.0)

    n_segments = len(points) - 1
    total_time = n_segments * segment_duration

    if t <= 0:
        return points[0]
    if t >= total_time:
        return points[-1]

    seg_idx = int(t / segment_duration)
    seg_idx = min(seg_idx, n_segments - 1)

    local_t = (t - seg_idx * segment_duration) / segment_duration
    local_t = max(0.0, min(1.0, local_t))

    # Cosine interpolation for smoothness
    s = 0.5 * (1.0 - math.cos(math.pi * local_t))

    p0 = points[seg_idx]
    p1 = points[seg_idx + 1]

    return (
        p0[0] + s * (p1[0] - p0[0]),
        p0[1] + s * (p1[1] - p0[1]),
        p0[2] + s * (p1[2] - p0[2]),
    )


class RandomTrajectory(Trajectory):
    """Deterministic random trajectory via seeded waypoint generation.

    Generates random waypoints using a seeded RNG, then smoothly
    interpolates between them.  The same seed always produces the
    same trajectory.

    Args:
        x0, y0, z0: Starting position.
        num_waypoints: Number of waypoints to generate.
        segment_duration: Seconds per segment between waypoints.
        max_step: Maximum distance from one waypoint to the next.
        x_min, x_max: Bounds for X coordinate.
        y_min, y_max: Bounds for Y coordinate.
        z_min, z_max: Bounds for Z coordinate.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        x0: float = 1000.0,
        y0: float = 1000.0,
        z0: float = 50.0,
        num_waypoints: int = 20,
        segment_duration: float = 2.0,
        max_step: float = 300.0,
        x_min: float = 0.0,
        x_max: float = 2000.0,
        y_min: float = 0.0,
        y_max: float = 2000.0,
        z_min: float = 0.0,
        z_max: float = 100.0,
        seed: int = 42,
    ) -> None:
        self._x0 = x0
        self._y0 = y0
        self._z0 = z0
        self._num_waypoints = num_waypoints
        self._segment_duration = segment_duration
        self._max_step = max_step
        self._bounds = (x_min, x_max, y_min, y_max, z_min, z_max)
        self._seed = seed
        self._waypoints: list[tuple[float, float, float]] = []
        self._speeds: list[float] = []
        self._generate_waypoints()

    def _generate_waypoints(self) -> None:
        rng = np.random.default_rng(self._seed)
        x_min, x_max, y_min, y_max, z_min, z_max = self._bounds

        self._waypoints = [(self._x0, self._y0, self._z0)]
        cx, cy, cz = self._x0, self._y0, self._z0

        for _ in range(self._num_waypoints - 1):
            # Generate random offset, bounded by max_step
            dx = rng.uniform(-self._max_step, self._max_step)
            dy = rng.uniform(-self._max_step, self._max_step)
            dz = rng.uniform(-self._max_step * 0.1, self._max_step * 0.1)

            cx = max(x_min, min(x_max, cx + dx))
            cy = max(y_min, min(y_max, cy + dy))
            cz = max(z_min, min(z_max, cz + dz))

            self._waypoints.append((cx, cy, cz))

        # Compute speeds between consecutive waypoints
        self._speeds = []
        for i in range(len(self._waypoints) - 1):
            p0 = self._waypoints[i]
            p1 = self._waypoints[i + 1]
            dist = math.sqrt(
                (p1[0] - p0[0]) ** 2
                + (p1[1] - p0[1]) ** 2
                + (p1[2] - p0[2]) ** 2
            )
            self._speeds.append(dist / self._segment_duration if self._segment_duration > 0 else 0.0)

    def reset(self) -> None:
        self._generate_waypoints()

    def position(self, t: float) -> tuple[float, float, float]:
        return _smooth_interpolate(
            self._waypoints, self._speeds, t, self._segment_duration
        )

    def velocity(self, t: float) -> tuple[float, float, float]:
        # Numerical differentiation for random trajectory
        dt = 1e-4
        p0 = self.position(t - dt)
        p1 = self.position(t + dt)
        return (
            (p1[0] - p0[0]) / (2 * dt),
            (p1[1] - p0[1]) / (2 * dt),
            (p1[2] - p0[2]) / (2 * dt),
        )

    def acceleration(self, t: float) -> tuple[float, float, float]:
        dt = 1e-4
        v0 = self.velocity(t - dt)
        v1 = self.velocity(t + dt)
        return (
            (v1[0] - v0[0]) / (2 * dt),
            (v1[1] - v0[1]) / (2 * dt),
            (v1[2] - v0[2]) / (2 * dt),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "random",
            "x0": self._x0,
            "y0": self._y0,
            "z0": self._z0,
            "num_waypoints": self._num_waypoints,
            "segment_duration": self._segment_duration,
            "max_step": self._max_step,
            "x_min": self._bounds[0],
            "x_max": self._bounds[1],
            "y_min": self._bounds[2],
            "y_max": self._bounds[3],
            "z_min": self._bounds[4],
            "z_max": self._bounds[5],
            "seed": self._seed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RandomTrajectory:
        return cls(
            x0=d.get("x0", 1000.0),
            y0=d.get("y0", 1000.0),
            z0=d.get("z0", 50.0),
            num_waypoints=d.get("num_waypoints", 20),
            segment_duration=d.get("segment_duration", 2.0),
            max_step=d.get("max_step", 300.0),
            x_min=d.get("x_min", 0.0),
            x_max=d.get("x_max", 2000.0),
            y_min=d.get("y_min", 0.0),
            y_max=d.get("y_max", 2000.0),
            z_min=d.get("z_min", 0.0),
            z_max=d.get("z_max", 100.0),
            seed=d.get("seed", 42),
        )
