"""Terminal state representing FSOC tracking terminals.

Terminal A is the local tracking system.
Terminal B is the remote beacon/terminal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass
class TerminalState:
    """Represents a free space optical communication terminal."""
    terminal_id: str = "TERMINAL_A"
    active: bool = True
    
    # 3D Position
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    
    # Orientation (yaw/pitch in world space)
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    
    # Field of view
    hfov_deg: float = 4.0
    vfov_deg: float = 3.0
    
    # Optical Transceiver state
    tx_ready: bool = True
    rx_ready: bool = True
    
    # Physical constraints
    pan_limits_deg: tuple[float, float] = (-180.0, 180.0)
    tilt_limits_deg: tuple[float, float] = (-90.0, 90.0)
    
    @property
    def position(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @property
    def optical_axis(self) -> tuple[float, float, float]:
        """Returns the normalized optical axis vector."""
        yaw_rad = math.radians(self.yaw_deg)
        pitch_rad = math.radians(self.pitch_deg)
        
        dx = math.sin(yaw_rad) * math.cos(pitch_rad)
        dy = math.sin(pitch_rad)
        dz = math.cos(yaw_rad) * math.cos(pitch_rad)
        return (dx, dy, dz)

    def to_dict(self) -> dict[str, Any]:
        return {
            "terminal_id": self.terminal_id,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "yaw_deg": self.yaw_deg,
            "pitch_deg": self.pitch_deg,
            "hfov_deg": self.hfov_deg,
            "tx_ready": self.tx_ready,
            "rx_ready": self.rx_ready,
        }
