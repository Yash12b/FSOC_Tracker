"""Authoritative tracking pipeline orchestrator.

Coordinates FrameSource → Perception → Tracking → Control → Metrics.
For simulation mode, also manages Camera → Sensor → Disturbances.

This is the SINGLE pipeline used by GUI, CLI, benchmark, and tests.
No other module should re-implement the pipeline loop.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

import numpy as np

from fsoc_tracker.core.time import compute_dt
from fsoc_tracker.perception.base import PerceptionEngine
from fsoc_tracker.perception.classical_engine import ClassicalBeaconDetector
from fsoc_tracker.perception.config import PerceptionConfig
from fsoc_tracker.perception.models import PerceptionResult
from fsoc_tracker.pipeline.eval import EvalSink, score_against_truth
from fsoc_tracker.pipeline.sources import FrameSource, SimulationSource
from fsoc_tracker.tracking.config import TrackerConfig
from fsoc_tracker.tracking.state import TrackingState, TrackState
from fsoc_tracker.tracking.tracker import KalmanTracker
from fsoc_tracker.control.config import ControllerConfig
from fsoc_tracker.control.controller import CameraActuator, CoarsePointingController
from fsoc_tracker.control.command import ControlCommand, ControlTelemetry, ControlMode


@dataclass
class PipelineFrameResult:
    """Result of processing one frame through the pipeline."""

    frame_index: int = 0
    timestamp_s: float = 0.0
    dt: float = 0.0

    perception: PerceptionResult | None = None
    perception_ms: float = 0.0

    tracking: TrackingState | None = None
    tracking_ms: float = 0.0

    command: ControlCommand | None = None
    telemetry: ControlTelemetry | None = None
    control_ms: float = 0.0

    total_ms: float = 0.0

    ground_truth: Any = None
    error_x: float | None = None
    error_y: float | None = None
    error_px: float | None = None
    fov_inside: bool = False

    ai_decision: Any = None
    ai_features: Any = None
    ai_failure_risk: float = 0.0
    ai_ms: float = 0.0
    roi_rect: tuple[int, int, int, int] | None = None

    search_active: bool = False
    search_reacquired: bool = False
    search_strategy: str = ""


@dataclass
class PipelineState:
    """Accumulated pipeline state across frames."""

    frame_count: int = 0
    total_time_s: float = 0.0
    last_frame_result: PipelineFrameResult | None = None
    acquisition_time_s: float | None = None
    acquisition_frame: int | None = None
    lock_frame: int | None = None
    loss_events: int = 0
    reacquisition_times: list[float] = field(default_factory=list)
    errors: list[float] = field(default_factory=list)
    errors_x: list[float] = field(default_factory=list)
    errors_y: list[float] = field(default_factory=list)
    processing_times_ms: list[float] = field(default_factory=list)
    perception_times_ms: list[float] = field(default_factory=list)
    tracking_times_ms: list[float] = field(default_factory=list)
    control_times_ms: list[float] = field(default_factory=list)
    was_locked: bool = False
    last_lock_time_s: float = 0.0
    last_loss_time_s: float = 0.0
    locked_time_s: float = 0.0
    evaluable_time_s: float = 0.0
    start_time_s: float = 0.0
    source_start_time_s: float | None = None
    _prev_ts: float | None = None
    fov_inside_count: int = 0
    fov_total_count: int = 0


@dataclass
class TrackingMetrics:
    """Computed tracking performance metrics.

    Produced from PipelineState after a run completes.
    All pixel errors are in image-pixel units.
    """

    mean_error_px: float = 0.0
    rmse_px: float = 0.0
    p95_error_px: float = 0.0
    max_error_px: float = 0.0

    mean_error_x_px: float = 0.0
    mean_error_y_px: float = 0.0

    total_frames: int = 0
    frames_with_gt: int = 0
    acquisition_time_s: float = 0.0
    acquisition_frame: int = 0

    fov_retention: float = 0.0
    target_loss_pct: float = 0.0
    loss_events: int = 0
    reacquisition_times: list[float] = field(default_factory=list)
    mean_reacquisition_time_s: float = 0.0

    locked_time_s: float = 0.0
    locked_pct: float = 0.0

    mean_processing_ms: float = 0.0
    mean_perception_ms: float = 0.0
    mean_tracking_ms: float = 0.0
    mean_control_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mean_error_px": round(self.mean_error_px, 2),
            "rmse_px": round(self.rmse_px, 2),
            "p95_error_px": round(self.p95_error_px, 2),
            "max_error_px": round(self.max_error_px, 2),
            "mean_error_x_px": round(self.mean_error_x_px, 2),
            "mean_error_y_px": round(self.mean_error_y_px, 2),
            "total_frames": self.total_frames,
            "frames_with_gt": self.frames_with_gt,
            "acquisition_time_s": round(self.acquisition_time_s, 3),
            "acquisition_frame": self.acquisition_frame,
            "fov_retention": round(self.fov_retention, 4),
            "target_loss_pct": round(self.target_loss_pct, 2),
            "loss_events": self.loss_events,
            "mean_reacquisition_time_s": round(self.mean_reacquisition_time_s, 3),
            "locked_time_s": round(self.locked_time_s, 3),
            "locked_pct": round(self.locked_pct, 4),
            "mean_processing_ms": round(self.mean_processing_ms, 2),
            "mean_perception_ms": round(self.mean_perception_ms, 2),
            "mean_tracking_ms": round(self.mean_tracking_ms, 2),
            "mean_control_ms": round(self.mean_control_ms, 2),
        }


def compute_metrics(state: PipelineState, frame_width: int = 0, frame_height: int = 0) -> TrackingMetrics:
    """Compute summary metrics from accumulated pipeline state."""
    m = TrackingMetrics()

    m.total_frames = state.frame_count
    m.frames_with_gt = len(state.errors)
    m.acquisition_time_s = state.acquisition_time_s or 0.0
    m.acquisition_frame = state.acquisition_frame or 0
    m.loss_events = state.loss_events
    m.reacquisition_times = list(state.reacquisition_times)
    m.locked_time_s = state.locked_time_s

    if state.evaluable_time_s > 0:
        m.locked_pct = state.locked_time_s / state.evaluable_time_s

    if state.errors:
        errors = np.array(state.errors)
        m.mean_error_px = float(np.mean(errors))
        m.rmse_px = float(np.sqrt(np.mean(errors ** 2)))
        m.p95_error_px = float(np.percentile(errors, 95))
        m.max_error_px = float(np.max(errors))

    if state.errors_x:
        m.mean_error_x_px = float(np.mean(state.errors_x))
    if state.errors_y:
        m.mean_error_y_px = float(np.mean(state.errors_y))

    if state.reacquisition_times:
        m.mean_reacquisition_time_s = float(np.mean(state.reacquisition_times))

    # FOV retention
    if state.fov_total_count > 0:
        m.fov_retention = state.fov_inside_count / state.fov_total_count
    elif state.errors and frame_width > 0 and frame_height > 0:
        half_fov_px = min(frame_width, frame_height) / 2.0
        inside = sum(1 for e in state.errors if e <= half_fov_px)
        m.fov_retention = inside / len(state.errors)

    # Target loss %
    if m.total_frames > 0:
        m.target_loss_pct = state.loss_events / max(1, m.total_frames)

    if state.processing_times_ms:
        m.mean_processing_ms = float(np.mean(state.processing_times_ms))
    if state.perception_times_ms:
        m.mean_perception_ms = float(np.mean(state.perception_times_ms))
    if state.tracking_times_ms:
        m.mean_tracking_ms = float(np.mean(state.tracking_times_ms))
    if state.control_times_ms:
        m.mean_control_ms = float(np.mean(state.control_times_ms))

    return m


class TrackingPipeline:
    """Authoritative single pipeline for all modes.

    Usage::

        pipeline = TrackingPipeline(config)
        pipeline.set_source(source)
        pipeline.start()
        while pipeline.running:
            result = pipeline.step()
        pipeline.stop()

    Or frame-by-frame::

        result = pipeline.process_frame(frame)
    """

    def __init__(
        self,
        perception: PerceptionEngine | None = None,
        tracker: KalmanTracker | None = None,
        controller: CoarsePointingController | None = None,
        actuator: CameraActuator | None = None,
        perception_config: PerceptionConfig | None = None,
        tracker_config: TrackerConfig | None = None,
        controller_config: ControllerConfig | None = None,
        ai_brain: Any | None = None,
        adaptive_roi: Any | None = None,
        failure_predictor: Any | None = None,
        decision_logger: Any | None = None,
        adaptive_kalman: Any | None = None,
        adaptive_controller: Any | None = None,
        search_controller: Any | None = None,
        eval_sink: EvalSink | None = None,
    ) -> None:
        self._perception = perception or ClassicalBeaconDetector(perception_config)
        self._tracker = tracker or KalmanTracker(tracker_config)
        self._controller = controller or CoarsePointingController(controller_config)
        self._actuator = actuator or CameraActuator()
        self._ai_brain = ai_brain
        self._adaptive_roi = adaptive_roi
        self._failure_predictor = failure_predictor
        self._decision_logger = decision_logger
        self._adaptive_kalman = adaptive_kalman
        self._adaptive_controller = adaptive_controller
        self._search_controller = search_controller
        self._search_active = False
        self._eval_sink = eval_sink

        self._source: FrameSource | None = None
        self._state = PipelineState()
        self._running = False
        self._last_frame: np.ndarray | None = None
        self._last_perception: PerceptionResult | None = None
        self._last_tracking: TrackingState | None = None
        self._last_command: ControlCommand | None = None
        self._feature_window: list[Any] = []

    @property
    def perception(self) -> PerceptionEngine:
        return self._perception

    @property
    def tracker(self) -> KalmanTracker:
        return self._tracker

    @property
    def controller(self) -> CoarsePointingController:
        return self._controller

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def running(self) -> bool:
        return self._running

    @property
    def last_frame(self) -> np.ndarray | None:
        return self._last_frame

    @property
    def last_perception(self) -> PerceptionResult | None:
        return self._last_perception

    @property
    def last_tracking(self) -> TrackingState | None:
        return self._last_tracking

    @property
    def last_command(self) -> ControlCommand | None:
        return self._last_command

    def set_source(self, source: FrameSource) -> None:
        """Set the input source. Inherits eval_sink from the source if present."""
        self._source = source
        sink = getattr(source, "eval_sink", None)
        if sink is not None:
            self._eval_sink = sink

    @property
    def eval_sink(self) -> EvalSink | None:
        return self._eval_sink

    def start(self) -> None:
        """Open source and begin processing."""
        if self._source is None:
            raise RuntimeError("No source set. Call set_source() first.")
        self._source.open()
        self._running = True
        self._state = PipelineState(start_time_s=time.monotonic())

    def stop(self) -> None:
        """Stop processing and release resources."""
        self._running = False
        if self._source is not None:
            self._source.release()

    def reset(self) -> None:
        """Reset all pipeline state."""
        self._tracker.reset()
        self._controller.reset()
        self._state = PipelineState()
        self._last_frame = None
        self._last_perception = None
        self._last_tracking = None
        self._last_command = None
        self._feature_window = []
        if self._adaptive_roi is not None:
            self._adaptive_roi.reset()

    def get_metrics(self) -> TrackingMetrics:
        """Compute summary metrics from the current pipeline state.

        Call after stop() or during a run to get accumulated metrics.
        """
        w = 0
        h = 0
        if self._source is not None and isinstance(self._source, SimulationSource):
            cam = self._source.camera
            if cam is not None:
                w = cam.state.width
                h = cam.state.height
        elif self._last_frame is not None:
            h, w = self._last_frame.shape[:2]
        return compute_metrics(self._state, w, h)

    def step(self) -> PipelineFrameResult | None:
        """Read one frame from source and process it.

        Returns None when source is exhausted.
        """
        if self._source is None or not self._running:
            return None

        frame = self._source.read()
        if frame is None:
            self._running = False
            return None

        return self.process_frame(frame)

    def process_frame(self, frame: Any) -> PipelineFrameResult:
        """Process a single frame through the full pipeline.

        This is the core processing loop. It works for any Frame object
        regardless of source (simulation, video, live, dataset).
        """
        t_start = time.perf_counter()

        result = PipelineFrameResult(
            frame_index=frame.frame_index,
            timestamp_s=frame.timestamp_s,
        )
        if self._state.source_start_time_s is None:
            self._state.source_start_time_s = frame.timestamp_s

        # Compute dt from timestamps (NEVER hardcode 1/30)
        if self._state._prev_ts is None:
            dt = 1.0 / frame.nominal_fps if frame.nominal_fps and frame.nominal_fps > 0 else 0.0
        else:
            dt = compute_dt(
                frame.timestamp_s,
                self._state._prev_ts,
                nominal_fps=frame.nominal_fps,
                fallback_dt=0.0,
            )
        result.dt = dt
        self._state._prev_ts = frame.timestamp_s

        # Store last frame for GUI display
        self._last_frame = frame.image

        # 1. Perception (optional ROI crop from previous frame)
        t0 = time.perf_counter()
        detect_image, roi_offset = self._crop_for_detection(frame.image)
        perception_result = self._perception.detect(
            detect_image, frame.timestamp_s, frame.frame_index,
        )
        if roi_offset != (0, 0) and perception_result.detections:
            ox, oy = roi_offset
            for cand in perception_result.detections:
                cand.center_x += ox
                cand.center_y += oy
        result.perception_ms = (time.perf_counter() - t0) * 1000.0
        result.perception = perception_result
        self._last_perception = perception_result

        # 2. Tracking — detections only, never frame metadata / GT
        t1 = time.perf_counter()
        detections = perception_result.detections if perception_result.detected else []
        tracking_state = self._tracker.update(detections, frame.timestamp_s)

        if self._adaptive_kalman is not None and self._adaptive_kalman._config.enabled:
            try:
                from fsoc_tracker.perception.quality import QualityState, QualityLevel
                from fsoc_tracker.tracking.maneuver import ManeuverState, MotionClass
                from fsoc_tracker.perception.uncertainty import UncertaintyState, UncertaintyLevel

                quality = QualityState(level=QualityLevel.GOOD)
                if perception_result and hasattr(perception_result, 'diagnostics'):
                    proc_time = perception_result.processing_time_ms
                    if proc_time > 33:
                        quality = QualityState(level=QualityLevel.DEGRADED)
                    elif proc_time > 50:
                        quality = QualityState(level=QualityLevel.POOR)

                maneuver = ManeuverState(motion_class=MotionClass.STEADY)
                if abs(tracking_state.velocity_x) > 50 or abs(tracking_state.velocity_y) > 50:
                    maneuver = ManeuverState(motion_class=MotionClass.MANEUVERING)

                uncertainty = UncertaintyState(level=UncertaintyLevel.MODERATE)
                unc_mag = tracking_state.uncertainty_x + tracking_state.uncertainty_y
                if unc_mag > 20:
                    uncertainty = UncertaintyState(level=UncertaintyLevel.HIGH)
                elif unc_mag > 40:
                    uncertainty = UncertaintyState(level=UncertaintyLevel.VERY_HIGH)

                self._adaptive_kalman.update(
                    quality=quality,
                    maneuver=maneuver,
                    uncertainty=uncertainty,
                    detection_confidence=tracking_state.detection_confidence,
                    has_detection=tracking_state.has_detection,
                )
            except Exception:
                logger.debug("adaptive Kalman update failed", exc_info=True)

        result.tracking_ms = (time.perf_counter() - t1) * 1000.0
        result.tracking = tracking_state
        self._last_tracking = tracking_state

        self._update_roi(perception_result, tracking_state)

        # 2.5. AI Mission Brain (optional)
        if self._ai_brain is not None:
            t_ai = time.perf_counter()
            try:
                ai_result = self._run_ai_step(
                    tracking_state, frame.timestamp_s, dt, frame
                )
                result.ai_decision = ai_result.get("decision")
                result.ai_features = ai_result.get("features")
                result.ai_failure_risk = ai_result.get("failure_risk", 0.0)
                result.roi_rect = ai_result.get("roi_rect")
            except Exception:
                logger.debug("AI step failed", exc_info=True)
            result.ai_ms = (time.perf_counter() - t_ai) * 1000.0

        # 3. Control
        t2 = time.perf_counter()
        command, telemetry = self._controller.compute(
            tracking_state,
            self._get_camera_intrinsics(frame),
            dt,
            frame.timestamp_s,
        )

        if self._adaptive_controller is not None and command is not None:
            try:
                error_x = tracking_state.estimated_x - frame.width / 2.0
                error_y = tracking_state.estimated_y - frame.height / 2.0
                adapt_telem = self._adaptive_controller.compute_adaptation(
                    error_x=error_x,
                    error_y=error_y,
                    velocity_x=tracking_state.velocity_x,
                    velocity_y=tracking_state.velocity_y,
                    image_width=frame.width,
                    image_height=frame.height,
                )
                if hasattr(self._controller, '_pan_pid') and hasattr(self._controller, '_tilt_pid'):
                    self._adaptive_controller.apply_to_pid(self._controller._pan_pid, adapt_telem, "pan")
                    self._adaptive_controller.apply_to_pid(self._controller._tilt_pid, adapt_telem, "tilt")
            except Exception:
                logger.debug("adaptive controller update failed", exc_info=True)

        result.control_ms = (time.perf_counter() - t2) * 1000.0
        result.command = command
        result.telemetry = telemetry
        self._last_command = command

        if self._search_controller is not None and tracking_state.state in (
            TrackState.LOST, TrackState.NO_TRACK, TrackState.SEARCHING,
        ):
            # Directed search: begin once from last-known state, drive the
            # camera with the controller's own bounded rates, gate
            # detections for reacquisition.
            try:
                cam = self._camera_for_actuation()
                cur_pan = cam.state.pan_deg if cam is not None else 0.0
                cur_tilt = cam.state.tilt_deg if cam is not None else 0.0
                if not self._search_active:
                    self._search_active = True
                    self._search_controller.begin_search(
                        tracking_state.estimated_x,
                        tracking_state.estimated_y,
                        tracking_state.velocity_x,
                        tracking_state.velocity_y,
                        frame.timestamp_s,
                        uncertainty_x=tracking_state.uncertainty_x,
                        uncertainty_y=tracking_state.uncertainty_y,
                        current_pan_deg=cur_pan,
                        current_tilt_deg=cur_tilt,
                    )
                else:
                    self._search_controller.update(
                        dt,
                        current_pan_deg=cur_pan,
                        current_tilt_deg=cur_tilt,
                    )
                primary = perception_result.primary_detection
                if primary is not None and primary.detected:
                    accepted = self._search_controller.process_detection(
                        primary.center_x,
                        primary.center_y,
                        primary.confidence,
                        frame.timestamp_s,
                    )
                    if accepted:
                        self._search_active = False
                        result.search_reacquired = True
                        self._search_controller.reset()
                search_state = self._search_controller.state
                result.search_active = self._search_active
                result.search_strategy = search_state.strategy.value
                if search_state.search_radius_px > 0:
                    command = ControlCommand(
                        pan_rate_deg_s=self._search_controller.pan_rate_deg_s,
                        tilt_rate_deg_s=self._search_controller.tilt_rate_deg_s,
                        timestamp_s=frame.timestamp_s,
                        # HOLD (not DISABLED): this is an active mount
                        # drive command so the actuator applies it.
                        control_mode=ControlMode.HOLD,
                    )
                    result.command = command
                    self._last_command = command
            except Exception:
                logger.debug("search update failed", exc_info=True)
        elif self._search_active:
            self._search_active = False
            result.search_active = False
            try:
                self._search_controller.reset()
            except Exception:
                logger.debug("search reset failed", exc_info=True)

        # 4. Apply to camera if simulation source (actuator only)
        if command is not None:
            cam = self._camera_for_actuation()
            if cam is not None:
                self._actuator.apply_command(cam, command, dt)

        # 5. Offline scoring from EvalSink only — never from Frame.metadata
        gt = None
        if self._eval_sink is not None:
            gt = self._eval_sink.primary_for(frame.frame_index)
        if gt is not None:
            result.ground_truth = gt
            err_x, err_y, err_px, fov_inside = score_against_truth(
                tracking_state.estimated_x,
                tracking_state.estimated_y,
                gt,
                frame.width,
                frame.height,
            )
            result.error_x = err_x
            result.error_y = err_y
            result.error_px = err_px
            result.fov_inside = fov_inside if err_px is not None else (
                perception_result is not None and perception_result.detected
            )
        else:
            result.fov_inside = (
                perception_result is not None and perception_result.detected
            )

        result.total_ms = (time.perf_counter() - t_start) * 1000.0

        # Update state
        self._update_state(result, frame.timestamp_s)

        return result

    def _get_camera_intrinsics(self, frame: Any) -> Any:
        """Get camera intrinsics from an attached camera or frame size."""
        cam = self._camera_for_actuation()
        if cam is not None and getattr(cam, "intrinsics", None) is not None:
            return cam.intrinsics
        from fsoc_tracker.simulation.camera.state import CameraIntrinsics
        return CameraIntrinsics(
            width=frame.width,
            height=frame.height,
        )

    def _camera_for_actuation(self) -> Any:
        if self._source is None:
            return None
        return getattr(self._source, "camera", None)

    def _crop_for_detection(self, image: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
        roi = self._adaptive_roi
        if roi is None or image is None:
            return image, (0, 0)
        region = None
        if hasattr(roi, "region"):
            region = roi.region
        elif hasattr(roi, "roi_rect"):
            region = roi.roi_rect
        if not region:
            return image, (0, 0)
        x1, y1, x2, y2 = (int(v) for v in region)
        h, w = image.shape[:2]
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))
        if x2 - x1 < 8 or y2 - y1 < 8:
            return image, (0, 0)
        return image[y1:y2, x1:x2], (x1, y1)

    def _update_roi(self, perception_result: PerceptionResult, tracking_state: TrackingState) -> None:
        roi = self._adaptive_roi
        if roi is None:
            return
        primary = perception_result.primary_detection if perception_result else None
        detected = bool(primary and primary.detected)
        confidence = primary.confidence if primary else 0.0
        if hasattr(roi, "update") and callable(getattr(roi, "update")):
            try:
                roi.update(
                    detected=detected,
                    confidence=confidence,
                    estimated_x=tracking_state.estimated_x,
                    estimated_y=tracking_state.estimated_y,
                    uncertainty_x=tracking_state.uncertainty_x,
                    uncertainty_y=tracking_state.uncertainty_y,
                )
                return
            except TypeError:
                pass
        if hasattr(roi, "compute"):
            situation = "tracking"
            action = "track"
            risk = 0.0
            if self.state.last_frame_result is not None:
                dec = self.state.last_frame_result.ai_decision
                if dec is not None:
                    situation = getattr(getattr(dec, "situation", None), "value", situation)
                    action = getattr(getattr(dec, "action", None), "value", action)
                risk = float(self.state.last_frame_result.ai_failure_risk)
            roi.compute(
                estimated_x=tracking_state.estimated_x,
                estimated_y=tracking_state.estimated_y,
                uncertainty_x=tracking_state.uncertainty_x,
                uncertainty_y=tracking_state.uncertainty_y,
                situation=situation,
                failure_risk=risk,
                action=action,
            )

    def _run_ai_step(
        self,
        tracking_state: TrackingState,
        timestamp_s: float,
        dt: float,
        frame: Any,
    ) -> dict[str, Any]:
        """Run AI mission brain step. Returns dict with decision, features, risk, roi."""
        from fsoc_tracker.ai.mission import ObservationFeatures, MissionObservation

        detected = tracking_state.has_detection and tracking_state.state in (
            TrackState.TRACKING, TrackState.ACQUIRING, TrackState.REACQUIRING,
        )
        confidence = tracking_state.detection_confidence if detected else 0.0
        residual = float(np.sqrt(
            tracking_state.residual_x**2 + tracking_state.residual_y**2
        )) if tracking_state.has_detection else 0.0
        center_x = frame.width / 2.0
        center_y = frame.height / 2.0
        dist_from_center = float(np.sqrt(
            (tracking_state.estimated_x - center_x)**2
            + (tracking_state.estimated_y - center_y)**2
        ))
        source_fps = frame.nominal_fps if frame.nominal_fps and frame.nominal_fps > 0 else 30.0

        obs = ObservationFeatures(
            timestamp_s=timestamp_s,
            detected=detected,
            confidence=confidence,
            residual_px=residual,
            uncertainty_x_px=max(0.0, tracking_state.uncertainty_x),
            uncertainty_y_px=max(0.0, tracking_state.uncertainty_y),
            velocity_x_px_s=tracking_state.velocity_x,
            velocity_y_px_s=tracking_state.velocity_y,
            distance_from_center_px=dist_from_center,
            time_since_detection_s=tracking_state.time_since_last_detection_s,
            latency_ms=0.0,
            source_fps=source_fps,
            processing_fps=1.0 / max(dt, 1e-6),
            candidate_count=0,
            roi_radius_px=self._adaptive_roi.state.radius_px if self._adaptive_roi else 80.0,
        )

        self._feature_window.append(obs)
        if len(self._feature_window) > 10:
            self._feature_window.pop(0)

        result: dict[str, Any] = {"features": obs, "failure_risk": 0.0}

        if self._failure_predictor is not None and self._failure_predictor.trained:
            if len(self._feature_window) >= self._failure_predictor.window_size:
                pred = self._failure_predictor.predict(self._feature_window)
                result["failure_risk"] = pred.risk_score

        mission_obs = MissionObservation(features=obs)
        decision = self._ai_brain.decide(mission_obs)
        result["decision"] = decision

        if self._adaptive_roi is not None:
            self._adaptive_roi.compute(
                estimated_x=tracking_state.estimated_x,
                estimated_y=tracking_state.estimated_y,
                uncertainty_x=tracking_state.uncertainty_x,
                uncertainty_y=tracking_state.uncertainty_y,
                situation=decision.situation.value,
                failure_risk=result["failure_risk"],
                action=decision.action.value,
            )
            result["roi_rect"] = self._adaptive_roi.roi_rect

        if self._decision_logger is not None:
            self._decision_logger.log(obs, decision.safety)

        return result

    def _update_state(self, result: PipelineFrameResult, timestamp_s: float) -> None:
        """Update accumulated pipeline state."""
        s = self._state
        s.frame_count += 1
        s.total_time_s = timestamp_s
        s.last_frame_result = result
        dt = (
            max(timestamp_s - s._prev_ts, 0.0)
            if s._prev_ts is not None else 0.0
        )
        s.evaluable_time_s += dt

        s.processing_times_ms.append(result.total_ms)
        s.perception_times_ms.append(result.perception_ms)
        s.tracking_times_ms.append(result.tracking_ms)
        s.control_times_ms.append(result.control_ms)

        # Track acquisition
        if result.tracking is not None:
            ts = result.tracking
            is_locked = ts.state.name in ("TRACKING", "REACQUIRING")
            if is_locked:
                s.locked_time_s += dt

            if s.acquisition_time_s is None and is_locked:
                source_start = s.source_start_time_s if s.source_start_time_s is not None else timestamp_s
                s.acquisition_time_s = max(0.0, timestamp_s - source_start)
                s.acquisition_frame = result.frame_index

            if is_locked and not s.was_locked:
                if s.last_loss_time_s > 0:
                    reacq = timestamp_s - s.last_loss_time_s
                    s.reacquisition_times.append(reacq)
                s.lock_frame = result.frame_index

            if not is_locked and s.was_locked:
                s.loss_events += 1
                s.last_loss_time_s = timestamp_s

            s.was_locked = is_locked

        # Track errors
        if result.error_px is not None:
            s.errors.append(result.error_px)
            if result.error_x is not None:
                s.errors_x.append(result.error_x)
            if result.error_y is not None:
                s.errors_y.append(result.error_y)

        # Track FOV retention
        s.fov_total_count += 1
        if result.fov_inside:
            s.fov_inside_count += 1

        s._prev_ts = timestamp_s
