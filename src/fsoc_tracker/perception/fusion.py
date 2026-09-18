"""Confidence-aware perception fusion.

Combines evidence from classical detector, AI detector, tracker
prediction, and image quality into one authoritative detection.
Uses documented scoring — not blind averaging.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fsoc_tracker.perception.models import (
    BeaconDetection,
    PerceptionResult,
)
from fsoc_tracker.perception.uncertainty import UncertaintyState


class FusionMethod(str, Enum):
    WEIGHTED_SCORE = "weighted_score"
    MAX_CONFIDENCE = "max_confidence"
    AI_DOMINANT = "ai_dominant"
    CLASSICAL_DOMINANT = "classical_dominant"


@dataclass
class FusionConfig:
    """Configuration for fusion engine."""

    method: FusionMethod = FusionMethod.WEIGHTED_SCORE

    w_classical: float = 0.35
    w_ai: float = 0.35
    w_tracker: float = 0.20
    w_quality: float = 0.10

    min_fusion_confidence: float = 0.2
    tracker_prediction_weight: float = 0.3
    association_distance_limit: float = 50.0

    reject_below_min_confidence: bool = True
    require_temporal_consistency: bool = False
    min_consistent_frames: int = 2


@dataclass
class FusedDetection:
    """Result of perception fusion."""

    detected: bool = False
    center_x: float = 0.0
    center_y: float = 0.0
    confidence: float = 0.0
    source: str = ""
    classical_confidence: float = 0.0
    ai_confidence: float = 0.0
    tracker_distance: float = 0.0
    quality_factor: float = 0.0
    fused_score: float = 0.0
    rejected: bool = False
    reject_reason: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)


class FusionEngine:
    """Combines evidence from multiple perception sources.

    Fusion scoring (WEIGHTED_SCORE method):
        score = w_classical * classical_conf
              + w_ai * ai_conf
              + w_tracker * tracker_compat
              + w_quality * quality_factor

    Where tracker_compat = max(0, 1 - dist / distance_limit).
    """

    def __init__(self, config: FusionConfig | None = None) -> None:
        self._config = config or FusionConfig()
        self._consistent_count: int = 0
        self._last_fused_x: float = 0.0
        self._last_fused_y: float = 0.0

    @property
    def config(self) -> FusionConfig:
        return self._config

    def fuse(
        self,
        classical_result: PerceptionResult | None = None,
        ai_result: PerceptionResult | None = None,
        predicted_position: tuple[float, float] | None = None,
        quality_factor: float = 1.0,
        uncertainty_state: UncertaintyState | None = None,
    ) -> FusedDetection:
        """Fuse evidence from multiple sources into one detection.

        Args:
            classical_result: Classical detector output.
            ai_result: AI detector output.
            predicted_position: Tracker predicted position (px, py).
            quality_factor: Image quality factor [0, 1].
            uncertainty_state: Current uncertainty estimate.

        Returns:
            FusedDetection with fused result.
        """
        classical_det = self._get_primary(classical_result)
        ai_det = self._get_primary(ai_result)

        classical_conf = classical_det.confidence if classical_det else 0.0
        ai_conf = ai_det.confidence if ai_det else 0.0

        classical_pos = (classical_det.center_x, classical_det.center_y) if classical_det else None
        ai_pos = (ai_det.center_x, ai_det.center_y) if ai_det else None

        fused = FusedDetection(
            classical_confidence=classical_conf,
            ai_confidence=ai_conf,
            quality_factor=quality_factor,
        )

        if self._config.method == FusionMethod.WEIGHTED_SCORE:
            result = self._weighted_fusion(
                classical_pos, classical_conf,
                ai_pos, ai_conf,
                predicted_position,
                quality_factor,
                fused,
            )
        elif self._config.method == FusionMethod.MAX_CONFIDENCE:
            result = self._max_confidence_fusion(
                classical_pos, classical_conf,
                ai_pos, ai_conf,
                fused,
            )
        elif self._config.method == FusionMethod.AI_DOMINANT:
            result = self._dominant_fusion(ai_pos, ai_conf, classical_pos, classical_conf, fused, "ai")
        else:
            result = self._dominant_fusion(classical_pos, classical_conf, ai_pos, ai_conf, fused, "classical")

        if result.detected:
            self._consistent_count += 1
            self._last_fused_x = result.center_x
            self._last_fused_y = result.center_y
        else:
            self._consistent_count = 0

        if self._config.reject_below_min_confidence and result.confidence < self._config.min_fusion_confidence:
            result.rejected = True
            result.reject_reason = f"confidence {result.confidence:.3f} < {self._config.min_fusion_confidence}"

        return result

    def _get_primary(self, result: PerceptionResult | None) -> BeaconDetection | None:
        if result is None:
            return None
        if result.primary_detection is not None and result.primary_detection.detected:
            return result.primary_detection
        if result.detections:
            best = max(result.detections, key=lambda d: d.confidence)
            if best.detected or best.confidence > 0.1:
                return best
        return None

    def _weighted_fusion(
        self,
        classical_pos, classical_conf,
        ai_pos, ai_conf,
        predicted_pos,
        quality_factor,
        fused: FusedDetection,
    ) -> FusedDetection:
        cfg = self._config

        tracker_compat = 0.0
        if predicted_pos is not None:
            best_pos = classical_pos or ai_pos
            if best_pos is not None:
                dist = math.sqrt(
                    (best_pos[0] - predicted_pos[0]) ** 2
                    + (best_pos[1] - predicted_pos[1]) ** 2
                )
                fused.tracker_distance = dist
                tracker_compat = max(0.0, 1.0 - dist / cfg.association_distance_limit)
            else:
                tracker_compat = 0.0

        fused_score = (
            cfg.w_classical * classical_conf
            + cfg.w_ai * ai_conf
            + cfg.w_tracker * tracker_compat
            + cfg.w_quality * quality_factor
        )
        fused.fused_score = fused_score

        best_pos = None
        if classical_pos and ai_pos:
            dist = math.sqrt(
                (classical_pos[0] - ai_pos[0]) ** 2
                + (classical_pos[1] - ai_pos[1]) ** 2
            )
            if dist < cfg.association_distance_limit:
                w_c = classical_conf / max(0.001, classical_conf + ai_conf)
                best_pos = (
                    classical_pos[0] * w_c + ai_pos[0] * (1.0 - w_c),
                    classical_pos[1] * w_c + ai_pos[1] * (1.0 - w_c),
                )
            else:
                if classical_conf >= ai_conf:
                    best_pos = classical_pos
                else:
                    best_pos = ai_pos
        elif classical_pos:
            best_pos = classical_pos
        elif ai_pos:
            best_pos = ai_pos
        elif predicted_pos is not None:
            best_pos = predicted_pos
            fused_score *= 0.5

        if best_pos is not None:
            fused.detected = True
            fused.center_x = best_pos[0]
            fused.center_y = best_pos[1]
            fused.confidence = min(1.0, fused_score)
            if classical_pos and ai_pos:
                fused.source = "hybrid"
            elif classical_pos:
                fused.source = "classical"
            else:
                fused.source = "ai"
        else:
            fused.detected = False
            fused.confidence = 0.0
            fused.source = "none"

        return fused

    def _max_confidence_fusion(
        self, classical_pos, classical_conf,
        ai_pos, ai_conf,
        fused: FusedDetection,
    ) -> FusedDetection:
        if classical_conf >= ai_conf and classical_pos:
            fused.detected = True
            fused.center_x, fused.center_y = classical_pos
            fused.confidence = classical_conf
            fused.source = "classical"
        elif ai_pos:
            fused.detected = True
            fused.center_x, fused.center_y = ai_pos
            fused.confidence = ai_conf
            fused.source = "ai"
        else:
            fused.detected = False
            fused.source = "none"
        return fused

    def _dominant_fusion(
        self, dom_pos, dom_conf, sub_pos, sub_conf,
        fused: FusedDetection, dom_name: str,
    ) -> FusedDetection:
        if dom_pos and dom_conf > 0.1:
            fused.detected = True
            fused.center_x, fused.center_y = dom_pos
            fused.confidence = dom_conf
            fused.source = dom_name
        elif sub_pos and sub_conf > 0.1:
            fused.detected = True
            fused.center_x, fused.center_y = sub_pos
            fused.confidence = sub_conf
            fused.source = "fallback"
        else:
            fused.detected = False
            fused.source = "none"
        return fused

    def reset(self) -> None:
        self._consistent_count = 0
        self._last_fused_x = 0.0
        self._last_fused_y = 0.0
