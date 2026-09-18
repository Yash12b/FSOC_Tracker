"""Classical bright-spot perception engine.

Wraps the classical detection pipeline behind the PerceptionEngine ABC.
"""

from __future__ import annotations

import numpy as np

from fsoc_tracker.perception.base import PerceptionEngine
from fsoc_tracker.perception.classical import detect_beacon
from fsoc_tracker.perception.config import PerceptionConfig
from fsoc_tracker.perception.models import PerceptionResult


class ClassicalBeaconDetector(PerceptionEngine):
    """Classical CV bright-spot beacon detector.

    Uses thresholding, connected components, feature extraction,
    and weighted scoring to detect small optical beacons.
    """

    def __init__(self, config: PerceptionConfig | None = None) -> None:
        super().__init__(config)

    @property
    def name(self) -> str:
        return "classical_bright_spot"

    def detect(
        self,
        image: np.ndarray,
        timestamp_s: float = 0.0,
        frame_index: int = 0,
    ) -> PerceptionResult:
        return detect_beacon(image, self._config, timestamp_s, frame_index)
