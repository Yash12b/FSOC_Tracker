"""Performance profiler / stage timer.

Measures per-stage timing for each frame.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class StageTimings:
    preprocessing_ms: float = 0.0
    disturbance_ms: float = 0.0
    perception_ms: float = 0.0
    tracking_ms: float = 0.0
    control_ms: float = 0.0
    rendering_ms: float = 0.0
    metrics_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class StageStats:
    mean_ms: float = 0.0
    median_ms: float = 0.0
    p95_ms: float = 0.0
    max_ms: float = 0.0
    min_ms: float = 0.0
    count: int = 0


class PerformanceProfiler:
    """Collects per-stage timing data across frames."""

    STAGES = ("preprocessing", "disturbance", "perception", "tracking", "control", "rendering", "metrics")

    def __init__(self) -> None:
        self._data: dict[str, list[float]] = {s: [] for s in self.STAGES}
        self._active_timer: str | None = None
        self._timer_start: float = 0.0

    def start_stage(self, stage: str) -> None:
        if stage not in self._data:
            self._data[stage] = []
        self._active_timer = stage
        self._timer_start = time.perf_counter()

    def end_stage(self) -> float:
        if self._active_timer is None:
            return 0.0
        elapsed_ms = (time.perf_counter() - self._timer_start) * 1000.0
        self._data[self._active_timer].append(elapsed_ms)
        self._active_timer = None
        return elapsed_ms

    def record_stage(self, stage: str, elapsed_ms: float) -> None:
        if stage not in self._data:
            self._data[stage] = []
        self._data[stage].append(elapsed_ms)

    def get_frame_timings(self) -> StageTimings:
        return StageTimings(
            preprocessing_ms=self._data.get("preprocessing", [0.0])[-1] if self._data.get("preprocessing") else 0.0,
            disturbance_ms=self._data.get("disturbance", [0.0])[-1] if self._data.get("disturbance") else 0.0,
            perception_ms=self._data.get("perception", [0.0])[-1] if self._data.get("perception") else 0.0,
            tracking_ms=self._data.get("tracking", [0.0])[-1] if self._data.get("tracking") else 0.0,
            control_ms=self._data.get("control", [0.0])[-1] if self._data.get("control") else 0.0,
            rendering_ms=self._data.get("rendering", [0.0])[-1] if self._data.get("rendering") else 0.0,
            metrics_ms=self._data.get("metrics", [0.0])[-1] if self._data.get("metrics") else 0.0,
            total_ms=sum(
                (self._data.get(s, [0.0])[-1] if self._data.get(s) else 0.0)
                for s in self.STAGES
            ),
        )

    def get_stats(self, stage: str) -> StageStats:
        vals = self._data.get(stage, [])
        if not vals:
            return StageStats()
        arr = np.array(vals)
        return StageStats(
            mean_ms=float(np.mean(arr)),
            median_ms=float(np.median(arr)),
            p95_ms=float(np.percentile(arr, 95)),
            max_ms=float(np.max(arr)),
            min_ms=float(np.min(arr)),
            count=len(vals),
        )

    def get_all_stats(self) -> dict[str, StageStats]:
        return {s: self.get_stats(s) for s in self.STAGES}

    def check_budget(self, budget: dict[str, float]) -> list[dict[str, Any]]:
        violations = []
        for stage, max_ms in budget.items():
            stats = self.get_stats(stage)
            if stats.mean_ms > max_ms:
                violations.append({
                    "stage": stage,
                    "budget_ms": max_ms,
                    "actual_mean_ms": stats.mean_ms,
                    "actual_p95_ms": stats.p95_ms,
                    "actual_max_ms": stats.max_ms,
                    "overrun_percent": ((stats.mean_ms - max_ms) / max_ms) * 100.0,
                })
        return violations

    def reset(self) -> None:
        self._data = {s: [] for s in self.STAGES}
        self._active_timer = None
        self._timer_start = 0.0
