"""Simulation configuration extensions.

Adds simulation-specific config that extends the base ``config.settings``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorldSimConfig(BaseModel):
    """Detailed world simulation configuration."""

    width: float = Field(default=2000.0, gt=0)
    height: float = Field(default=2000.0, gt=0)
    depth: float = Field(default=100.0, gt=0)
    boundary_mode: str = "reflect"
    random_seed: int = 42


class TargetSimConfig(BaseModel):
    """Detailed target simulation configuration."""

    target_id: int = 0
    shape: str = "square"
    width: float = Field(default=0.01, gt=0)
    height: float = Field(default=0.01, gt=0)
    brightness: float = Field(default=1.0, gt=0)
    x0: float = 1000.0
    y0: float = 1000.0
    z0: float = 50.0
    trajectory_type: str = "straight_line"
    trajectory_params: dict = Field(default_factory=dict)


class EngineConfig(BaseModel):
    """Engine-level settings."""

    max_step_dt: float = Field(default=0.1, gt=0)
    max_simulation_time_s: float = Field(default=300.0, gt=0)
