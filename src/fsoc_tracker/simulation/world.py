"""Virtual world model for the simulation environment.

The world is a configurable 3D volume in which targets move independently.
The world is independent from any camera renderer -- it is purely
mathematical state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fsoc_tracker.simulation.boundaries import BoundaryMode
from fsoc_tracker.simulation.platform import PlatformState
from fsoc_tracker.simulation.target import WorldTargetState


@dataclass
class WorldConfig:
    """Configuration for the simulation world.

    Default values correspond to SIH26169 requirements:
        - 2000 x 2000 minimum virtual canvas
        - configurable depth
    """

    width: float = 2000.0
    height: float = 2000.0
    depth: float = 2000.0

    x_min: float = 0.0
    y_min: float = 0.0
    z_min: float = 0.0

    boundary_mode: BoundaryMode = BoundaryMode.REFLECT

    random_seed: int = 42

    def __post_init__(self) -> None:
        self.x_max = self.x_min + self.width
        self.y_max = self.y_min + self.height
        self.z_max = self.z_min + self.depth

    @property
    def bounds_x(self) -> tuple[float, float]:
        return (self.x_min, self.x_max)

    @property
    def bounds_y(self) -> tuple[float, float]:
        return (self.y_min, self.y_max)

    @property
    def bounds_z(self) -> tuple[float, float]:
        return (self.z_min, self.z_max)

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "x_min": self.x_min,
            "y_min": self.y_min,
            "z_min": self.z_min,
            "boundary_mode": self.boundary_mode.value,
            "random_seed": self.random_seed,
        }


@dataclass
class WorldState:
    """Complete state of the simulation world at a point in time.

    Contains the world configuration, all target states, platform state,
    and the current simulation time.  This is the authoritative snapshot
    that the camera renderer and tracker will consume.
    """

    config: WorldConfig = field(default_factory=WorldConfig)
    targets: list[WorldTargetState] = field(default_factory=list)
    platform: PlatformState = field(default_factory=PlatformState)
    simulation_time_s: float = 0.0
    step_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_target(self, target_id: int) -> WorldTargetState | None:
        """Return the target with the given ID, or None."""
        for t in self.targets:
            if t.target_id == target_id:
                return t
        return None

    def get_active_targets(self) -> list[WorldTargetState]:
        """Return only active targets."""
        return [t for t in self.targets if t.active]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "config": self.config.to_dict(),
            "targets": [t.to_dict() for t in self.targets],
            "platform": self.platform.to_dict(),
            "simulation_time_s": self.simulation_time_s,
            "step_count": self.step_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorldState:
        """Deserialize from a dictionary."""
        from fsoc_tracker.simulation.boundaries import BoundaryMode

        cfg_dict = d.get("config", {})
        boundary_str = cfg_dict.pop("boundary_mode", "reflect")
        cfg_dict["boundary_mode"] = BoundaryMode(boundary_str)
        config = WorldConfig(**cfg_dict)

        targets = [WorldTargetState.from_dict(t) for t in d.get("targets", [])]
        platform = PlatformState.from_dict(d.get("platform", {}))

        return cls(
            config=config,
            targets=targets,
            platform=platform,
            simulation_time_s=d.get("simulation_time_s", 0.0),
            step_count=d.get("step_count", 0),
            metadata=d.get("metadata", {}),
        )
