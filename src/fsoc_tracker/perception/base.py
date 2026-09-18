"""Perception engine interface.

Abstract base class for perception backends (classical, AI, hybrid).
The downstream pipeline is agnostic to which backend produced the detection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from fsoc_tracker.perception.config import PerceptionConfig
from fsoc_tracker.perception.models import PerceptionResult


class PerceptionEngine(ABC):
    """Abstract base class for perception engines.

    All perception backends must implement this interface.
    The downstream tracking/control pipeline consumes only
    PerceptionResult, never knowing which backend produced it.
    """

    def __init__(self, config: PerceptionConfig | None = None) -> None:
        self._config = config or PerceptionConfig()

    @property
    def config(self) -> PerceptionConfig:
        return self._config

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        timestamp_s: float = 0.0,
        frame_index: int = 0,
    ) -> PerceptionResult:
        """Run detection on a single frame.

        Args:
            image: Input image (grayscale or BGR).
            timestamp_s: Frame timestamp.
            frame_index: Sequential frame index.

        Returns:
            PerceptionResult with detections and metadata.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the perception algorithm."""

    def reset(self) -> None:
        """Reset internal state (optional, for stateful detectors)."""
