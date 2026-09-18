"""Boundary handling for the simulation world.

Targets that reach the world boundary can be handled in several ways:
    - REFLECT: bounce off the boundary (velocity reversed)
    - CLAMP: stop at the boundary (position clamped)
    - WRAP: wrap around to the opposite side
"""

from __future__ import annotations

from enum import Enum


class BoundaryMode(str, Enum):
    """How targets behave when reaching world boundaries."""

    REFLECT = "reflect"
    CLAMP = "clamp"
    WRAP = "wrap"


def apply_boundary(
    pos: float,
    vel: float,
    lo: float,
    hi: float,
    mode: BoundaryMode,
) -> tuple[float, float]:
    """Apply boundary handling to a single axis.

    Args:
        pos: Current position on this axis.
        vel: Current velocity on this axis.
        lo: Lower boundary.
        hi: Upper boundary.
        mode: Boundary handling mode.

    Returns:
        New (position, velocity) after boundary handling.

    Raises:
        ValueError: If lo >= hi.
    """
    if lo >= hi:
        raise ValueError(f"Invalid bounds: lo={lo} must be < hi={hi}")

    if mode == BoundaryMode.CLAMP:
        if pos < lo:
            return lo, 0.0
        if pos > hi:
            return hi, 0.0
        return pos, vel

    if mode == BoundaryMode.WRAP:
        span = hi - lo
        new_pos = (pos - lo) % span + lo
        return new_pos, vel

    # REFLECT (default)
    if pos < lo:
        new_pos = lo + (lo - pos)
        return new_pos, -vel
    if pos > hi:
        new_pos = hi - (pos - hi)
        return new_pos, -vel
    return pos, vel


def apply_boundary_3d(
    x: float,
    y: float,
    z: float,
    vx: float,
    vy: float,
    vz: float,
    x_lo: float,
    x_hi: float,
    y_lo: float,
    y_hi: float,
    z_lo: float,
    z_hi: float,
    mode: BoundaryMode,
) -> tuple[float, float, float, float, float, float]:
    """Apply boundary handling to all three axes.

    Returns:
        New (x, y, z, vx, vy, vz) after boundary handling.
    """
    x, vx = apply_boundary(x, vx, x_lo, x_hi, mode)
    y, vy = apply_boundary(y, vy, y_lo, y_hi, mode)
    z, vz = apply_boundary(z, vz, z_lo, z_hi, mode)
    return x, y, z, vx, vy, vz
