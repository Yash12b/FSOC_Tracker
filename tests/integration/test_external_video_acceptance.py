"""External-video acceptance test.

Proves the complete observation chain on a real MP4 file with NO
simulation in the loop:

    MP4 file
    -> VideoSource (FrameSource)
    -> actual decoded frame (image + video timestamps)
    -> perception (ClassicalBeaconDetector -> centroid)
    -> tracker (KalmanTracker.update)
    -> prediction (KalmanTracker.predict)
    -> telemetry (MetricsCollector FrameMetrics + build_result)

Information-boundary rules (enforced by tests below):
    * The runtime function ``_run_video_mission`` receives ONLY the video
      path. Ground-truth annotations live in a guarded container that
      raises if touched while the runtime window is open.
    * No world state, simulator target coordinates, future trajectory, or
      hidden beacon object may enter runtime tracking. Frame metadata is
      scanned for leaked keys on every frame.
    * dt ALWAYS comes from decoded video timestamps. There is no
      hard-coded FPS constant anywhere in the runtime path (the videos
      use 25 FPS and 15 FPS deliberately -- never 30).
    * Ground-truth centroids are used OFFLINE, after the run, only to
      score centroid/estimate error. They never influence tracking.
"""

from __future__ import annotations

import inspect
import math
import os
import tempfile
import time

import cv2
import numpy as np
import pytest

from fsoc_tracker.benchmark.collector import MetricsCollector
from fsoc_tracker.benchmark.models import FrameMetrics
from fsoc_tracker.control.controller import CoarsePointingController
from fsoc_tracker.core.interfaces import FrameSource
from fsoc_tracker.core.models import SourceType
from fsoc_tracker.perception.classical_engine import ClassicalBeaconDetector
from fsoc_tracker.pipeline.sources import VideoSource
from fsoc_tracker.simulation.camera.state import CameraIntrinsics
from fsoc_tracker.tracking.tracker import KalmanTracker

# ---------------------------------------------------------------------------
# Test video synthesis (OFFLINE fixture, never visible to runtime tracking)
# ---------------------------------------------------------------------------

MAIN_WIDTH, MAIN_HEIGHT = 400, 300
MAIN_FPS = 25.0
MAIN_FRAMES = 100

SMALL_WIDTH, SMALL_HEIGHT = 320, 240
SMALL_FPS = 15.0
SMALL_FRAMES = 45

FORBIDDEN_METADATA_KEYS = (
    "ground_truth",
    "world_state",
    "target_position",
    "beacon_position",
    "trajectory",
    "future",
    "distance_m",
    "beacon_distance",
    "simulation_time",
)

# PS Benchmark-2 reference: 30 fps full-screen video with noise.
PS_WIDTH, PS_HEIGHT = 640, 480
PS_FPS = 30.0
PS_FRAMES = 90


def _make_beacon_video(
    path: str,
    width: int,
    height: int,
    fps: float,
    num_frames: int,
    seed: int = 7,
    salt_pepper_density: float = 0.0,
    noise_sigma: float = 6.0,
) -> list[tuple[float, float]]:
    """Write an MP4 with a moving Gaussian beacon + sensor noise.

    Returns per-frame ground-truth centroids (float pixels, pre-encode).
    The list is OFFLINE annotation data for scoring only.
    """
    rng = np.random.default_rng(seed)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    assert out.isOpened(), f"VideoWriter failed for {path}"

    x0, y0 = 0.2 * width, 0.3 * height
    x1, y1 = 0.8 * width, 0.7 * height
    gt: list[tuple[float, float]] = []

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float64)
    for i in range(num_frames):
        a = i / max(num_frames - 1, 1)
        cx, cy = x0 + (x1 - x0) * a, y0 + (y1 - y0) * a
        gt.append((cx, cy))
        blob = 255.0 * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * 3.0**2))
        noise = rng.normal(0.0, noise_sigma, (height, width))
        img = np.clip(20.0 + blob + noise, 0, 255).astype(np.uint8)
        if salt_pepper_density > 0.0:
            pepper = rng.random((height, width)) < salt_pepper_density / 2.0
            salt = rng.random((height, width)) < salt_pepper_density / 2.0
            img[pepper] = 0
            img[salt] = 255
        out.write(cv2.cvtColor(img, cv2.COLOR_GRAY2BGR))
    out.release()
    return gt


class _GuardedGT:
    """Annotation container that explodes if touched during runtime."""

    def __init__(self, data: list[tuple[float, float]]) -> None:
        self._data = data
        self.armed = False
        self.accesses = 0

    def __getitem__(self, idx):
        if self.armed:
            self.accesses += 1
            raise AssertionError(
                "RUNTIME VIOLATION: ground-truth annotations accessed "
                "inside the tracking loop"
            )
        return self._data[idx]

    def __len__(self) -> int:
        if self.armed:
            self.accesses += 1
            raise AssertionError(
                "RUNTIME VIOLATION: ground-truth annotations accessed "
                "inside the tracking loop"
            )
        return len(self._data)

    def release(self) -> list[tuple[float, float]]:
        self.armed = False
        return self._data


# ---------------------------------------------------------------------------
# RUNTIME tracking path (must stay free of GT / world / simulation state)
# ---------------------------------------------------------------------------

def _run_video_mission(video_path: str) -> dict:
    """Run perception -> centroid -> tracker -> prediction -> telemetry.

    Inputs: ONLY the video path. Reads decoded frames (image, timestamp,
    frame index, dimensions, nominal fps) through the FrameSource
    interface. dt is derived from consecutive video timestamps.
    """
    source: FrameSource = VideoSource(video_path)
    assert isinstance(source, FrameSource)
    source.open()
    assert source.is_open()
    assert source.nominal_fps is not None and source.nominal_fps > 0

    detector = ClassicalBeaconDetector()
    tracker = KalmanTracker()
    controller = CoarsePointingController()
    collector = MetricsCollector()
    collector.start()

    trace: list[dict] = []
    prev_ts: float | None = None
    wall_start = time.perf_counter()

    while True:
        f = source.read()
        if f is None:
            break
        assert f.source_type == SourceType.VIDEO

        # Information boundary: frames must carry no hidden truth.
        for key in f.metadata.keys():
            lowered = key.lower()
            assert "ground_truth" not in lowered, f"GT leak: {key}"
            assert "world" not in lowered, f"world leak: {key}"
            assert "trajectory" not in lowered, f"trajectory leak: {key}"
            assert "target_position" not in lowered, f"target leak: {key}"
            assert "beacon_position" not in lowered, f"beacon leak: {key}"

        ts = float(f.timestamp_s)
        dt = 0.0 if prev_ts is None else ts - prev_ts
        assert dt >= 0.0, "video timestamps must be monotonic"
        prev_ts = ts

        t0 = time.perf_counter()
        det = detector.detect(f.image, ts, f.frame_index)
        t_perc = (time.perf_counter() - t0) * 1000.0

        detected = bool(
            det.primary_detection is not None and det.primary_detection.detected
        )
        centroid = (
            (float(det.primary_detection.center_x),
             float(det.primary_detection.center_y))
            if detected else None
        )

        t1 = time.perf_counter()
        if detected:
            trk = tracker.update(det.detections, ts)
        else:
            # No observation: coast on the motion model (prediction leg).
            trk = tracker.predict(ts)
        t_trk = (time.perf_counter() - t1) * 1000.0

        # Control uses decoded-frame geometry + timestamp-derived dt only.
        intrinsics = CameraIntrinsics(
            width=int(f.width), height=int(f.height),
            horizontal_fov_deg=4.0, vertical_fov_deg=3.0,
        )
        t2 = time.perf_counter()
        cmd, _ = controller.compute(trk, intrinsics, dt, ts)
        t_ctl = (time.perf_counter() - t2) * 1000.0
        t_proc = (time.perf_counter() - t0) * 1000.0

        collector.record_frame(FrameMetrics(
            frame_index=int(f.frame_index),
            timestamp_s=ts,
            dt=dt,
            source_fps=source.nominal_fps,
            processing_time_ms=t_proc,
            perception_time_ms=t_perc,
            tracking_time_ms=t_trk,
            control_time_ms=t_ctl,
            detected=detected,
            detection_confidence=float(det.primary_detection.confidence)
            if detected else 0.0,
            detection_x=centroid[0] if centroid else 0.0,
            detection_y=centroid[1] if centroid else 0.0,
            candidate_count=int(det.num_candidates),
            track_x=float(trk.estimated_x),
            track_y=float(trk.estimated_y),
            track_state=str(trk.state.name),
            lock_status=(trk.state.name == "TRACKING"),
        ))
        trace.append({
            "frame": int(f.frame_index),
            "timestamp_s": ts,
            "dt": dt,
            "width": int(f.width),
            "height": int(f.height),
            "detected": detected,
            "centroid": centroid,
            "candidates": int(det.num_candidates),
            "track_state": str(trk.state.name),
            "est": (float(trk.estimated_x), float(trk.estimated_y)),
            "pan_rate": float(cmd.pan_rate_deg_s),
            "tilt_rate": float(cmd.tilt_rate_deg_s),
            "proc_ms": t_proc,
        })

    wall_time_s = time.perf_counter() - wall_start
    # Prediction leg on the live tracker past end-of-stream: coast forward
    # one video period and confirm the motion model extrapolates.
    coast = []
    if trace:
        last_ts = trace[-1]["timestamp_s"]
        video_dt = float(np.median([r["dt"] for r in trace[1:]])) if len(trace) > 1 else 0.0
        for k in (1, 2, 3):
            pred = tracker.predict(last_ts + k * video_dt)
            coast.append((float(pred.estimated_x), float(pred.estimated_y)))

    collector.stop()
    result = collector.build_result()
    info = source.get_info()
    source.release()
    return {
        "trace": trace,
        "coast": coast,
        "collector_result": result,
        "collector_frames": list(collector.frames),
        "events": list(collector.events),
        "wall_time_s": wall_time_s,
        "video_fps": float(source.nominal_fps or 0.0),
        "video_info": info,
    }


def _score_offline(mission: dict, gt: list[tuple[float, float]]) -> dict:
    """OFFLINE scoring only: compare runtime outputs against annotations."""
    trace = mission["trace"]
    det_errs, est_errs = [], []
    for row in trace:
        gx, gy = gt[row["frame"]]
        if row["centroid"] is not None:
            det_errs.append(math.dist(row["centroid"], (gx, gy)))
        est_errs.append(math.dist(row["est"], (gx, gy)))
    detected = sum(1 for r in trace if r["detected"])
    tracking = sum(1 for r in trace if r["track_state"] == "TRACKING")
    longest, run = 0, 0
    for r in trace:
        run = run + 1 if r["track_state"] == "TRACKING" else 0
        longest = max(longest, run)
    lat = [r["proc_ms"] for r in trace]
    return {
        "detection_rate": detected / len(trace),
        "tracking_rate": tracking / len(trace),
        "longest_tracking_run": longest,
        "mean_det_err": float(np.mean(det_errs)) if det_errs else float("inf"),
        "rmse_det": float(np.sqrt(np.mean(np.square(det_errs)))) if det_errs else float("inf"),
        "mean_est_err": float(np.mean(est_errs)),
        "rmse_est": float(np.sqrt(np.mean(np.square(est_errs)))),
        "processing_fps": len(trace) / mission["wall_time_s"],
        "mean_latency_ms": float(np.mean(lat)),
        "p95_latency_ms": float(np.percentile(lat, 95)),
    }


@pytest.fixture
def main_video():
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    gt = _make_beacon_video(
        tmp.name, MAIN_WIDTH, MAIN_HEIGHT, MAIN_FPS, MAIN_FRAMES)
    guarded = _GuardedGT(gt)
    yield tmp.name, guarded
    guarded.armed = False
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


@pytest.fixture
def small_video():
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    gt = _make_beacon_video(
        tmp.name, SMALL_WIDTH, SMALL_HEIGHT, SMALL_FPS, SMALL_FRAMES,
        seed=21,
    )
    guarded = _GuardedGT(gt)
    yield tmp.name, guarded
    guarded.armed = False
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


@pytest.fixture
def ps_video():
    """PS Benchmark-2 reference: 30 fps full-screen + S&P/Gaussian noise."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    gt = _make_beacon_video(
        tmp.name, PS_WIDTH, PS_HEIGHT, PS_FPS, PS_FRAMES,
        seed=99, salt_pepper_density=0.10, noise_sigma=8.0,
    )
    guarded = _GuardedGT(gt)
    yield tmp.name, guarded
    guarded.armed = False
    if os.path.exists(tmp.name):
        os.unlink(tmp.name)


def _run_guarded(path: str, guarded: _GuardedGT) -> dict:
    guarded.armed = True
    try:
        return _run_video_mission(path)
    finally:
        guarded.armed = False


# ---------------------------------------------------------------------------
# Acceptance tests
# ---------------------------------------------------------------------------

class TestVideoDecoding:
    def test_framesource_decodes_real_frames(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        trace = mission["trace"]
        assert len(trace) == MAIN_FRAMES
        for row in trace:
            assert row["width"] == MAIN_WIDTH
            assert row["height"] == MAIN_HEIGHT

    def test_timestamps_come_from_video_not_constants(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        trace = mission["trace"]
        # Deliberately non-30 FPS: the stream must report its own rate.
        assert mission["video_fps"] == pytest.approx(MAIN_FPS, abs=1.0)
        assert mission["video_fps"] != pytest.approx(30.0, abs=1.0)
        expected_dt = 1.0 / MAIN_FPS
        for row in trace[1:]:
            assert row["dt"] == pytest.approx(expected_dt, abs=0.01)
        duration = trace[-1]["timestamp_s"] - trace[0]["timestamp_s"]
        assert duration == pytest.approx((MAIN_FRAMES - 1) / MAIN_FPS, abs=0.05)

    def test_no_hidden_truth_in_frames(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        for row in mission["trace"]:
            assert row["detected"] in (True, False)
        # Guarded annotations raise on ANY access while armed; a clean run
        # means runtime tracking never touched ground truth.
        assert guarded.accesses == 0


class TestRuntimeIsolation:
    def test_runtime_source_has_no_world_or_trajectory(self):
        # Usage patterns (not guard-string names): the runtime function
        # must never construct/read simulation objects, trajectories,
        # or ground-truth payloads. (The leak-scan assertions above
        # mention those words only to reject them in frame metadata.)
        src = inspect.getsource(_run_video_mission)
        for forbidden in (
            "SimulationEngine(", "WorldTargetState(", "WorldConfig(",
            "trajectory_type=", "trajectory_params=", "get_state(",
            "add_target(", 'metadata["ground_truth"]',
            "metadata.get(\"ground_truth\"", "simulation_time_s",
        ):
            assert forbidden not in src, f"runtime references {forbidden}"

    def test_source_type_is_video(self, main_video):
        path, guarded = main_video
        src = VideoSource(path)
        src.open()
        frame = src.read()
        assert frame is not None
        assert frame.source_type == SourceType.VIDEO
        for key in FORBIDDEN_METADATA_KEYS:
            assert key not in frame.metadata
        src.release()


class TestPerceptionToCentroid:
    def test_detection_rate_and_centroid_accuracy(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        scores = _score_offline(mission, guarded.release())
        assert scores["detection_rate"] >= 0.8
        assert scores["mean_det_err"] < 5.0
        assert scores["rmse_det"] < 7.0


class TestTrackerAndPrediction:
    def test_tracking_continuity(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        scores = _score_offline(mission, guarded.release())
        assert scores["tracking_rate"] >= 0.5
        assert scores["longest_tracking_run"] >= MAIN_FRAMES // 2
        assert scores["mean_est_err"] < 10.0

    def test_prediction_coasts_forward(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        guarded.release()
        assert len(mission["coast"]) == 3
        # Constant-velocity motion: coasted predictions keep advancing
        # along +x (beacon drifts right) without collapsing to NaN.
        xs = [p[0] for p in mission["coast"]]
        assert all(math.isfinite(v) for p in mission["coast"] for v in p)
        assert xs[-1] >= xs[0]


class TestTelemetry:
    def test_fps_latency_and_events(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        scores = _score_offline(mission, guarded.release())
        assert scores["processing_fps"] > 5.0
        assert scores["mean_latency_ms"] < 200.0
        assert scores["p95_latency_ms"] < 400.0
        # Collector telemetry: per-frame records, monotonic timestamps,
        # video-rate dt on every record (never a 1/30 constant).
        frames = mission["collector_frames"]
        assert len(frames) == MAIN_FRAMES
        expected_dt = 1.0 / MAIN_FPS
        for fm in frames[1:]:
            assert fm.dt == pytest.approx(expected_dt, abs=0.01)
            assert fm.source_fps == pytest.approx(MAIN_FPS, abs=1.0)
        kinds = {e["type"] for e in mission["events"]}
        assert "acquired" in kinds

    def test_collector_result_summarises_run(self, main_video):
        path, guarded = main_video
        mission = _run_guarded(path, guarded)
        guarded.release()
        result = mission["collector_result"]
        assert result is not None
        assert result.tracking is not None
        assert result.performance is not None


class TestArbitraryVideoGeometry:
    def test_different_dimensions_and_rate(self, small_video):
        path, guarded = small_video
        mission = _run_guarded(path, guarded)
        trace = mission["trace"]
        assert len(trace) == SMALL_FRAMES
        assert mission["video_fps"] == pytest.approx(SMALL_FPS, abs=1.0)
        expected_dt = 1.0 / SMALL_FPS
        for row in trace:
            assert row["width"] == SMALL_WIDTH
            assert row["height"] == SMALL_HEIGHT
        for row in trace[1:]:
            assert row["dt"] == pytest.approx(expected_dt, abs=0.02)
        scores = _score_offline(mission, guarded.release())
        assert scores["detection_rate"] >= 0.8
        assert scores["mean_det_err"] < 5.0

    def test_repeat_run_identical(self, main_video):
        path, guarded = main_video
        first = _run_guarded(path, guarded)
        second = _run_guarded(path, guarded)
        guarded.release()
        assert len(first["trace"]) == len(second["trace"])
        for a, b in zip(first["trace"], second["trace"]):
            assert a["centroid"] == b["centroid"]
            assert a["track_state"] == b["track_state"]
            assert a["est"] == b["est"]


class TestPSBenchmark2Reference:
    """Evaluator-style video: 640x480 @ 30 fps, full-screen, noisy."""

    def test_decodes_at_evaluator_rate(self, ps_video):
        path, guarded = ps_video
        mission = _run_guarded(path, guarded)
        guarded.release()
        trace = mission["trace"]
        assert len(trace) == PS_FRAMES
        assert mission["video_fps"] == pytest.approx(PS_FPS, abs=1.0)
        expected_dt = 1.0 / PS_FPS
        for row in trace:
            assert row["width"] == PS_WIDTH
            assert row["height"] == PS_HEIGHT
        for row in trace[1:]:
            assert row["dt"] == pytest.approx(expected_dt, abs=0.01)

    def test_tracks_through_noise(self, ps_video):
        path, guarded = ps_video
        mission = _run_guarded(path, guarded)
        scores = _score_offline(mission, guarded.release())
        assert scores["detection_rate"] >= 0.5
        assert scores["mean_det_err"] < 8.0
        assert scores["longest_tracking_run"] >= PS_FRAMES // 4


def _offline_gt(path: str, mission: dict) -> list[tuple[float, float]]:
    """Recompute annotation centroids OFFLINE for telemetry-only tests.

    Regenerates the same synthetic trajectory parameters used to encode
    the video. Used only when a test needs scores without consuming the
    guarded fixture annotations. Never called inside runtime tracking.
    """
    n = len(mission["trace"])
    w = mission["trace"][0]["width"]
    h = mission["trace"][0]["height"]
    return [
        (0.2 * w + (0.6 * w) * i / max(n - 1, 1),
         0.3 * h + (0.4 * h) * i / max(n - 1, 1))
        for i in range(n)
    ]
