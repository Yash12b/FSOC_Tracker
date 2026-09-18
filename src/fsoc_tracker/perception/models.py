"""Perception data models.

Strongly typed models for detection results, perception state,
and candidate region features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class PerceptionStatus(Enum):
    NO_TARGET = auto()
    CANDIDATE = auto()
    DETECTED = auto()
    UNCERTAIN = auto()


class TargetClass(str, Enum):
    BEACON = "beacon"
    UNKNOWN = "unknown"


@dataclass
class CandidateFeatures:
    """Extracted features for a single candidate region."""

    centroid_x: float = 0.0
    centroid_y: float = 0.0
    area: float = 0.0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    width: float = 0.0
    height: float = 0.0
    aspect_ratio: float = 1.0
    perimeter: float = 0.0
    circularity: float = 0.0
    mean_intensity: float = 0.0
    max_intensity: float = 0.0
    integrated_intensity: float = 0.0
    local_contrast: float = 0.0


@dataclass
class BeaconDetection:
    """A single detection produced by the perception engine.

    Represents one candidate that passed scoring thresholds.
    """

    detected: bool = False
    target_id: int = 0
    target_class: TargetClass = TargetClass.BEACON
    center_x: float = 0.0
    center_y: float = 0.0
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)
    width: float = 0.0
    height: float = 0.0
    area: float = 0.0
    confidence: float = 0.0
    mean_intensity: float = 0.0
    max_intensity: float = 0.0
    integrated_intensity: float = 0.0
    local_contrast: float = 0.0
    timestamp_s: float = 0.0
    frame_index: int = 0
    algorithm: str = ""
    visibility_state: PerceptionStatus = PerceptionStatus.NO_TARGET
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def centroid(self) -> tuple[float, float]:
        return (self.center_x, self.center_y)

    @property
    def bbox_size(self) -> tuple[float, float]:
        return (self.width, self.height)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "target_id": self.target_id,
            "target_class": self.target_class.value,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "bbox": list(self.bbox),
            "width": self.width,
            "height": self.height,
            "area": self.area,
            "confidence": self.confidence,
            "mean_intensity": self.mean_intensity,
            "max_intensity": self.max_intensity,
            "integrated_intensity": self.integrated_intensity,
            "local_contrast": self.local_contrast,
            "timestamp_s": self.timestamp_s,
            "frame_index": self.frame_index,
            "algorithm": self.algorithm,
            "visibility_state": self.visibility_state.name,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BeaconDetection:
        vis_str = d.get("visibility_state", "NO_TARGET")
        PerceptionStatus[vis_str] if vis_str in PerceptionStatus.__members__ else PerceptionStatus.NO_TARGET
        cls_str = d.get("target_class", "beacon")
        tc = TargetClass(cls_str) if cls_str in TargetClass.__members__ else TargetClass.UNKNOWN
        return cls(
            detected=d.get("detected", False),
            target_id=d.get("target_id", 0),
            target_class=tc,
            center_x=d.get("center_x", 0.0),
            center_y=d.get("center_y", 0.0),
            bbox=tuple(d.get("bbox", (0, 0, 0, 0))),
            width=d.get("width", 0.0),
            height=d.get("height", 0.0),
            area=d.get("area", 0.0),
            confidence=d.get("confidence", 0.0),
            mean_intensity=d.get("mean_intensity", 0.0),
            max_intensity=d.get("max_intensity", 0.0),
            integrated_intensity=d.get("integrated_intensity", 0.0),
            local_contrast=d.get("local_contrast", 0.0),
            timestamp_s=d.get("timestamp_s", 0.0),
            frame_index=d.get("frame_index", 0),
            algorithm=d.get("algorithm", ""),
        )


@dataclass
class PerceptionResult:
    """Complete result from the perception engine for one frame."""

    detections: list[BeaconDetection] = field(default_factory=list)
    primary_detection: BeaconDetection | None = None
    processing_time_ms: float = 0.0
    frame_timestamp: float = 0.0
    frame_index: int = 0
    detector_name: str = ""
    status: PerceptionStatus = PerceptionStatus.NO_TARGET
    diagnostics: dict[str, Any] = field(default_factory=dict)
    image_width: int = 0
    image_height: int = 0

    @property
    def detected(self) -> bool:
        return self.primary_detection is not None and self.primary_detection.detected

    @property
    def num_candidates(self) -> int:
        return len(self.detections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detections": [d.to_dict() for d in self.detections],
            "primary_detection": self.primary_detection.to_dict() if self.primary_detection else None,
            "processing_time_ms": self.processing_time_ms,
            "frame_timestamp": self.frame_timestamp,
            "frame_index": self.frame_index,
            "detector_name": self.detector_name,
            "status": self.status.name,
            "image_width": self.image_width,
            "image_height": self.image_height,
        }
