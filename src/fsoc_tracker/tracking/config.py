"""Tracker configuration.

Strongly typed Pydantic model for all tracking parameters.
Defaults align with SIH26169 reference conditions.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FilterType(str, Enum):
    KALMAN_2D_CV = "kalman_2d_cv"


class AssociationMethod(str, Enum):
    NEAREST_NEIGHBOR = "nearest_neighbor"
    MAHALANOBIS = "mahalanobis"


class TimestampGapPolicy(str, Enum):
    REJECT = "reject"
    CLAMP = "clamp"
    RESET = "reset"


class TrackerConfig(BaseModel):
    """Configuration for the temporal tracking subsystem.

    Reference from SIH26169 PS:
        - acquisition <= 2 sec
        - re-acquisition <= 1 sec
        - tracking error <= 10 px
        - target loss < 5%
        - processing >= 20 FPS
    """

    filter_type: FilterType = FilterType.KALMAN_2D_CV

    process_noise_pos: float = Field(default=20.0, gt=0,
        description="Process noise for position (px^2/s^2). Higher = filter trusts measurements more.")
    process_noise_vel: float = Field(default=40.0, gt=0,
        description="Process noise for velocity (px^2/s^4). Higher = filter adapts faster to velocity changes.")

    measurement_noise_x: float = Field(default=5.0, gt=0,
        description="Measurement noise variance for x (px^2). Reflects detector precision.")
    measurement_noise_y: float = Field(default=5.0, gt=0,
        description="Measurement noise variance for y (px^2). Reflects detector precision.")

    initial_position_uncertainty: float = Field(default=100.0, gt=0,
        description="Initial position covariance (px^2). Large = uncertain initial position.")
    initial_velocity_uncertainty: float = Field(default=500.0, gt=0,
        description="Initial velocity covariance (px/s)^2. Large = uncertain initial velocity.")

    association_method: AssociationMethod = AssociationMethod.NEAREST_NEIGHBOR
    association_gate_px: float = Field(default=80.0, gt=0,
        description="Maximum Euclidean distance (px) for valid association.")
    association_gate_mahal: float = Field(default=9.21, gt=0,
        description="Mahalanobis distance threshold (chi-squared, df=2, p=0.01). "
        "Used when association_method=mahalanobis (recommended for "
        "glint-heavy fields; see benchmark --assoc-method).")
    association_gate_floor_px: float = Field(default=15.0, ge=0.0,
        description="Euclidean floor under Mahalanobis gating: very close "
        "candidates are always accepted (protects early-track lock).")

    minimum_detection_confidence: float = Field(default=0.2, ge=0, le=1,
        description="Minimum confidence to consider a detection valid.")

    acquisition_min_consecutive_hits: int = Field(default=3, ge=1,
        description="Minimum consecutive valid detections before transitioning to TRACKING.")
    acquisition_timeout_s: float = Field(default=2.0, gt=0,
        description="Maximum duration (s) in ACQUIRING state before falling back to SEARCHING.")

    max_prediction_duration_s: float = Field(default=1.0, gt=0,
        description="Maximum duration (s) to continue predicting without a measurement before declaring LOST.")
    reacquisition_timeout_s: float = Field(default=1.0, gt=0,
        description="Maximum duration (s) in REACQUIRING before falling back to SEARCHING.")

    lock_quality_threshold: float = Field(default=0.5, ge=0, le=1,
        description="Minimum quality score to declare LOCKED.")

    timestamp_gap_policy: TimestampGapPolicy = TimestampGapPolicy.CLAMP
    max_timestamp_gap_s: float = Field(default=5.0, gt=0,
        description="Maximum allowed gap (s) before applying gap policy.")

    def build_process_noise_matrix(self, dt: float) -> list[list[float]]:
        """Build 4x4 process noise covariance matrix Q for dt seconds.

        Constant-velocity model:
            Q = G * G^T * sigma^2
        where G is the discrete-time noise input matrix.
        """
        q_pos = self.process_noise_pos
        q_vel = self.process_noise_vel
        dt2 = dt * dt / 2.0
        return [
            [dt2*dt2 * q_pos, 0,                 dt2 * q_pos,  0],
            [0,                 dt2*dt2 * q_pos,  0,            dt2 * q_pos],
            [dt2 * q_pos,       0,                dt * q_vel,   0],
            [0,                 dt2 * q_pos,       0,           dt * q_vel],
        ]

    def build_measurement_noise_matrix(self) -> list[list[float]]:
        """Build 2x2 measurement noise covariance matrix R."""
        return [
            [self.measurement_noise_x, 0],
            [0, self.measurement_noise_y],
        ]
