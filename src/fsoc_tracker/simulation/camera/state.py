"""Camera state and configuration models.

Strongly typed dataclasses for camera state, intrinsics, and
projection results.  No raw dictionaries for core camera state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CameraViewMode(str, Enum):
    """Camera view modes.

    FREE_WORLD:       Independent orbit camera for exploration/visualization.
    TERMINAL_A_POV:   Camera operates from Terminal A's actual optical orientation.
    FOLLOW:           Camera tracks the primary beacon via PID control.
    SEARCH_TRACK:     Camera performs search pattern, then locks via PID.
    """

    FREE_WORLD = "FREE"
    TERMINAL_A_POV = "TERMINAL A POV"
    FOLLOW = "FOLLOW"
    SEARCH_TRACK = "SEARCH / TRACK"


@dataclass
class CameraIntrinsics:
    """Camera intrinsic parameters derived from FOV and resolution.

    Focal lengths are computed from:
        fx = (width / 2) / tan(HFOV / 2)
        fy = (height / 2) / tan(VFOV / 2)

    Principal point defaults to image center.
    """

    width: int = 640
    height: int = 480
    horizontal_fov_deg: float = 4.0
    vertical_fov_deg: float = 3.0

    focal_length_px: float = 0.0
    fx: float = 0.0
    fy: float = 0.0
    cx: float = 0.0
    cy: float = 0.0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Camera resolution must be positive")
        if not 0.0 < self.horizontal_fov_deg < 180.0:
            raise ValueError("Horizontal FOV must be between 0 and 180 degrees")
        if not 0.0 < self.vertical_fov_deg < 180.0:
            raise ValueError("Vertical FOV must be between 0 and 180 degrees")
        self._compute()

    def _compute(self) -> None:
        hfov_rad = math.radians(self.horizontal_fov_deg)
        vfov_rad = math.radians(self.vertical_fov_deg)
        self.fx = (self.width / 2.0) / math.tan(hfov_rad / 2.0)
        self.fy = (self.height / 2.0) / math.tan(vfov_rad / 2.0)
        self.cx = self.width / 2.0
        self.cy = self.height / 2.0
        self.focal_length_px = (self.fx + self.fy) / 2.0

    @property
    def hfov_rad(self) -> float:
        return math.radians(self.horizontal_fov_deg)

    @property
    def vfov_rad(self) -> float:
        return math.radians(self.vertical_fov_deg)


@dataclass
class CameraLimits:
    """Optional pan/tilt angular limits."""

    pan_min_deg: float | None = None
    pan_max_deg: float | None = None
    tilt_min_deg: float | None = None
    tilt_max_deg: float | None = None

    def clamp_pan(self, pan_deg: float) -> float:
        if self.pan_min_deg is not None:
            pan_deg = max(self.pan_min_deg, pan_deg)
        if self.pan_max_deg is not None:
            pan_deg = min(self.pan_max_deg, pan_deg)
        return pan_deg

    def clamp_tilt(self, tilt_deg: float) -> float:
        if self.tilt_min_deg is not None:
            tilt_deg = max(self.tilt_min_deg, tilt_deg)
        if self.tilt_max_deg is not None:
            tilt_deg = min(self.tilt_max_deg, tilt_deg)
        return tilt_deg

    def pan_at_limit(self, pan_deg: float) -> bool:
        if self.pan_min_deg is not None and pan_deg <= self.pan_min_deg:
            return True
        if self.pan_max_deg is not None and pan_deg >= self.pan_max_deg:
            return True
        return False

    def tilt_at_limit(self, tilt_deg: float) -> bool:
        if self.tilt_min_deg is not None and tilt_deg <= self.tilt_min_deg:
            return True
        if self.tilt_max_deg is not None and tilt_deg >= self.tilt_max_deg:
            return True
        return False


@dataclass
class CameraState:
    """Full state of the virtual PTZ camera.

    Pan = yaw (horizontal rotation).
    Tilt = pitch (vertical rotation).
    Roll is supported but typically zero for FSOC terminals.

    Coordinate convention:
        World: +X right, +Y up, +Z forward
        Camera: +X right, +Y up, +Z forward (looking direction)

    Pan/tilt define the camera's orientation in world space.

    Attributes:
        position_x, position_y, position_z: World position.
        pan_deg: Horizontal rotation (yaw) in degrees.
        tilt_deg: Vertical rotation (pitch) in degrees.
        roll_deg: Roll in degrees.
        horizontal_fov_deg: Horizontal field of view.
        vertical_fov_deg: Vertical field of view.
        width, height: Image resolution in pixels.
        max_pan_speed_deg_s: Maximum pan rotation rate.
        max_tilt_speed_deg_s: Maximum tilt rotation rate.
        view_mode: Current camera view mode.
        timestamp_s: Current timestamp.
        enabled: Whether camera is active.
    """

    position_x: float = 1000.0
    position_y: float = 1000.0
    position_z: float = 50.0

    pan_deg: float = 0.0
    tilt_deg: float = 0.0
    roll_deg: float = 0.0

    horizontal_fov_deg: float = 4.0
    vertical_fov_deg: float = 3.0

    width: int = 640
    height: int = 480

    max_pan_speed_deg_s: float = 5.0
    max_tilt_speed_deg_s: float = 5.0

    view_mode: CameraViewMode = CameraViewMode.FREE_WORLD
    timestamp_s: float = 0.0
    enabled: bool = True

    @property
    def position(self) -> tuple[float, float, float]:
        return (self.position_x, self.position_y, self.position_z)

    @property
    def yaw(self) -> float:
        """Yaw in degrees (alias for pan_deg)."""
        return self.pan_deg

    @yaw.setter
    def yaw(self, value: float) -> None:
        self.pan_deg = value

    @property
    def pitch(self) -> float:
        """Pitch in degrees (alias for tilt_deg)."""
        return self.tilt_deg

    @pitch.setter
    def pitch(self, value: float) -> None:
        self.tilt_deg = value

    @property
    def intrinsics(self) -> CameraIntrinsics:
        return CameraIntrinsics(
            width=self.width,
            height=self.height,
            horizontal_fov_deg=self.horizontal_fov_deg,
            vertical_fov_deg=self.vertical_fov_deg,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_x": self.position_x,
            "position_y": self.position_y,
            "position_z": self.position_z,
            "pan_deg": self.pan_deg,
            "tilt_deg": self.tilt_deg,
            "roll_deg": self.roll_deg,
            "horizontal_fov_deg": self.horizontal_fov_deg,
            "vertical_fov_deg": self.vertical_fov_deg,
            "width": self.width,
            "height": self.height,
            "max_pan_speed_deg_s": self.max_pan_speed_deg_s,
            "max_tilt_speed_deg_s": self.max_tilt_speed_deg_s,
            "view_mode": self.view_mode.value,
            "timestamp_s": self.timestamp_s,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CameraState:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ProjectionResult:
    """Result of projecting a 3D world point into the camera image.

    Attributes:
        visible: Whether the point is within the camera FOV.
        pixel_x: Horizontal pixel coordinate (0 = left edge).
        pixel_y: Vertical pixel coordinate (0 = top edge).
        depth: Distance along camera Z axis (positive = in front).
        normalized_x: Normalized horizontal position (-1 to 1 across FOV).
        normalized_y: Normalized vertical position (-1 to 1 across FOV).
        horizontal_angle_deg: Horizontal angle from optical axis.
        vertical_angle_deg: Vertical angle from optical axis.
        camera_x, camera_y, camera_z: Point in camera coordinates.
    """

    visible: bool = False
    pixel_x: float = 0.0
    pixel_y: float = 0.0
    depth: float = 0.0
    normalized_x: float = 0.0
    normalized_y: float = 0.0
    horizontal_angle_deg: float = 0.0
    vertical_angle_deg: float = 0.0
    camera_x: float = 0.0
    camera_y: float = 0.0
    camera_z: float = 0.0


@dataclass
class AngularError:
    """Angular error between camera optical axis and target direction.

    Units are degrees.  Positive horizontal_angle_deg means target is
    to the right of center.  Positive vertical_angle_deg means target
    is above center.
    """

    horizontal_angle_deg: float = 0.0
    vertical_angle_deg: float = 0.0

    @property
    def total_angle_deg(self) -> float:
        return math.sqrt(self.horizontal_angle_deg**2 + self.vertical_angle_deg**2)
