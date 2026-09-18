"""Ground truth provider abstraction.

Supports synthetic ground truth from the simulator, sidecar annotation
files, and no-ground-truth mode for external video.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GroundTruthPoint:
    frame_index: int = 0
    timestamp_s: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    visible: bool = True
    bbox: tuple[int, int, int, int] | None = None
    size_px: float = 10.0
    metadata: dict[str, Any] | None = None


class GroundTruthProvider(ABC):
    @abstractmethod
    def get(self, frame_index: int) -> GroundTruthPoint | None: ...

    @property
    @abstractmethod
    def has_ground_truth(self) -> bool: ...

    @property
    @abstractmethod
    def frame_count(self) -> int | None: ...

    def get_range(self, start: int, end: int) -> list[GroundTruthPoint | None]:
        return [self.get(i) for i in range(start, end)]


class NullGroundTruthProvider(GroundTruthProvider):
    def get(self, frame_index: int) -> None:
        return None

    @property
    def has_ground_truth(self) -> bool:
        return False

    @property
    def frame_count(self) -> None:
        return None


class SyntheticGroundTruthProvider(GroundTruthProvider):
    def __init__(self) -> None:
        self._points: dict[int, GroundTruthPoint] = {}

    def add_point(self, point: GroundTruthPoint) -> None:
        self._points[point.frame_index] = point

    def add_points(self, points: list[GroundTruthPoint]) -> None:
        for p in points:
            self._points[p.frame_index] = p

    def get(self, frame_index: int) -> GroundTruthPoint | None:
        return self._points.get(frame_index)

    @property
    def has_ground_truth(self) -> bool:
        return len(self._points) > 0

    @property
    def frame_count(self) -> int:
        return len(self._points)


class SidecarGroundTruthProvider(GroundTruthProvider):
    def __init__(self, sidecar_path: str) -> None:
        self._points: dict[int, GroundTruthPoint] = {}
        self._load(sidecar_path)

    def _load(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return

        if p.suffix == ".json":
            self._load_json(p)
        elif p.suffix == ".jsonl":
            self._load_jsonl(p)
        elif p.suffix == ".csv":
            self._load_csv(p)

    def _load_json(self, path: Path) -> None:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            for entry in data:
                pt = self._parse_entry(entry)
                if pt is not None:
                    self._points[pt.frame_index] = pt
        elif isinstance(data, dict) and "frames" in data:
            for entry in data["frames"]:
                pt = self._parse_entry(entry)
                if pt is not None:
                    self._points[pt.frame_index] = pt

    def _load_jsonl(self, path: Path) -> None:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                pt = self._parse_entry(entry)
                if pt is not None:
                    self._points[pt.frame_index] = pt

    def _load_csv(self, path: Path) -> None:
        import csv
        with open(path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                pt = self._parse_entry(row)
                if pt is not None:
                    self._points[pt.frame_index] = pt

    def _parse_entry(self, entry: dict[str, Any]) -> GroundTruthPoint | None:
        try:
            frame_index = int(entry.get("frame_index", entry.get("frame", 0)))
            return GroundTruthPoint(
                frame_index=frame_index,
                timestamp_s=float(entry.get("timestamp", entry.get("timestamp_s", 0.0))),
                target_x=float(entry.get("target_x", entry.get("x", 0.0))),
                target_y=float(entry.get("target_y", entry.get("y", 0.0))),
                visible=bool(entry.get("visible", True)),
                size_px=float(entry.get("size_px", entry.get("size", 10.0))),
            )
        except (ValueError, KeyError):
            return None

    def get(self, frame_index: int) -> GroundTruthPoint | None:
        return self._points.get(frame_index)

    @property
    def has_ground_truth(self) -> bool:
        return len(self._points) > 0

    @property
    def frame_count(self) -> int:
        return len(self._points)
