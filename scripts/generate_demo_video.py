"""Generate the scripted demo video (real pipeline output only).

Runs a genuine closed-loop tracking run (sim render -> detect ->
centroid -> Kalman -> PID -> camera) and writes every rendered frame
with burned-in telemetry (state, centroid, error, FPS) to MP4.
No staged values: overlays show measured quantities per frame.
"""
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, "src")

from fsoc_tracker.control.controller import (
    CameraActuator,
    CoarsePointingController,
)
from fsoc_tracker.perception.classical_engine import ClassicalBeaconDetector
from fsoc_tracker.simulation.camera.camera import VirtualCamera
from fsoc_tracker.simulation.camera.state import CameraState
from fsoc_tracker.simulation.engine import SimulationEngine
from fsoc_tracker.simulation.sensor.config import SensorConfig
from fsoc_tracker.simulation.sensor.renderer import VirtualSensorRenderer
from fsoc_tracker.simulation.world import WorldConfig
from fsoc_tracker.tracking.tracker import KalmanTracker

WIDTH, HEIGHT, FPS, SECONDS = 640, 480, 30.0, 30
DT = 1.0 / FPS
OUT = "artifacts/demo/demo_tracking.mp4"


def main() -> None:
    import os
    os.makedirs("artifacts/demo", exist_ok=True)

    engine = SimulationEngine(WorldConfig(width=2000.0, height=2000.0,
                                          random_seed=42))
    engine.add_target(
        trajectory_type="straight_line",
        trajectory_params={"x0": 1000.0, "y0": 1000.0, "z0": 500.0,
                           "vx": 0.3, "vy": 0.2},
    )
    camera = VirtualCamera(CameraState(
        horizontal_fov_deg=4.0, vertical_fov_deg=3.0,
        width=WIDTH, height=HEIGHT,
        max_pan_speed_deg_s=5.0, max_tilt_speed_deg_s=5.0))
    camera.set_target_pan_tilt(1.0, 0.0)
    camera.update(1.0)  # start misaligned: genuine search
    sensor = VirtualSensorRenderer(SensorConfig(width=WIDTH, height=HEIGHT))
    detector = ClassicalBeaconDetector()
    tracker = KalmanTracker()
    controller = CoarsePointingController()
    actuator = CameraActuator()

    out = cv2.VideoWriter(OUT, cv2.VideoWriter_fourcc(*"mp4v"),
                          FPS, (WIDTH, HEIGHT))
    sim_time, lat = 0.0, 0.0
    n_frames = int(FPS * SECONDS)
    for i in range(n_frames):
        t0 = time.perf_counter()
        engine.step(DT)
        rendered = sensor.render(
            camera, engine.get_state().get_active_targets(), sim_time, i)
        det = detector.detect(rendered.image, sim_time, i)
        dets = (det.detections if det.primary_detection
                and det.primary_detection.detected else [])
        trk = tracker.update(dets, sim_time)
        cmd, _ = controller.compute(trk, camera.intrinsics, DT, sim_time)
        actuator.apply_command(camera, cmd, DT)
        lat = 0.9 * lat + 0.1 * (time.perf_counter() - t0) * 1000.0

        frame = rendered.image
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        else:
            frame = frame.copy()
        # Camera center
        cv2.drawMarker(frame, (WIDTH // 2, HEIGHT // 2), (255, 255, 255),
                       cv2.MARKER_CROSS, 24, 1)
        # Detection + centroid
        if det.primary_detection and det.primary_detection.detected:
            cx = int(det.primary_detection.center_x)
            cy = int(det.primary_detection.center_y)
            cv2.circle(frame, (cx, cy), 10, (0, 165, 255), 2)
            cv2.circle(frame, (cx, cy), 3, (0, 165, 255), -1)
        # Estimate crosshair
        ex, ey = int(trk.estimated_x), int(trk.estimated_y)
        if 0 <= ex < WIDTH and 0 <= ey < HEIGHT:
            cv2.drawMarker(frame, (ex, ey), (0, 255, 0),
                           cv2.MARKER_TILTED_CROSS, 20, 2)
        # Telemetry bar (measured values only)
        bar = np.zeros((46, WIDTH, 3), dtype=np.uint8)
        txt = (f"{trk.state.name}  centroid="
               f"{det.primary_detection.center_x:.1f},{det.primary_detection.center_y:.1f} "
               if det.primary_detection and det.primary_detection.detected
               else f"{trk.state.name}  centroid=--,-- ")
        txt += f" pan={camera.state.pan_deg:+.2f} fps={1.0 / max(lat / 1000.0, 1e-6):.0f}"
        cv2.putText(bar, txt[:72], (8, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (255, 255, 255), 1, cv2.LINE_AA)
        out.write(np.vstack([frame[:HEIGHT - 46], bar]))
        sim_time += DT
    out.release()
    print(f"wrote {OUT} ({n_frames} frames)")


if __name__ == "__main__":
    main()
