"""Benchmark method registry — only genuinely available methods.

Five evaluation methods are defined for the PS metrics. Whether a
learned method may run is probed at runtime from its trained
artifacts, with label validation against the current enums:

- learned motion (temporal): linear future-displacement weights.
- learned policy: classifier weights whose labels must exactly match
  the current MissionAction set.
- learned situation is NOT offered: the saved situation weights were
  trained on a stale 7-label set while the code defines 10
  situations, so the expert classifier is always used instead.
- the GRU temporal checkpoint is experimental (toy sample count) and
  is NOT used by any benchmark method.

A method whose weights are missing, untrained, or stale is reported
NOT AVAILABLE and is never executed with a fabricated stand-in.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

METHOD_CLASSICAL_PID = "classical_pid"
METHOD_KALMAN_EXPERT = "kalman_expert"
METHOD_LEARNED_TEMPORAL_EXPERT = "learned_temporal_expert"
METHOD_LEARNED_TEMPORAL_LEARNED_POLICY = "learned_temporal_learned_policy"
METHOD_FULL_AI_MISSION = "full_ai_mission"

METHOD_ORDER: tuple[str, ...] = (
    METHOD_CLASSICAL_PID,
    METHOD_KALMAN_EXPERT,
    METHOD_LEARNED_TEMPORAL_EXPERT,
    METHOD_LEARNED_TEMPORAL_LEARNED_POLICY,
    METHOD_FULL_AI_MISSION,
)

METHOD_LABELS: dict[str, str] = {
    METHOD_CLASSICAL_PID: "CLASSICAL + PID",
    METHOD_KALMAN_EXPERT: "KALMAN + EXPERT",
    METHOD_LEARNED_TEMPORAL_EXPERT: "LEARNED TEMPORAL + EXPERT",
    METHOD_LEARNED_TEMPORAL_LEARNED_POLICY: "LEARNED TEMPORAL + LEARNED POLICY",
    METHOD_FULL_AI_MISSION: "FULL AI MISSION",
}

METHOD_DESCRIPTIONS: dict[str, str] = {
    METHOD_CLASSICAL_PID: (
        "Classical detection centroid drives PID directly (no Kalman filter, no AI)."
    ),
    METHOD_KALMAN_EXPERT: (
        "Kalman-filtered track drives PID (engineered stack, no learned components)."
    ),
    METHOD_LEARNED_TEMPORAL_EXPERT: (
        "Kalman + PID with a trained linear motion model feeding ROI, predictive "
        "control, and search via the mission brain (expert policy)."
    ),
    METHOD_LEARNED_TEMPORAL_LEARNED_POLICY: (
        "Learned motion + trained policy classifier selecting safety-gated "
        "mission actions."
    ),
    METHOD_FULL_AI_MISSION: (
        "Production TrackingPipeline with the full adaptive stack (mission brain, "
        "adaptive ROI/Kalman/controller, failure predictor, search)."
    ),
}

MOTION_FILENAME = "motion-v2.npz"
POLICY_FILENAME = "policy-v2.npz"
EXPERIMENT_FILENAME = "experiment.json"


class MethodUnavailableError(RuntimeError):
    """Raised when a benchmark method has no genuine implementation."""


@dataclass
class MethodAvailability:
    method: str
    available: bool
    reason: str
    provenance: dict[str, Any] = field(default_factory=dict)


def model_dir() -> Path:
    """Directory holding the trained mission artifacts.

    Overridable with FSOC_BENCHMARK_MODEL_DIR (used by tests).
    """
    override = os.environ.get("FSOC_BENCHMARK_MODEL_DIR", "").strip()
    if override:
        return Path(override)
    return Path("artifacts/models/mission-v3")


def _load_motion(directory: Path) -> tuple[Any | None, dict[str, Any]]:
    from fsoc_tracker.ai.learned import LearnedMotionModel

    path = directory / MOTION_FILENAME
    if not path.exists():
        return None, {"motion_weights": None}
    try:
        model = LearnedMotionModel.load(path)
    except Exception as exc:
        return None, {"motion_weights": str(path), "motion_error": str(exc)}
    if not model.trained:
        return None, {"motion_weights": str(path), "motion_trained": False}
    return model, {"motion_weights": str(path), "motion_version": model.version}


def _load_policy(directory: Path) -> tuple[Any | None, dict[str, Any]]:
    from fsoc_tracker.ai.learned import LearnedFeatureClassifier
    from fsoc_tracker.ai.mission import MissionAction

    path = directory / POLICY_FILENAME
    if not path.exists():
        return None, {"policy_weights": None}
    try:
        model = LearnedFeatureClassifier.load(path)
    except Exception as exc:
        return None, {"policy_weights": str(path), "policy_error": str(exc)}
    if not model.trained:
        return None, {"policy_weights": str(path), "policy_trained": False}
    expected = {a.value for a in MissionAction}
    actual = set(model.labels)
    if actual != expected:
        return None, {
            "policy_weights": str(path),
            "policy_trained": True,
            "policy_labels": sorted(actual),
            "policy_labels_stale": True,
        }
    return model, {"policy_weights": str(path), "policy_labels": sorted(actual)}


def _experiment_provenance(directory: Path) -> dict[str, Any]:
    path = directory / EXPERIMENT_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        "experiment_seed": data.get("seed"),
        "experiment_train_samples": data.get("train_samples"),
        "experiment_motion_test_rmse": (data.get("motion") or {}).get("test_rmse_euclidean"),
        "experiment_policy_test_accuracy": (data.get("policy") or {}).get("test_accuracy"),
    }


def check_method_availability(method: str, directory: Path | None = None) -> MethodAvailability:
    """Probe whether a benchmark method can genuinely run."""
    directory = directory or model_dir()
    if method not in METHOD_ORDER:
        return MethodAvailability(method, False, f"unknown method: {method}")

    if method in (METHOD_CLASSICAL_PID, METHOD_KALMAN_EXPERT, METHOD_FULL_AI_MISSION):
        # Engineered / production-stack methods need no learned weights.
        # FULL AI MISSION additionally uses learned models when valid
        # (see load_method_components).
        return MethodAvailability(
            method, True, "engineered stack, no learned weights required", {}
        )

    if method == METHOD_LEARNED_TEMPORAL_EXPERT:
        motion, prov = _load_motion(directory)
        if motion is None:
            return MethodAvailability(
                method, False,
                f"learned motion weights unavailable ({prov.get('motion_error', 'missing')})",
                prov,
            )
        prov.update(_experiment_provenance(directory))
        return MethodAvailability(method, True, "trained motion weights loaded", prov)

    # METHOD_LEARNED_TEMPORAL_LEARNED_POLICY
    motion, motion_prov = _load_motion(directory)
    policy, policy_prov = _load_policy(directory)
    prov = {**motion_prov, **policy_prov}
    if motion is None:
        return MethodAvailability(
            method, False,
            f"learned motion weights unavailable ({motion_prov.get('motion_error', 'missing')})",
            prov,
        )
    if policy is None:
        if policy_prov.get("policy_labels_stale"):
            reason = "learned policy trained on stale labels — NOT AVAILABLE (not fabricated)"
        else:
            reason = f"learned policy unavailable ({policy_prov.get('policy_error', 'missing')})"
        return MethodAvailability(method, False, reason, prov)
    prov.update(_experiment_provenance(directory))
    return MethodAvailability(method, True, "trained motion + policy weights loaded", prov)


def load_method_components(method: str, directory: Path | None = None) -> dict[str, Any]:
    """Load the learned components for a method, or raise.

    Raises:
        MethodUnavailableError: if any required artifact is missing,
            untrained, or stale. Callers must surface this as
            NOT AVAILABLE instead of substituting a stand-in.
    """
    availability = check_method_availability(method, directory)
    if not availability.available:
        raise MethodUnavailableError(
            f"Benchmark method '{METHOD_LABELS.get(method, method)}' NOT AVAILABLE: "
            f"{availability.reason}"
        )
    directory = directory or model_dir()
    components: dict[str, Any] = {"provenance": availability.provenance}
    if method in (METHOD_LEARNED_TEMPORAL_EXPERT, METHOD_LEARNED_TEMPORAL_LEARNED_POLICY,
                  METHOD_FULL_AI_MISSION):
        motion, _ = _load_motion(directory)
        components["learned_motion"] = motion
    if method in (METHOD_LEARNED_TEMPORAL_LEARNED_POLICY, METHOD_FULL_AI_MISSION):
        policy, _ = _load_policy(directory)
        # FULL AI MISSION tolerates a stale policy (expert fallback);
        # the dedicated policy method does not.
        if policy is None and method == METHOD_FULL_AI_MISSION:
            components["learned_policy"] = None
        else:
            components["learned_policy"] = policy
    return components
