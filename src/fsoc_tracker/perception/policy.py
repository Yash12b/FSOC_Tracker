"""Adaptive perception policy.

Selects perception strategy based on image quality, tracking state,
and uncertainty. Clean state-machine transitions, not arbitrary if-chains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from fsoc_tracker.perception.quality import QualityLevel, QualityState
from fsoc_tracker.perception.uncertainty import UncertaintyLevel, UncertaintyState


class PerceptionMode(Enum):
    FULL_FRAME = auto()
    ROI = auto()
    REFINEMENT = auto()
    SEARCH = auto()


@dataclass
class PerceptionPolicyState:
    """Current policy decision and metadata."""

    mode: PerceptionMode = PerceptionMode.FULL_FRAME
    use_enhanced_denoising: bool = False
    use_adaptive_threshold: bool = True
    use_roi_extraction: bool = False
    use_subpixel_refinement: bool = True
    roi_expand_factor: float = 1.0
    confidence_boost: float = 0.0

    reason: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)


class PerceptionPolicy:
    """Selects perception strategy based on operating conditions.

    Transitions are explicit and logged. No opaque decision logic.

    Strategy selection:
        EXCELLENT/GOOD quality + TRACKING -> ROI + refinement
        DEGRADED quality -> adaptive threshold + denoising
        POOR quality -> enhanced denoising + global threshold
        CRITICAL quality -> minimal processing
        LOST/SEARCHING -> full-frame search
        HIGH uncertainty -> wider ROI
        LOW uncertainty -> tight ROI
    """

    def decide(
        self,
        quality: QualityState,
        uncertainty: UncertaintyState,
        tracking_state_name: str = "NO_TRACK",
        has_detection: bool = False,
        last_roi: tuple[int, int, int, int] | None = None,
    ) -> PerceptionPolicyState:
        """Decide perception strategy for current frame.

        Args:
            quality: Current image quality assessment.
            uncertainty: Current uncertainty estimate.
            tracking_state_name: Current tracker state name.
            has_detection: Whether a detection existed in the previous frame.
            last_roi: Previous ROI bounding box (x1, y1, x2, y2).

        Returns:
            PerceptionPolicyState with strategy and parameters.
        """
        state = PerceptionPolicyState()

        is_tracking = tracking_state_name in ("TRACKING", "REACQUIRING")
        is_searching = tracking_state_name in ("SEARCHING", "LOST", "NO_TRACK")
        is_acquiring = tracking_state_name == "ACQUIRING"

        if is_searching:
            state.mode = PerceptionMode.FULL_FRAME
            state.use_roi_extraction = False
            state.use_adaptive_threshold = True
            state.reason = "searching_full_frame"
            return state

        if quality.level == QualityLevel.CRITICAL:
            state.mode = PerceptionMode.FULL_FRAME
            state.use_enhanced_denoising = True
            state.use_adaptive_threshold = True
            state.use_subpixel_refinement = False
            state.reason = "critical_quality_fallback"
            return state

        if is_tracking and has_detection:
            state.mode = PerceptionMode.ROI
            state.use_roi_extraction = True
            state.use_subpixel_refinement = True

            if uncertainty.level in (UncertaintyLevel.HIGH, UncertaintyLevel.VERY_HIGH):
                state.roi_expand_factor = 2.5
                state.reason = "tracking_high_uncertainty_wide_roi"
            elif uncertainty.level == UncertaintyLevel.MODERATE:
                state.roi_expand_factor = 1.5
                state.reason = "tracking_moderate_uncertainty"
            else:
                state.roi_expand_factor = 1.0
                state.reason = "tracking_tight_roi"

            if quality.level == QualityLevel.DEGRADED:
                state.use_enhanced_denoising = True
                state.use_adaptive_threshold = True
                state.reason += "_degraded_enhanced"
            elif quality.level == QualityLevel.POOR:
                state.use_enhanced_denoising = True
                state.use_adaptive_threshold = True
                state.confidence_boost = -0.1
                state.reason += "_poor_quality_caution"

            return state

        if is_acquiring:
            state.mode = PerceptionMode.FULL_FRAME
            state.use_roi_extraction = False
            state.use_adaptive_threshold = True
            state.use_subpixel_refinement = True
            state.reason = "acquiring_full_frame"
            return state

        state.mode = PerceptionMode.FULL_FRAME
        state.use_adaptive_threshold = quality.level in (
            QualityLevel.DEGRADED, QualityLevel.POOR, QualityLevel.CRITICAL
        )
        state.use_enhanced_denoising = quality.level in (
            QualityLevel.POOR, QualityLevel.CRITICAL
        )
        state.use_subpixel_refinement = quality.level != QualityLevel.CRITICAL
        state.reason = "default_full_frame"
        return state
