"""Advanced system configuration.

Central configuration for all Stage 13 adaptive/advanced features.
Every advanced feature is independently switchable for ablation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QualityAnalysisConfig(BaseModel):
    enabled: bool = True
    min_brightness: float = 10.0
    max_brightness: float = 240.0
    min_contrast: float = 15.0
    max_noise: float = 30.0


class AdaptivePerceptionConfig(BaseModel):
    enabled: bool = True
    use_roi_when_tracking: bool = True
    roi_expand_factor_high_uncertainty: float = 2.5
    roi_expand_factor_moderate: float = 1.5
    enhanced_denoise_on_degraded: bool = True
    adaptive_threshold_on_degraded: bool = True


class ConfidenceFusionConfig(BaseModel):
    enabled: bool = True
    method: str = "weighted_score"
    w_classical: float = 0.35
    w_ai: float = 0.35
    w_tracker: float = 0.20
    w_quality: float = 0.10
    min_fusion_confidence: float = 0.2
    association_distance_limit: float = 50.0


class UncertaintyConfig(BaseModel):
    enabled: bool = True
    position_scale_factor: float = 1.0
    confidence_weight: float = 0.20
    quality_weight: float = 0.15


class AdaptiveKalmanConfig(BaseModel):
    enabled: bool = True
    q_scale_min: float = 0.3
    q_scale_max: float = 5.0
    r_scale_min: float = 0.5
    r_scale_max: float = 10.0
    maneuver_q_scale: float = 3.0
    uncertainty_r_scale: float = 2.0
    smoothing_alpha: float = 0.3


class ManeuverDetectionConfig(BaseModel):
    enabled: bool = True
    innovation_threshold: float = 15.0
    sustained_threshold: int = 3
    velocity_change_threshold: float = 50.0
    unpredictable_threshold: float = 40.0


class CoarseToFineConfig(BaseModel):
    enabled: bool = True
    method: str = "intensity_weighted"
    roi_half_size: int = 15
    background_subtraction: bool = True
    psf_sigma: float = 2.0
    max_refinement_delta: float = 5.0


class SearchConfig(BaseModel):
    enabled: bool = True
    initial_roi_radius_px: float = 50.0
    expanded_roi_radius_px: float = 150.0
    max_roi_radius_px: float = 300.0
    structured_pattern: str = "spiral"
    phase_timeout_frames: int = 30
    velocity_projection_s: float = 0.3


class ReacquisitionConfig(BaseModel):
    enabled: bool = True
    min_temporal_stability: int = 2
    require_velocity_consistency: bool = True
    require_size_consistency: bool = True
    reacquiring_to_tracking_hits: int = 3


class AdaptiveControllerConfig(BaseModel):
    enabled: bool = True
    low_error_threshold: float = 5.0
    medium_error_threshold: float = 20.0
    high_error_threshold: float = 50.0
    feed_forward_enabled: bool = True
    feed_forward_gain: float = 0.15
    anti_oscillation_enabled: bool = True
    oscillation_sign_changes: int = 4
    uncertainty_scale_enabled: bool = True


class GainSchedulingConfig(BaseModel):
    enabled: bool = True
    low_kp_scale: float = 0.7
    low_kd_scale: float = 0.5
    medium_kp_scale: float = 1.0
    medium_kd_scale: float = 1.0
    high_kp_scale: float = 1.5
    high_kd_scale: float = 1.5


class FeedForwardConfig(BaseModel):
    enabled: bool = True
    gain: float = 0.15
    max_feed_forward: float = 1.0


class AISchedulingConfig(BaseModel):
    enabled: bool = False
    mode: str = "classical_between_ai"
    ai_frame_interval: int = 5
    adaptive_interval: bool = True


class DynamicROIConfig(BaseModel):
    enabled: bool = True
    min_roi_size: int = 30
    max_roi_size: int = 200
    uncertainty_expansion_rate: float = 1.5
    velocity_expansion_rate: float = 0.1


class ModelCascadeConfig(BaseModel):
    enabled: bool = False
    fast_model: str = "classical"
    slow_model: str = "ai"
    confidence_threshold: float = 0.5


class HardCaseCaptureConfig(BaseModel):
    enabled: bool = False
    save_on_high_error: bool = True
    error_threshold_px: float = 30.0
    save_on_false_positive: bool = True
    save_on_track_loss: bool = True
    max_captures: int = 100


class TuningConfig(BaseModel):
    enabled: bool = False
    objective_weights: dict = Field(default_factory=lambda: {
        "rmse": 0.3,
        "settling_time": 0.2,
        "overshoot": 0.2,
        "control_effort": 0.15,
        "loss_penalty": 0.15,
    })


class AdvancedConfig(BaseModel):
    """Master configuration for all Stage 13 advanced features.

    Every feature is independently switchable for ablation testing.
    """

    quality_analysis: QualityAnalysisConfig = Field(default_factory=QualityAnalysisConfig)
    adaptive_perception: AdaptivePerceptionConfig = Field(default_factory=AdaptivePerceptionConfig)
    confidence_fusion: ConfidenceFusionConfig = Field(default_factory=ConfidenceFusionConfig)
    uncertainty: UncertaintyConfig = Field(default_factory=UncertaintyConfig)
    adaptive_kalman: AdaptiveKalmanConfig = Field(default_factory=AdaptiveKalmanConfig)
    maneuver_detection: ManeuverDetectionConfig = Field(default_factory=ManeuverDetectionConfig)
    coarse_to_fine: CoarseToFineConfig = Field(default_factory=CoarseToFineConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    reacquisition: ReacquisitionConfig = Field(default_factory=ReacquisitionConfig)
    adaptive_controller: AdaptiveControllerConfig = Field(default_factory=AdaptiveControllerConfig)
    gain_scheduling: GainSchedulingConfig = Field(default_factory=GainSchedulingConfig)
    feed_forward: FeedForwardConfig = Field(default_factory=FeedForwardConfig)
    ai_scheduling: AISchedulingConfig = Field(default_factory=AISchedulingConfig)
    dynamic_roi: DynamicROIConfig = Field(default_factory=DynamicROIConfig)
    model_cascade: ModelCascadeConfig = Field(default_factory=ModelCascadeConfig)
    hard_case_capture: HardCaseCaptureConfig = Field(default_factory=HardCaseCaptureConfig)
    tuning: TuningConfig = Field(default_factory=TuningConfig)

    def feature_flags(self) -> dict[str, bool]:
        """Return dict of feature name -> enabled status."""
        return {
            "quality_analysis": self.quality_analysis.enabled,
            "adaptive_perception": self.adaptive_perception.enabled,
            "confidence_fusion": self.confidence_fusion.enabled,
            "uncertainty": self.uncertainty.enabled,
            "adaptive_kalman": self.adaptive_kalman.enabled,
            "maneuver_detection": self.maneuver_detection.enabled,
            "coarse_to_fine": self.coarse_to_fine.enabled,
            "search": self.search.enabled,
            "reacquisition": self.reacquisition.enabled,
            "adaptive_controller": self.adaptive_controller.enabled,
            "gain_scheduling": self.gain_scheduling.enabled,
            "feed_forward": self.feed_forward.enabled,
            "ai_scheduling": self.ai_scheduling.enabled,
            "dynamic_roi": self.dynamic_roi.enabled,
            "model_cascade": self.model_cascade.enabled,
            "hard_case_capture": self.hard_case_capture.enabled,
        }
