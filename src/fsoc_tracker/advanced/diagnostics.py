"""Diagnostic events and explainability.

Structured decision events that explain WHY the system made
each adaptive decision. No LLM — pure engineering reasons.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class DiagnosticEvent(Enum):
    PERCEPTION_SWITCH = auto()
    ROI_EXPANSION = auto()
    ROI_REDUCTION = auto()
    SEARCH_START = auto()
    SEARCH_END = auto()
    SEARCH_PHASE_ADVANCE = auto()
    REACQUIRE_START = auto()
    REACQUIRE_SUCCESS = auto()
    REACQUIRE_REJECT = auto()
    LOCK_GAINED = auto()
    LOCK_LOST = auto()
    GAIN_SCHEDULE_CHANGE = auto()
    FEED_FORWARD_ACTIVE = auto()
    OSCILLATION_DETECTED = auto()
    UNCERTAINTY_HIGH = auto()
    UNCERTAINTY_LOW = auto()
    Q_ADAPTATION = auto()
    R_ADAPTATION = auto()
    MANEUVER_DETECTED = auto()
    SMOOTH_MOTION = auto()
    AI_INFERENCE_SKIPPED = auto()
    MODEL_FALLBACK = auto()
    CONTROL_AUTHORITY_REDUCED = auto()
    SUBPIXEL_REFINEMENT = auto()
    CONFIDENCE_REJECT = auto()


@dataclass
class DiagnosticEntry:
    """A single diagnostic event with reason and metrics."""

    event: DiagnosticEvent
    timestamp_s: float
    reason: str
    frame_index: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event": self.event.name,
            "timestamp_s": round(self.timestamp_s, 4),
            "reason": self.reason,
            "frame_index": self.frame_index,
            "metrics": self.metrics,
        }


class DiagnosticLog:
    """Bounded diagnostic event log.

    Stores recent events for debugging and explainability.
    Automatically evicts old entries.
    """

    def __init__(self, max_entries: int = 500) -> None:
        self._entries: list[DiagnosticEntry] = []
        self._max_entries = max_entries

    @property
    def entries(self) -> list[DiagnosticEntry]:
        return list(self._entries)

    @property
    def recent(self) -> list[DiagnosticEntry]:
        return self._entries[-20:]

    def log(
        self,
        event: DiagnosticEvent,
        timestamp_s: float,
        reason: str,
        frame_index: int = 0,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """Log a diagnostic event."""
        entry = DiagnosticEntry(
            event=event,
            timestamp_s=timestamp_s,
            reason=reason,
            frame_index=frame_index,
            metrics=metrics or {},
        )
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def get_events(
        self,
        event_type: DiagnosticEvent | None = None,
        since_timestamp: float = 0.0,
    ) -> list[DiagnosticEntry]:
        """Query events by type and/or time range."""
        result = self._entries
        if event_type is not None:
            result = [e for e in result if e.event == event_type]
        if since_timestamp > 0:
            result = [e for e in result if e.timestamp_s >= since_timestamp]
        return result

    def count_recent(self, event_type: DiagnosticEvent, window_s: float = 1.0, current_time: float = 0.0) -> int:
        """Count events of a type within a time window."""
        cutoff = current_time - window_s
        return sum(1 for e in self._entries if e.event == event_type and cutoff <= e.timestamp_s <= current_time)

    def clear(self) -> None:
        self._entries.clear()

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self._entries[-50:]]
