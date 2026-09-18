"""Bounded AI mission-brain primitives for hybrid beacon tracking.

The mission brain consumes runtime-observable tracking features only. It may
recommend a strategy, but deterministic control and safety limits remain the
final authority.
"""

from __future__ import annotations

import json
import math
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class Situation(str, Enum):
    NORMAL_TRACKING = "normal_tracking"
    FAST_TARGET_MOTION = "fast_target_motion"
    HIGH_NOISE = "high_noise"
    EDGE_OF_FOV = "edge_of_fov"
    DEGRADING_TRACK = "degrading_track"
    LOW_CONFIDENCE = "low_confidence"
    PREDICTION_UNCERTAIN = "prediction_uncertain"
    TARGET_LOST = "target_lost"
    REACQUISITION = "reacquisition"
    RECOVERY = "recovery"


class MissionAction(str, Enum):
    TRACK = "track"
    TRACK_PREDICTIVE = "track_predictive"
    USE_ROI = "use_roi"
    USE_FULL_FRAME = "use_full_frame"
    RUN_CLASSICAL = "run_classical"
    RUN_HYBRID = "run_hybrid"
    LOCAL_SEARCH = "local_search"
    GLOBAL_SEARCH = "global_search"
    REACQUIRE = "reacquire"
    HOLD = "hold"
    SAFE_STOP = "safe_stop"


@dataclass(frozen=True)
class ObservationFeatures:
    """Runtime-observable state; deliberately contains no ground truth."""

    timestamp_s: float
    detected: bool
    confidence: float
    residual_px: float
    uncertainty_x_px: float
    uncertainty_y_px: float
    velocity_x_px_s: float
    velocity_y_px_s: float
    distance_from_center_px: float
    time_since_detection_s: float
    latency_ms: float
    source_fps: float
    processing_fps: float
    candidate_count: int
    roi_radius_px: float = 0.0


@dataclass(frozen=True)
class MotionPrediction:
    mean_x_px: float
    mean_y_px: float
    uncertainty_x_px: float
    uncertainty_y_px: float
    horizon_s: float
    method: str = "bounded_constant_velocity"


class MotionPredictor:
    """Deterministic baseline predictor used until a trained model wins A/B."""

    def __init__(self, uncertainty_growth_px_s: float = 10.0) -> None:
        if uncertainty_growth_px_s < 0:
            raise ValueError("uncertainty_growth_px_s must be non-negative")
        self._uncertainty_growth = uncertainty_growth_px_s

    def predict(self, features: ObservationFeatures, horizon_s: float) -> MotionPrediction:
        if horizon_s < 0 or not math.isfinite(horizon_s):
            raise ValueError("horizon_s must be finite and non-negative")
        return MotionPrediction(
            mean_x_px=features.velocity_x_px_s * horizon_s,
            mean_y_px=features.velocity_y_px_s * horizon_s,
            uncertainty_x_px=max(0.0, features.uncertainty_x_px)
            + self._uncertainty_growth * horizon_s,
            uncertainty_y_px=max(0.0, features.uncertainty_y_px)
            + self._uncertainty_growth * horizon_s,
            horizon_s=horizon_s,
        )


class SituationClassifier:
    """Explainable observable-feature situation classifier.

    Classifies into 10 situation categories based on runtime-observable features.
    No ground truth is used.
    """

    def __init__(
        self,
        fast_velocity_threshold_px_s: float = 200.0,
        edge_of_fov_margin: float = 0.15,
        degrading_track_misses: int = 3,
        uncertainty_threshold_px: float = 30.0,
    ) -> None:
        self._fast_vel = fast_velocity_threshold_px_s
        self._edge_margin = edge_of_fov_margin
        self._degrading_misses = degrading_track_misses
        self._uncertainty_thresh = uncertainty_threshold_px

    def classify(self, features: ObservationFeatures) -> Situation:
        # TARGET_LOST: no detection at all
        if not features.detected and features.time_since_detection_s <= 0:
            return Situation.TARGET_LOST

        # REACQUISITION: had a detection before, now lost
        if not features.detected and features.time_since_detection_s > 0:
            return Situation.REACQUISITION

        # LOW_CONFIDENCE: detection exists but weak
        if features.confidence < 0.3:
            return Situation.LOW_CONFIDENCE

        # HIGH_NOISE: residual exceeds uncertainty
        if features.residual_px > max(
            10.0, features.uncertainty_x_px + features.uncertainty_y_px
        ):
            return Situation.HIGH_NOISE

        # FAST_TARGET_MOTION: high velocity
        vel_mag = math.sqrt(
            features.velocity_x_px_s ** 2 + features.velocity_y_px_s ** 2
        )
        if vel_mag > self._fast_vel:
            return Situation.FAST_TARGET_MOTION

        # EDGE_OF_FOV: detection near image boundary
        if features.distance_from_center_px > 0:
            # Approximate FOV edge: distance from center > 80% of half-diagonal
            # Use distance_from_center_px as proxy (already computed upstream)
            if features.roi_radius_px > 0:
                normalized_dist = features.distance_from_center_px / max(
                    features.roi_radius_px, 1.0
                )
                if normalized_dist > (1.0 - self._edge_margin):
                    return Situation.EDGE_OF_FOV

        # PREDICTION_UNCERTAIN: high uncertainty relative to velocity
        if features.uncertainty_x_px > self._uncertainty_thresh or (
            features.uncertainty_y_px > self._uncertainty_thresh
        ):
            return Situation.PREDICTION_UNCERTAIN

        # DEGRADING_TRACK: multiple consecutive misses (low confidence + miss trend)
        if (
            features.confidence < 0.5
            and features.time_since_detection_s > 0.1
        ):
            return Situation.DEGRADING_TRACK

        return Situation.NORMAL_TRACKING


@dataclass(frozen=True)
class SafetyLimits:
    max_pan_rate_deg_s: float = 5.0
    max_tilt_rate_deg_s: float = 5.0
    max_roi_radius_px: float = 320.0
    stale_timeout_s: float = 0.5


@dataclass(frozen=True)
class SafeRecommendation:
    action: MissionAction
    confidence: float
    approved: bool
    fallback: MissionAction | None
    reason: str
    timestamp_s: float


@dataclass(frozen=True)
class MissionObservation:
    """Input bundle accepted by the orchestrator."""

    features: ObservationFeatures
    camera_pan_deg: float = 0.0
    camera_tilt_deg: float = 0.0


@dataclass(frozen=True)
class MissionDecision:
    action: MissionAction
    situation: Situation
    confidence: float
    prediction: MotionPrediction | None
    reason: str
    timestamp_s: float
    safety: SafeRecommendation


class AIMissionBrain:
    """Coordinates small AI modules without mutating application state."""

    def __init__(
        self,
        policy: ExpertPolicy | None = None,
        predictor: MotionPredictor | None = None,
        learned_motion: object | None = None,
        learned_situation: object | None = None,
        learned_policy: object | None = None,
        max_latency_ms: float = 20.0,
        prediction_horizon_s: float = 0.1,
    ) -> None:
        if max_latency_ms <= 0:
            raise ValueError("max_latency_ms must be positive")
        if prediction_horizon_s < 0 or not math.isfinite(prediction_horizon_s):
            raise ValueError("prediction_horizon_s must be finite and non-negative")
        self._policy = policy or ExpertPolicy()
        self._predictor = predictor or MotionPredictor()
        self._classifier = SituationClassifier()
        self._learned_motion = learned_motion
        self._learned_situation = learned_situation
        self._learned_policy = learned_policy
        self._max_latency_ms = max_latency_ms
        self._prediction_horizon_s = prediction_horizon_s

    @property
    def prediction_horizon_s(self) -> float:
        """Motion-forecast horizon in seconds (runtime configurable)."""
        return self._prediction_horizon_s

    @prediction_horizon_s.setter
    def prediction_horizon_s(self, value: float) -> None:
        if value < 0 or not math.isfinite(value):
            raise ValueError(
                "prediction_horizon_s must be finite and non-negative")
        self._prediction_horizon_s = float(value)

    @property
    def model_status(self) -> str:
        """Provenance label for the active policy stack (runtime display)."""
        parts = []
        if self._learned_motion is not None and getattr(
            self._learned_motion, "trained", False
        ):
            parts.append("learned_motion")
        if self._learned_policy is not None and getattr(
            self._learned_policy, "trained", False
        ):
            parts.append("learned_policy")
        if not parts:
            return "expert_only"
        return "expert+" + "+".join(parts)

    def decide(self, observation: MissionObservation) -> MissionDecision:
        started = time.perf_counter()
        features = observation.features
        recommendation = self._policy.decide(features)
        situation = self._classifier.classify(features)
        if (
            self._learned_situation is not None
            and getattr(self._learned_situation, "trained", False)
        ):
            label, confidence = self._learned_situation.predict(features)  # type: ignore[attr-defined]
            with suppress(ValueError):
                situation = Situation(label)
            if situation.value != label:
                situation = self._classifier.classify(features)
        else:
            confidence = recommendation.confidence
        if self._learned_policy is not None and getattr(self._learned_policy, "trained", False):
            label, policy_confidence = self._learned_policy.predict(features)  # type: ignore[attr-defined]
            with suppress(ValueError):
                recommendation = self._policy.safety.approve(
                    MissionAction(label),
                    policy_confidence,
                    "learned_policy",
                    features.timestamp_s,
                )
        prediction = (
            self._predictor.predict(features, self._prediction_horizon_s)
            if features.detected or features.time_since_detection_s > 0
            else None
        )
        if (
            self._learned_motion is not None
            and getattr(self._learned_motion, "trained", False)
            and prediction is not None
        ):
            dx, dy, ux, uy = self._learned_motion.predict(features)  # type: ignore[attr-defined]
            prediction = MotionPrediction(
                mean_x_px=dx,
                mean_y_px=dy,
                uncertainty_x_px=ux,
                uncertainty_y_px=uy,
                horizon_s=self._prediction_horizon_s,
                method="learned_motion",
            )
        if (time.perf_counter() - started) * 1000.0 > self._max_latency_ms:
            recommendation = SafeRecommendation(
                action=MissionAction.HOLD,
                confidence=0.0,
                approved=False,
                fallback=MissionAction.HOLD,
                reason="ai_timeout",
                timestamp_s=features.timestamp_s,
            )
        return MissionDecision(
            action=recommendation.action,
            situation=situation,
            confidence=min(recommendation.confidence, confidence),
            prediction=prediction,
            reason=recommendation.reason,
            timestamp_s=features.timestamp_s,
            safety=recommendation,
        )


class MissionDecisionExecutor:
    """Applies only validated high-level modes; never writes camera state."""

    def __init__(self, stale_timeout_s: float = 0.5) -> None:
        if stale_timeout_s <= 0:
            raise ValueError("stale_timeout_s must be positive")
        self._stale_timeout_s = stale_timeout_s

    def validate(self, decision: MissionDecision, now_s: float) -> MissionAction:
        age = now_s - decision.timestamp_s
        if age < 0 or age > self._stale_timeout_s or not decision.safety.approved:
            return MissionAction.HOLD
        return decision.action


class SafetyEnvelope:
    """Validates recommendations and clamps actuator-facing values."""

    def __init__(self, limits: SafetyLimits | None = None) -> None:
        self.limits = limits or SafetyLimits()

    def approve(
        self,
        action: MissionAction,
        confidence: float,
        reason: str,
        timestamp_s: float,
        observation_age_s: float = 0.0,
    ) -> SafeRecommendation:
        valid_confidence = math.isfinite(confidence) and 0.0 <= confidence <= 1.0
        approved = valid_confidence and math.isfinite(timestamp_s)
        fallback = None
        if observation_age_s > self.limits.stale_timeout_s:
            approved = False
            fallback = MissionAction.HOLD
            reason = "observation_stale"
        if not approved and fallback is None:
            fallback = MissionAction.HOLD
        return SafeRecommendation(
            action=action if approved else fallback,
            confidence=min(max(confidence, 0.0), 1.0) if math.isfinite(confidence) else 0.0,
            approved=approved,
            fallback=fallback,
            reason=reason,
            timestamp_s=timestamp_s,
        )

    def clamp_rates(self, pan_rate_deg_s: float, tilt_rate_deg_s: float) -> tuple[float, float]:
        return (
            max(
                -self.limits.max_pan_rate_deg_s,
                min(self.limits.max_pan_rate_deg_s, pan_rate_deg_s),
            ),
            max(
                -self.limits.max_tilt_rate_deg_s,
                min(self.limits.max_tilt_rate_deg_s, tilt_rate_deg_s),
            ),
        )


class ExpertPolicy:
    """Interpretable policy baseline for future learned-policy comparison."""

    def __init__(
        self,
        classifier: SituationClassifier | None = None,
        safety: SafetyEnvelope | None = None,
    ) -> None:
        self._classifier = classifier or SituationClassifier()
        self._safety = safety or SafetyEnvelope()

    @property
    def safety(self) -> SafetyEnvelope:
        return self._safety

    def decide(self, features: ObservationFeatures) -> SafeRecommendation:
        situation = self._classifier.classify(features)
        if situation == Situation.REACQUISITION:
            action, reason = MissionAction.REACQUIRE, "detection_missing_after_prior_observation"
        elif situation == Situation.TARGET_LOST:
            action, reason = MissionAction.LOCAL_SEARCH, "target_not_observed"
        elif situation == Situation.LOW_CONFIDENCE:
            action, reason = MissionAction.RUN_HYBRID, "low_observation_confidence"
        elif situation == Situation.HIGH_NOISE:
            action, reason = MissionAction.TRACK_PREDICTIVE, "innovation_exceeds_uncertainty"
        elif situation == Situation.FAST_TARGET_MOTION:
            action, reason = MissionAction.TRACK_PREDICTIVE, "high_target_velocity"
        elif situation == Situation.EDGE_OF_FOV:
            action, reason = MissionAction.USE_ROI, "target_near_fov_boundary"
        elif situation == Situation.DEGRADING_TRACK:
            action, reason = MissionAction.TRACK_PREDICTIVE, "tracking_quality_degrading"
        elif situation == Situation.PREDICTION_UNCERTAIN:
            action, reason = MissionAction.TRACK_PREDICTIVE, "high_prediction_uncertainty"
        elif situation == Situation.RECOVERY:
            action, reason = MissionAction.REACQUIRE, "recovering_from_loss"
        else:
            action, reason = MissionAction.USE_ROI, "stable_observation"
        confidence = min(1.0, max(0.0, features.confidence))
        return self._safety.approve(action, confidence, reason, features.timestamp_s)


class DecisionLogger:
    """Bounded JSONL logger for explainable policy decisions."""

    def __init__(self, path: str | Path, max_records: int = 10000) -> None:
        if max_records <= 0:
            raise ValueError("max_records must be positive")
        self._path = Path(path)
        self._max_records = max_records
        self._records = 0

    def log(self, features: ObservationFeatures, decision: SafeRecommendation) -> None:
        if self._records >= self._max_records:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "logged_at": time.time(),
            "features": asdict(features),
            "decision": asdict(decision),
        }
        record["decision"]["action"] = decision.action.value
        if decision.fallback is not None:
            record["decision"]["fallback"] = decision.fallback.value
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._records += 1


def policy_dataset_row(
    features: ObservationFeatures,
    decision: SafeRecommendation,
) -> dict[str, Any]:
    """Create a ground-truth-free policy training row."""
    row = asdict(features)
    row.update({"action": decision.action.value, "policy_confidence": decision.confidence})
    return row
