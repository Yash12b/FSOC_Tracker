"""KalmanTracker: main tracker class implementing temporal tracking.

Consumes Detection objects from any perception backend.
Produces TrackingState for the downstream controller.
Never uses ground truth.
"""

from __future__ import annotations

import math
from typing import Any


from fsoc_tracker.core.time import compute_dt
from fsoc_tracker.perception.models import BeaconDetection
from fsoc_tracker.tracking.association import associate_nearest
from fsoc_tracker.tracking.config import TrackerConfig
from fsoc_tracker.tracking.kalman import KalmanFilter2D
from fsoc_tracker.tracking.state import TrackEvent, TrackState, TrackingEvent, TrackingState
from fsoc_tracker.tracking.state_machine import TrackStateMachine


class KalmanTracker:
    """Kalman-filter-based temporal tracker.

    Usage::

        tracker = KalmanTracker(config)
        state = tracker.update(detections, timestamp_s)
        # state is TrackingState
    """

    def __init__(self, config: TrackerConfig | None = None) -> None:
        self._config = config or TrackerConfig()
        self._kf = KalmanFilter2D(self._config)
        self._sm = TrackStateMachine(track_id=0)

        self._track_id: int = 0
        self._track_start_time_s: float = 0.0
        self._last_update_time_s: float = 0.0
        self._last_measurement_time_s: float = 0.0

        self._consecutive_detections: int = 0
        self._consecutive_misses: int = 0
        self._total_detections: int = 0
        self._total_misses: int = 0

        self._acquisition_start_time_s: float = 0.0
        self._acquisition_success_time_s: float = 0.0

        self._loss_time_s: float = 0.0
        self._reacquisition_time_s: float = 0.0

        self._events: list[TrackingEvent] = []
        self._last_raw_detection: BeaconDetection | None = None
        self._has_measurement: bool = False

    @property
    def config(self) -> TrackerConfig:
        return self._config

    @property
    def state(self) -> TrackState:
        return self._sm.state

    @property
    def events(self) -> list[TrackingEvent]:
        return list(self._events)

    def update(
        self,
        detections: list[BeaconDetection],
        timestamp_s: float,
        frame_metadata: dict[str, Any] | None = None,
    ) -> TrackingState:
        """Process one frame of detections.

        Args:
            detections: List of detections from perception (may be empty).
            timestamp_s: Frame timestamp.
            frame_metadata: Optional metadata (frame_index, etc.).

        Returns:
            Current TrackingState after processing.
        """
        current_state = self._sm.state

        if frame_metadata:
            forbidden = (
                "ground_truth",
                "is_primary",
                "primary_beacon",
                "primary_beacon_id",
                "world_x",
                "world_y",
                "world_z",
            )
            for key in forbidden:
                if key in frame_metadata:
                    raise ValueError(
                        f"KalmanTracker must not receive simulator identity/truth "
                        f"({key!r}); pass detections only"
                    )

        # Filter valid detections
        valid_dets = [d for d in detections if d.detected and d.confidence >= self._config.minimum_detection_confidence]

        if current_state == TrackState.NO_TRACK:
            return self._handle_no_track(valid_dets, timestamp_s)

        # Compute dt
        dt = compute_dt(timestamp_s, self._last_update_time_s)
        if dt <= 0:
            # Duplicate/out-of-order timestamp: hold prediction (dt=0)
            # rather than jumping. Large positive gaps are handled by
            # the timestamp gap policy below.
            dt = 0.0

        # Check for timestamp gaps
        if timestamp_s - self._last_update_time_s > self._config.max_timestamp_gap_s:
            policy = self._config.timestamp_gap_policy
            if policy.value == "reset":
                self.reset(timestamp_s)
                return self._handle_no_track(valid_dets, timestamp_s)
            elif policy.value == "clamp":
                dt = min(dt, self._config.max_timestamp_gap_s)

        self._last_update_time_s = timestamp_s

        if current_state == TrackState.SEARCHING:
            return self._handle_searching(valid_dets, timestamp_s, dt)
        elif current_state == TrackState.ACQUIRING:
            return self._handle_acquiring(valid_dets, timestamp_s, dt)
        elif current_state == TrackState.TRACKING:
            return self._handle_tracking(valid_dets, timestamp_s, dt)
        elif current_state == TrackState.LOST:
            return self._handle_lost(valid_dets, timestamp_s, dt)
        elif current_state == TrackState.REACQUIRING:
            return self._handle_reacquiring(valid_dets, timestamp_s, dt)

        return self._build_state(timestamp_s, dt)

    def predict(self, timestamp_s: float) -> TrackingState:
        """Predict state without a measurement.

        Used when perception returns no data but the tracker should
        continue predicting.
        """
        if self._sm.state in (TrackState.TRACKING, TrackState.LOST, TrackState.REACQUIRING):
            dt = compute_dt(timestamp_s, self._last_update_time_s)
            if dt > 0:
                self._kf.predict(dt)
                self._last_update_time_s = timestamp_s
        return self._build_state(timestamp_s)

    def get_state(self) -> TrackingState:
        """Get current tracking state."""
        return self._build_state(self._last_update_time_s)

    def reset(self, timestamp_s: float = 0.0) -> None:
        """Reset tracker to initial state."""
        self._kf.reset()
        self._sm.reset(timestamp_s)

        self._track_start_time_s = 0.0
        self._last_update_time_s = timestamp_s
        self._last_measurement_time_s = timestamp_s

        self._consecutive_detections = 0
        self._consecutive_misses = 0
        self._total_detections = 0
        self._total_misses = 0

        self._acquisition_start_time_s = 0.0
        self._acquisition_success_time_s = 0.0

        self._loss_time_s = 0.0
        self._reacquisition_time_s = 0.0

        self._events.clear()
        self._last_raw_detection = None
        self._has_measurement = False

    def _handle_no_track(
        self, detections: list[BeaconDetection], timestamp_s: float,
    ) -> TrackingState:
        """Handle state NO_TRACK."""
        if detections:
            best = self._select_best(detections)
            self._start_track(best, timestamp_s)

            # Check if we can immediately go to TRACKING
            if self._config.acquisition_min_consecutive_hits <= 1:
                self._consecutive_detections = 1
                self._acquisition_success_time_s = timestamp_s
                self._kf.initialize((best.center_x, best.center_y), timestamp_s)
                event = self._sm.transition(TrackState.TRACKING, timestamp_s)
                self._events.append(event)
                self._events.append(TrackingEvent(
                    event=TrackEvent.TRACK_ACQUIRED,
                    timestamp_s=timestamp_s,
                    track_id=self._track_id,
                    metadata={"acquisition_time_s": 0.0},
                ))
            else:
                self._kf.initialize((best.center_x, best.center_y), timestamp_s)
                event = self._sm.transition(TrackState.ACQUIRING, timestamp_s)
                self._events.append(event)

            return self._build_state(timestamp_s)

        # Stay in NO_TRACK -> SEARCHING
        if self._sm.state == TrackState.NO_TRACK:
            event = self._sm.transition(TrackState.SEARCHING, timestamp_s)
            self._events.append(event)

        return self._build_state(timestamp_s)

    def _handle_searching(
        self, detections: list[BeaconDetection], timestamp_s: float, dt: float,
    ) -> TrackingState:
        """Handle state SEARCHING."""
        if detections:
            best = self._select_best(detections)
            self._start_track(best, timestamp_s)
            self._kf.initialize((best.center_x, best.center_y), timestamp_s)
            self._consecutive_detections = 1
            self._last_measurement_time_s = timestamp_s
            self._has_measurement = True

            if self._config.acquisition_min_consecutive_hits <= 1:
                self._acquisition_success_time_s = timestamp_s
                event = self._sm.transition(TrackState.TRACKING, timestamp_s)
                self._events.append(event)
                self._events.append(TrackingEvent(
                    event=TrackEvent.TRACK_ACQUIRED,
                    timestamp_s=timestamp_s,
                    track_id=self._track_id,
                    metadata={"acquisition_time_s": 0.0},
                ))
            else:
                event = self._sm.transition(TrackState.ACQUIRING, timestamp_s)
                self._events.append(event)

            return self._build_state(timestamp_s, dt)

        return self._build_state(timestamp_s, dt)

    def _handle_acquiring(
        self, detections: list[BeaconDetection], timestamp_s: float, dt: float,
    ) -> TrackingState:
        """Handle state ACQUIRING."""
        # Check acquisition timeout
        elapsed = timestamp_s - self._acquisition_start_time_s
        if elapsed > self._config.acquisition_timeout_s:
            self._reset_track(timestamp_s)
            event = self._sm.transition(TrackState.SEARCHING, timestamp_s)
            self._events.append(event)
            return self._build_state(timestamp_s, dt)

        if detections:
            best = self._associate(detections)
            if best is not None:
                self._kf.update((best.center_x, best.center_y))
                self._consecutive_detections += 1
                self._consecutive_misses = 0
                self._last_raw_detection = best
                self._last_measurement_time_s = timestamp_s
                self._has_measurement = True

                if self._consecutive_detections >= self._config.acquisition_min_consecutive_hits:
                    self._acquisition_success_time_s = timestamp_s
                    acq_time = timestamp_s - self._acquisition_start_time_s
                    event = self._sm.transition(TrackState.TRACKING, timestamp_s)
                    self._events.append(event)
                    self._events.append(TrackingEvent(
                        event=TrackEvent.TRACK_ACQUIRED,
                        timestamp_s=timestamp_s,
                        track_id=self._track_id,
                        metadata={"acquisition_time_s": acq_time},
                    ))
            else:
                self._consecutive_misses += 1
                self._total_misses += 1
        else:
            self._consecutive_misses += 1
            self._total_misses += 1

        return self._build_state(timestamp_s, dt)

    def _handle_tracking(
        self, detections: list[BeaconDetection], timestamp_s: float, dt: float,
    ) -> TrackingState:
        """Handle state TRACKING."""
        # Predict
        pred_x, pred_y = self._kf.predict(dt)

        if detections:
            best = self._associate(detections)
            if best is not None:
                # Update with measurement
                self._kf.update((best.center_x, best.center_y))

                self._consecutive_detections += 1
                self._consecutive_misses = 0
                self._total_detections += 1
                self._last_raw_detection = best
                self._last_measurement_time_s = timestamp_s
                self._has_measurement = True

                event = self._sm.transition(TrackState.TRACKING, timestamp_s)
                if event.event != TrackEvent.TRACK_UPDATED:
                    self._events.append(event)
                self._events.append(TrackingEvent(
                    event=TrackEvent.TRACK_UPDATED,
                    timestamp_s=timestamp_s,
                    track_id=self._track_id,
                ))
            else:
                self._handle_miss_in_tracking(timestamp_s)
        else:
            self._handle_miss_in_tracking(timestamp_s)

        return self._build_state(timestamp_s, dt)

    def _handle_miss_in_tracking(self, timestamp_s: float) -> None:
        """Handle a missed detection while in TRACKING state."""
        self._consecutive_misses += 1
        self._total_misses += 1
        self._last_raw_detection = None

        # Check prediction window using time since last measurement
        time_since_measurement = timestamp_s - self._last_measurement_time_s
        if time_since_measurement > self._config.max_prediction_duration_s:
            self._loss_time_s = timestamp_s
            event = self._sm.transition(TrackState.LOST, timestamp_s)
            self._events.append(event)
            self._events.append(TrackingEvent(
                event=TrackEvent.TRACK_LOST,
                timestamp_s=timestamp_s,
                track_id=self._track_id,
                metadata={"miss_duration_s": time_since_measurement},
            ))
        else:
            self._events.append(TrackingEvent(
                event=TrackEvent.TRACK_PREDICTED,
                timestamp_s=timestamp_s,
                track_id=self._track_id,
            ))

    def _handle_lost(
        self, detections: list[BeaconDetection], timestamp_s: float, dt: float,
    ) -> TrackingState:
        """Handle state LOST."""
        # Predict to grow covariance (reduces gate tightness for reappearance)
        if dt > 0 and self._kf.is_initialized:
            self._kf.predict(dt)

        # Check reacquisition timeout
        time_since_loss = timestamp_s - self._loss_time_s
        if time_since_loss > self._config.reacquisition_timeout_s:
            self._reset_track(timestamp_s)
            event = self._sm.transition(TrackState.SEARCHING, timestamp_s)
            self._events.append(event)
            return self._build_state(timestamp_s, dt)

        if detections:
            best = self._associate(detections)
            if best is not None:
                self._kf.update((best.center_x, best.center_y))
                self._consecutive_detections = 1
                self._consecutive_misses = 0
                self._reacquisition_time_s = timestamp_s
                self._last_raw_detection = best
                self._last_measurement_time_s = timestamp_s
                self._has_measurement = True

                reacq_duration = timestamp_s - self._loss_time_s
                event = self._sm.transition(TrackState.REACQUIRING, timestamp_s)
                self._events.append(event)
                self._events.append(TrackingEvent(
                    event=TrackEvent.TRACK_REACQUIRED,
                    timestamp_s=timestamp_s,
                    track_id=self._track_id,
                    metadata={"reacquisition_duration_s": reacq_duration},
                ))

        return self._build_state(timestamp_s, dt)

    def _handle_reacquiring(
        self, detections: list[BeaconDetection], timestamp_s: float, dt: float,
    ) -> TrackingState:
        """Handle state REACQUIRING."""
        # Predict
        pred_x, pred_y = self._kf.predict(dt)

        if detections:
            best = self._associate(detections)
            if best is not None:
                self._kf.update((best.center_x, best.center_y))
                self._consecutive_detections += 1
                self._consecutive_misses = 0
                self._last_raw_detection = best
                self._last_measurement_time_s = timestamp_s
                self._has_measurement = True

                if self._consecutive_detections >= self._config.acquisition_min_consecutive_hits:
                    event = self._sm.transition(TrackState.TRACKING, timestamp_s)
                    self._events.append(event)
                    self._events.append(TrackingEvent(
                        event=TrackEvent.TRACK_ACQUIRED,
                        timestamp_s=timestamp_s,
                        track_id=self._track_id,
                    ))
            else:
                self._consecutive_misses += 1
                self._total_misses += 1
        else:
            self._consecutive_misses += 1
            self._total_misses += 1

        # Check reacquisition timeout
        time_since_reacq = timestamp_s - self._reacquisition_time_s
        if time_since_reacq > self._config.reacquisition_timeout_s:
            self._loss_time_s = timestamp_s
            self._reset_track(timestamp_s)
            event = self._sm.transition(TrackState.SEARCHING, timestamp_s)
            self._events.append(event)

        return self._build_state(timestamp_s, dt)

    def _select_best(self, detections: list[BeaconDetection]) -> BeaconDetection:
        """Select best detection by confidence."""
        return max(detections, key=lambda d: d.confidence)

    def _associate(self, detections: list[BeaconDetection]) -> BeaconDetection | None:
        """Associate detection to current track using gating."""
        predicted = self._kf.position
        return associate_nearest(
            detections, predicted, self._config,
            kalman_mahal_fn=self._kf.mahalanobis_distance,
        )

    def _start_track(self, detection: BeaconDetection, timestamp_s: float) -> None:
        """Initialize a new track from a detection."""
        self._track_id += 1
        self._track_start_time_s = timestamp_s
        self._acquisition_start_time_s = timestamp_s
        self._last_measurement_time_s = timestamp_s
        self._has_measurement = True
        self._consecutive_detections = 0
        self._consecutive_misses = 0

    def _reset_track(self, timestamp_s: float) -> None:
        """Reset track-specific counters (not the full tracker)."""
        self._consecutive_detections = 0
        self._consecutive_misses = 0
        self._last_raw_detection = None

    def _build_state(self, timestamp_s: float, dt: float = 0.0) -> TrackingState:
        """Build TrackingState from current internal state."""
        ts = TrackingState()
        ts.state = self._sm.state
        ts.track_id = self._track_id
        ts.timestamp_s = timestamp_s

        if self._kf.is_initialized:
            px, py = self._kf.position
            vx, vy = self._kf.velocity
            ux, uy = self._kf.position_uncertainty
            innov_x, innov_y = self._kf.innovation

            ts.estimated_x = px
            ts.estimated_y = py
            ts.velocity_x = vx
            ts.velocity_y = vy
            ts.uncertainty_x = ux
            ts.uncertainty_y = uy
            ts.residual_x = innov_x
            ts.residual_y = innov_y
            ts.residual_magnitude = math.sqrt(innov_x**2 + innov_y**2)
            ts.mahalanobis_distance = self._kf.mahalanobis_distance
            prediction_dt = dt if dt > 0 else 0.033
            ts.predicted_x = px + vx * prediction_dt
            ts.predicted_y = py + vy * prediction_dt

        if self._last_raw_detection is not None:
            ts.has_detection = True
            ts.detection_x = self._last_raw_detection.center_x
            ts.detection_y = self._last_raw_detection.center_y
            ts.detection_confidence = self._last_raw_detection.confidence

        ts.track_age_s = timestamp_s - self._track_start_time_s if self._track_start_time_s > 0 else 0.0
        ts.consecutive_detections = self._consecutive_detections
        ts.consecutive_misses = self._consecutive_misses

        # detection_age_s: time since last raw detection was associated
        if self._has_measurement:
            ts.detection_age_s = timestamp_s - self._last_measurement_time_s
        else:
            ts.detection_age_s = 0.0

        if self._total_detections + self._total_misses > 0:
            ts.time_since_last_detection_s = timestamp_s - (self._track_start_time_s + ts.track_age_s) if self._consecutive_misses > 0 else 0.0

        # Acquisition timing
        if self._acquisition_success_time_s > 0 and self._acquisition_start_time_s > 0:
            ts.acquisition_start_time_s = self._acquisition_start_time_s
            ts.acquisition_success_time_s = self._acquisition_success_time_s
            ts.acquisition_time_s = self._acquisition_success_time_s - self._acquisition_start_time_s

        # Loss/reacquisition timing
        ts.loss_time_s = self._loss_time_s
        ts.reacquisition_time_s = self._reacquisition_time_s
        if self._reacquisition_time_s > 0 and self._loss_time_s > 0:
            ts.reacquisition_duration_s = self._reacquisition_time_s - self._loss_time_s

        # Prediction-only flag
        ts.prediction_only = (
            self._sm.state in (TrackState.TRACKING, TrackState.LOST, TrackState.REACQUIRING)
            and self._consecutive_misses > 0
        )

        # Quality
        ts.quality = self._compute_quality(timestamp_s)

        # Lock
        ts.locked = (
            self._sm.state == TrackState.TRACKING
            and ts.quality >= self._config.lock_quality_threshold
            and self._consecutive_misses == 0
        )

        return ts

    def _compute_quality(self, timestamp_s: float) -> float:
        """Compute normalized track quality score [0, 1]."""
        if self._sm.state in (TrackState.NO_TRACK, TrackState.SEARCHING):
            return 0.0

        factors = []

        # Confidence factor
        if self._last_raw_detection is not None:
            factors.append(self._last_raw_detection.confidence)

        # Uncertainty factor (lower uncertainty = higher quality)
        if self._kf.is_initialized:
            ux, uy = self._kf.position_uncertainty
            max_unc = 50.0
            unc_factor = max(0.0, 1.0 - min(ux + uy, max_unc) / max_unc)
            factors.append(unc_factor)

        # Detection streak factor
        if self._consecutive_detections > 0:
            streak_factor = min(1.0, self._consecutive_detections / 10.0)
            factors.append(streak_factor)

        # Miss penalty
        if self._consecutive_misses > 0:
            miss_penalty = max(0.0, 1.0 - self._consecutive_misses * 0.2)
            factors.append(miss_penalty)

        if not factors:
            return 0.0

        return float(sum(factors) / len(factors))
