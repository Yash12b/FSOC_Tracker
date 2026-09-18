"""Platform state for the simulation environment.

The platform represents the physical mounting of the FSOC terminal.
Initially stationary; the disturbance engine (Stage 9) will modify this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlatformState:
    """State of the FSOC terminal platform in world coordinates.

    Represents position, orientation, and angular velocity of the
    platform that carries the virtual camera.  Initially stationary.

    Attributes:
        x, y, z: Position in world coordinates (meters).
        roll_deg, pitch_deg, yaw_deg: Orientation in degrees.
        vx, vy, vz: Linear velocity (m/s).
        roll_rate_deg_s, pitch_rate_deg_s, yaw_rate_deg_s: Angular velocity (deg/s).
        timestamp_s: Current simulation time.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0

    vx: float = 0.0
    vy: float = 0.0
    vz: float = 0.0

    roll_rate_deg_s: float = 0.0
    pitch_rate_deg_s: float = 0.0
    yaw_rate_deg_s: float = 0.0

    timestamp_s: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "roll_deg": self.roll_deg,
            "pitch_deg": self.pitch_deg,
            "yaw_deg": self.yaw_deg,
            "vx": self.vx,
            "vy": self.vy,
            "vz": self.vz,
            "roll_rate_deg_s": self.roll_rate_deg_s,
            "pitch_rate_deg_s": self.pitch_rate_deg_s,
            "yaw_rate_deg_s": self.yaw_rate_deg_s,
            "timestamp_s": self.timestamp_s,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PlatformState:
        """Deserialize from a dictionary."""
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
