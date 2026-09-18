"""AI Beacon Perception subsystem — project-specific small-target detection.

Architecture:
    Input Frame → Preprocessing → Tiny CNN → Heatmap → Center + Confidence → PerceptionResult

The AI backend is specialized for SMALL, BRIGHT, LOCALIZED optical beacon
targets (5-20 pixels) under disturbances. It uses a heatmap-based center
prediction approach for accurate centroid localization.

Modules:
    config     — AIModelConfig, AIBackendType, TrainingConfig
    model      — BeaconCNN (tiny heatmap-based detector)
    dataset    — Synthetic dataset generation from simulator
    training   — Training loop and loss functions
    inference  — AIBeaconDetector (PerceptionEngine implementation)
    hybrid     — HybridBeaconDetector (classical + AI fusion)
    export     — ONNX export and model loading
    benchmark  — AI vs classical benchmark framework
"""

from fsoc_tracker.ai.config import AIBackendType, AIModelConfig, TrainingConfig
from fsoc_tracker.ai.hybrid import HybridBeaconDetector
from fsoc_tracker.ai.inference import AIBeaconDetector
from fsoc_tracker.ai.learned import (
    LearnedFeatureClassifier,
    LearnedMotionModel,
    MotionModelMetrics,
    observation_vector,
)
from fsoc_tracker.ai.mission import (
    AIMissionBrain,
    DecisionLogger,
    ExpertPolicy,
    MissionAction,
    MissionDecision,
    MissionDecisionExecutor,
    MissionObservation,
    MotionPredictor,
    ObservationFeatures,
    SafetyEnvelope,
    SafetyLimits,
    Situation,
    SituationClassifier,
)
from fsoc_tracker.ai.neural import (
    build_temporal_predictor,
    build_visual_heatmap_model,
    torch_backend_available,
)

__all__ = [
    "AIModelConfig",
    "AIBackendType",
    "TrainingConfig",
    "AIBeaconDetector",
    "HybridBeaconDetector",
    "DecisionLogger",
    "AIMissionBrain",
    "ExpertPolicy",
    "MissionDecision",
    "MissionDecisionExecutor",
    "MissionObservation",
    "MissionAction",
    "MotionPredictor",
    "ObservationFeatures",
    "SafetyEnvelope",
    "SafetyLimits",
    "Situation",
    "SituationClassifier",
    "LearnedFeatureClassifier",
    "LearnedMotionModel",
    "MotionModelMetrics",
    "observation_vector",
    "build_temporal_predictor",
    "build_visual_heatmap_model",
    "torch_backend_available",
]
