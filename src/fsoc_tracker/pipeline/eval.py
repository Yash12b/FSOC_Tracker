"""Offline evaluation channel — never mixed into runtime Frames.

The tracker, perception, AI, and controller consume camera frames only.
Scoring against simulator (or labeled) truth happens here, after the
fact, keyed by frame index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalRecord:
    """One frame of evaluation truth, stored off the runtime Frame."""

    frame_index: int
    timestamp_s: float
    primary_id: int | None = None
    ground_truths: list[Any] = field(default_factory=list)

    @property
    def primary(self) -> Any | None:
        """Truth for the designated primary beacon, else None.

        Never falls back to "first rendered target" — that would score
        the wrong object in multi-beacon worlds.
        """
        if not self.ground_truths:
            return None
        if self.primary_id is None:
            return None
        for gt in self.ground_truths:
            tid = getattr(gt, "target_id", None)
            if tid is None and isinstance(gt, dict):
                tid = gt.get("target_id")
            if tid == self.primary_id:
                return gt
        return None


class EvalSink:
    """Side channel for evaluation truth.

    Attach to a simulation (or labeled dataset) source. The runtime
    pipeline never reads this unless it is scoring after control.
    """

    def __init__(self) -> None:
        self._by_index: dict[int, EvalRecord] = {}
        self._latest: EvalRecord | None = None

    def record(
        self,
        frame_index: int,
        timestamp_s: float,
        ground_truths: list[Any],
        primary_id: int | None = None,
    ) -> EvalRecord:
        rec = EvalRecord(
            frame_index=frame_index,
            timestamp_s=timestamp_s,
            primary_id=primary_id,
            ground_truths=list(ground_truths),
        )
        self._by_index[frame_index] = rec
        self._latest = rec
        return rec

    def get(self, frame_index: int) -> EvalRecord | None:
        return self._by_index.get(frame_index)

    def primary_for(self, frame_index: int) -> Any | None:
        rec = self.get(frame_index)
        return rec.primary if rec is not None else None

    @property
    def latest(self) -> EvalRecord | None:
        return self._latest

    def clear(self) -> None:
        self._by_index.clear()
        self._latest = None

    def __len__(self) -> int:
        return len(self._by_index)


def score_against_truth(
    estimated_x: float,
    estimated_y: float,
    gt: Any,
    frame_width: int,
    frame_height: int,
) -> tuple[float | None, float | None, float | None, bool]:
    """Return (error_x, error_y, error_px, fov_inside) from eval truth.

    ``gt`` may be a GroundTruth dataclass or a dict with the same fields.
    """
    if gt is None:
        return None, None, None, False

    visible = getattr(gt, "target_visible", None)
    if visible is None and isinstance(gt, dict):
        visible = gt.get("target_visible", False)
    px = getattr(gt, "target_pixel_x", None)
    py = getattr(gt, "target_pixel_y", None)
    if px is None and isinstance(gt, dict):
        px = gt.get("target_pixel_x")
        py = gt.get("target_pixel_y")
    if not visible or px is None or py is None:
        return None, None, None, False

    err_x = estimated_x - float(px)
    err_y = estimated_y - float(py)
    err_px = float((err_x**2 + err_y**2) ** 0.5)
    fov_inside = 0 <= float(px) < frame_width and 0 <= float(py) < frame_height
    return err_x, err_y, err_px, fov_inside
