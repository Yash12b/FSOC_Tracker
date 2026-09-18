"""Explainability layer for AI mission brain decisions.

Produces human-readable explanations of why each decision was made,
including the driving features, risk scores, and situation classification.

Integrates with DecisionLogger and provides post-hoc analysis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from fsoc_tracker.ai.mission import (
    MissionAction,
    MissionDecision,
    ObservationFeatures,
    Situation,
)


@dataclass
class FeatureContribution:
    """How much a feature contributed to the decision."""
    feature_name: str
    value: float
    normal_range: tuple[float, float]
    contribution: float  # -1.0 to 1.0
    explanation: str


@dataclass
class DecisionExplanation:
    """Complete explanation of a single AI decision."""
    timestamp_s: float
    situation: str
    action: str
    confidence: float
    failure_risk: float
    approved: bool
    reason: str
    feature_contributions: list[FeatureContribution]
    summary: str
    raw_features: dict[str, float] = field(default_factory=dict)


class ExplainabilityEngine:
    """Generates human-readable explanations for AI decisions.

    Maps feature values to natural language explanations and identifies
    the key drivers of each decision.
    """

    FEATURE_RANGES = {
        "confidence": (0.0, 1.0),
        "residual_px": (0.0, 50.0),
        "uncertainty_x_px": (0.0, 30.0),
        "uncertainty_y_px": (0.0, 30.0),
        "velocity_x_px_s": (-200.0, 200.0),
        "velocity_y_px_s": (-200.0, 200.0),
        "distance_from_center_px": (0.0, 400.0),
        "time_since_detection_s": (0.0, 2.0),
        "processing_fps": (10.0, 120.0),
        "source_fps": (15.0, 60.0),
    }

    SITUATION_DESCRIPTIONS = {
        Situation.NORMAL_TRACKING: "Target is being tracked normally",
        Situation.FAST_TARGET_MOTION: "Target is moving faster than expected",
        Situation.HIGH_NOISE: "Measurement noise exceeds expected uncertainty",
        Situation.EDGE_OF_FOV: "Target is near the field-of-view boundary",
        Situation.DEGRADING_TRACK: "Tracking quality is degrading",
        Situation.LOW_CONFIDENCE: "Detection confidence is below threshold",
        Situation.PREDICTION_UNCERTAIN: "Prediction uncertainty is high",
        Situation.TARGET_LOST: "No target detected in current frame",
        Situation.REACQUISITION: "Attempting to reacquire previously lost target",
        Situation.RECOVERY: "Recovering from target loss",
    }

    ACTION_DESCRIPTIONS = {
        MissionAction.TRACK: "Continue standard tracking",
        MissionAction.TRACK_PREDICTIVE: "Use prediction to filter noisy measurements",
        MissionAction.USE_ROI: "Narrow perception to region of interest",
        MissionAction.USE_FULL_FRAME: "Search full frame for target",
        MissionAction.RUN_CLASSICAL: "Switch to classical (CPU-only) detector",
        MissionAction.RUN_HYBRID: "Run both classical and AI detectors",
        MissionAction.LOCAL_SEARCH: "Search nearby region for target",
        MissionAction.GLOBAL_SEARCH: "Search entire frame for target",
        MissionAction.REACQUIRE: "Reacquire target using predicted position",
        MissionAction.HOLD: "Hold current camera position",
        MissionAction.SAFE_STOP: "Emergency stop — safety limit exceeded",
    }

    def explain(
        self,
        features: ObservationFeatures,
        decision: MissionDecision,
        failure_risk: float = 0.0,
    ) -> DecisionExplanation:
        """Generate a complete explanation for a decision."""
        contributions = self._compute_contributions(features, failure_risk)
        summary = self._generate_summary(features, decision, failure_risk, contributions)

        raw = {
            "confidence": features.confidence,
            "residual_px": features.residual_px,
            "uncertainty_x_px": features.uncertainty_x_px,
            "uncertainty_y_px": features.uncertainty_y_px,
            "velocity_x_px_s": features.velocity_x_px_s,
            "velocity_y_px_s": features.velocity_y_px_s,
            "distance_from_center_px": features.distance_from_center_px,
            "time_since_detection_s": features.time_since_detection_s,
            "processing_fps": features.processing_fps,
            "source_fps": features.source_fps,
        }

        return DecisionExplanation(
            timestamp_s=features.timestamp_s,
            situation=decision.situation.value,
            action=decision.action.value,
            confidence=decision.confidence,
            failure_risk=failure_risk,
            approved=decision.safety.approved,
            reason=decision.reason,
            feature_contributions=contributions,
            summary=summary,
            raw_features=raw,
        )

    def _compute_contributions(
        self, features: ObservationFeatures, failure_risk: float
    ) -> list[FeatureContribution]:
        """Compute per-feature contributions to the decision."""
        contributions = []

        conf_status = "normal" if features.confidence > 0.5 else ("low" if features.confidence > 0.2 else "very_low")
        conf_contrib = (features.confidence - 0.5) * 2.0
        contributions.append(FeatureContribution(
            feature_name="confidence",
            value=features.confidence,
            normal_range=(0.5, 1.0),
            contribution=conf_contrib,
            explanation=f"Detection confidence is {conf_status} ({features.confidence:.2f})",
        ))

        if features.residual_px > 15:
            res_contrib = -1.0 + min(15.0 / features.residual_px, 1.0)
            contributions.append(FeatureContribution(
                feature_name="residual_px",
                value=features.residual_px,
                normal_range=(0.0, 10.0),
                contribution=res_contrib,
                explanation=f"Measurement residual is high ({features.residual_px:.1f}px)",
            ))

        unc = max(features.uncertainty_x_px, features.uncertainty_y_px)
        if unc > 10:
            unc_contrib = -1.0 + min(10.0 / unc, 1.0)
            contributions.append(FeatureContribution(
                feature_name="uncertainty",
                value=unc,
                normal_range=(0.0, 10.0),
                contribution=unc_contrib,
                explanation=f"Position uncertainty is elevated ({unc:.1f}px)",
            ))

        vel = max(abs(features.velocity_x_px_s), abs(features.velocity_y_px_s))
        if vel > 100:
            vel_contrib = -0.5
            contributions.append(FeatureContribution(
                feature_name="velocity",
                value=vel,
                normal_range=(0.0, 50.0),
                contribution=vel_contrib,
                explanation=f"Target velocity is high ({vel:.0f}px/s)",
            ))

        if features.time_since_detection_s > 0.1:
            tld_contrib = -min(features.time_since_detection_s / 1.0, 1.0)
            contributions.append(FeatureContribution(
                feature_name="time_since_detection",
                value=features.time_since_detection_s,
                normal_range=(0.0, 0.1),
                contribution=tld_contrib,
                explanation=f"No detection for {features.time_since_detection_s:.2f}s",
            ))

        if failure_risk > 0.3:
            fr_contrib = -failure_risk
            contributions.append(FeatureContribution(
                feature_name="failure_risk",
                value=failure_risk,
                normal_range=(0.0, 0.3),
                contribution=fr_contrib,
                explanation=f"Failure risk is elevated ({failure_risk:.2f})",
            ))

        return sorted(contributions, key=lambda c: abs(c.contribution), reverse=True)

    def _generate_summary(
        self,
        features: ObservationFeatures,
        decision: MissionDecision,
        failure_risk: float,
        contributions: list[FeatureContribution],
    ) -> str:
        """Generate a human-readable summary."""
        sit_desc = self.SITUATION_DESCRIPTIONS.get(
            decision.situation, decision.situation.value
        )
        act_desc = self.ACTION_DESCRIPTIONS.get(
            decision.action, decision.action.value
        )

        top_driver = ""
        if contributions:
            top_driver = f" Primary driver: {contributions[0].explanation}."

        approval = "approved" if decision.safety.approved else "rejected (safety)"

        return (
            f"{sit_desc}. Action: {act_desc} ({approval}). "
            f"Confidence={decision.confidence:.2f}, failure_risk={failure_risk:.2f}."
            f"{top_driver}"
        )

    def format_jsonl(self, explanation: DecisionExplanation) -> str:
        """Format explanation as JSONL for logging."""
        record = {
            "timestamp_s": explanation.timestamp_s,
            "situation": explanation.situation,
            "action": explanation.action,
            "confidence": round(explanation.confidence, 3),
            "failure_risk": round(explanation.failure_risk, 3),
            "approved": explanation.approved,
            "reason": explanation.reason,
            "summary": explanation.summary,
            "top_features": [
                {"name": c.feature_name, "value": round(c.value, 3), "contribution": round(c.contribution, 3)}
                for c in explanation.feature_contributions[:3]
            ],
        }
        return json.dumps(record, separators=(",", ":"))

    def save_explanations(
        self, explanations: list[DecisionExplanation], path: str | Path
    ) -> None:
        """Save explanations to JSONL file."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as f:
            for exp in explanations:
                f.write(self.format_jsonl(exp) + "\n")
