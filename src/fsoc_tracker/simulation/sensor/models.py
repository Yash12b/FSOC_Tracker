"""Data models for sensor rendering and ground truth.

Strongly typed dataclasses for ground truth metadata,
visibility states, and rendered frame results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import numpy as np


class TargetVisibility(Enum):
    VISIBLE = auto()
    PARTIAL = auto()
    OUTSIDE = auto()
    BEHIND_CAMERA = auto()


@dataclass
class GroundTruth:
    """Ground truth metadata for a single target in a rendered frame.

    This is metadata only and must NOT be drawn into the image.
    It is used for evaluation, training, debugging, and benchmarking.
    """

    target_id: int = 0
    target_visible: bool = False
    visibility: TargetVisibility = TargetVisibility.OUTSIDE
    target_world_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    target_camera_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    target_pixel_x: float = 0.0
    target_pixel_y: float = 0.0
    target_bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    target_size_px: float = 0.0
    horizontal_angle_deg: float = 0.0
    vertical_angle_deg: float = 0.0
    depth: float = 0.0
    brightness: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_visible": self.target_visible,
            "visibility": self.visibility.name,
            "target_world_position": list(self.target_world_position),
            "target_camera_position": list(self.target_camera_position),
            "target_pixel_x": self.target_pixel_x,
            "target_pixel_y": self.target_pixel_y,
            "target_bbox": list(self.target_bbox),
            "target_size_px": self.target_size_px,
            "horizontal_angle_deg": self.horizontal_angle_deg,
            "vertical_angle_deg": self.vertical_angle_deg,
            "depth": self.depth,
            "brightness": self.brightness,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GroundTruth:
        vis_str = d.get("visibility", "OUTSIDE")
        visibility = TargetVisibility[vis_str] if vis_str in TargetVisibility.__members__ else TargetVisibility.OUTSIDE
        return cls(
            target_id=d.get("target_id", 0),
            target_visible=d.get("target_visible", False),
            visibility=visibility,
            target_world_position=tuple(d.get("target_world_position", (0.0, 0.0, 0.0))),
            target_camera_position=tuple(d.get("target_camera_position", (0.0, 0.0, 0.0))),
            target_pixel_x=d.get("target_pixel_x", 0.0),
            target_pixel_y=d.get("target_pixel_y", 0.0),
            target_bbox=tuple(d.get("target_bbox", (0, 0, 0, 0))),
            target_size_px=d.get("target_size_px", 0.0),
            horizontal_angle_deg=d.get("horizontal_angle_deg", 0.0),
            vertical_angle_deg=d.get("vertical_angle_deg", 0.0),
            depth=d.get("depth", 0.0),
            brightness=d.get("brightness", 1.0),
        )


@dataclass
class RenderedFrame:
    """Complete result from the sensor renderer.

    Contains the raw sensor image (for perception), ground truth
    (for evaluation only), and metadata.
    """

    image: np.ndarray
    ground_truths: list[GroundTruth] = field(default_factory=list)
    timestamp_s: float = 0.0
    frame_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def width(self) -> int:
        return self.image.shape[1]

    @property
    def height(self) -> int:
        return self.image.shape[0]

    @property
    def channels(self) -> int:
        return self.image.shape[2] if self.image.ndim == 3 else 1

    def truth_for(self, primary_id: int | None) -> GroundTruth | None:
        """Eval truth for the designated primary. No silent first-target fallback
        unless the world contains exactly one beacon.
        """
        if not self.ground_truths:
            return None
        if primary_id is not None:
            for gt in self.ground_truths:
                if gt.target_id == primary_id:
                    return gt
            return None
        if len(self.ground_truths) == 1:
            return self.ground_truths[0]
        return None

    @property
    def primary_ground_truth(self) -> GroundTruth | None:
        """Deprecated alias: unique-target worlds only. Prefer truth_for(id)."""
        return self.truth_for(None)
