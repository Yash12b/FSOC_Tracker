# FSOC Tracker — User Manual

**Version:** 0.1.0
**SIH Problem Statement:** SIH26169

---

## 1. Installation

### Prerequisites
- Python 3.10 or later
- pip

### Install from source

```bash
git clone <repository-url>
cd fsoc_tracker

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install with all dependencies
pip install -e ".[dev,full]"

# Verify installation
python -m fsoc_tracker
```

### Optional dependencies

```bash
# AI perception (requires torch)
pip install -e ".[ai]"

# Full install (dev + AI + plotting)
pip install -e ".[dev,ai,full]"
```

---

## 2. Quick Start

### Smoke test (real pipeline, 5 seconds)

```bash
python -m fsoc_tracker
```

### Headless simulation

```bash
# Basic simulation (straight line, 10 seconds)
fsoc-sim

# Circular trajectory with disturbances
fsoc-sim -t circular -d 10 --disturbance light

# All options
fsoc-sim --trajectory figure_8 --duration 20 --dt 0.033 --seed 42 \
         --target-size 10 --disturbance moderate --output runs/ --verbose
```

### Video benchmark

```bash
# Benchmark an MP4 file
fsoc-bench -i video.mp4

# With verbose output
fsoc-bench -i video.mp4 -v --output runs/benchmark
```

### Benchmark suites (generated worlds + seeds)

```bash
# Single generated-world run
python -m fsoc_tracker.cli.run_benchmark sim --method kalman_expert \
    --world multi --seed 42 --frames 300 --output logs/benchmark

# Multi-seed aggregation (mean/std across seeds)
python -m fsoc_tracker.cli.run_benchmark sim --method kalman_expert \
    --world loss --seeds 42,43,44 --frames 300 --output logs/benchmark
```

### GUI

```bash
python -m fsoc_tracker --gui
```

---

## 3. Configuration

All parameters are configurable via YAML files in `configs/`.

### Configuration profiles

| Profile | File | Description |
|---------|------|-------------|
| Default | `configs/default.yaml` | Standard SIH26169 defaults |
| Production | `configs/production.yaml` | All advanced features enabled |
| Baseline | `configs/baseline.yaml` | Minimal (no advanced features) |
| Debug | `configs/debug.yaml` | Full diagnostics + logging |
| Benchmark | `configs/benchmark.yaml` | Video benchmark settings |

### Using a config file

```bash
python -m fsoc_tracker -c configs/production.yaml
fsoc-sim -c configs/debug.yaml -t circular
```

### Key parameters

```yaml
camera:
  width: 640              # Image width (pixels)
  height: 480             # Image height (pixels)
  horizontal_fov_deg: 4.0 # Horizontal FOV (degrees)
  vertical_fov_deg: 3.0   # Vertical FOV (degrees)
  update_rate_hz: 30.0    # Camera update rate (Hz)

target:
  size_px: 10.0           # Beacon size (pixels)
  shape: square           # Beacon shape
  motion_type: straight_line  # Trajectory type

control:
  max_pan_speed_deg_s: 5.0   # Max pan rate (deg/s)
  max_tilt_speed_deg_s: 5.0  # Max tilt rate (deg/s)
  pid:
    kp_pan: 0.5              # Pan proportional gain
    ki_pan: 0.01             # Pan integral gain
    kd_pan: 0.1              # Pan derivative gain

disturbance:
  enabled: false             # Enable disturbances
  types: []                  # List of disturbance types
  gaussian_sigma: 5.0        # Gaussian noise sigma
```

---

## 4. Operation Modes

### Simulation Mode

The full closed-loop simulation:
1. Virtual world generates target position
2. Virtual camera renders the scene
3. Sensor creates beacon image
4. Disturbances are applied (optional)
5. Perception detects the beacon
6. Tracker estimates position and velocity
7. Controller computes pan/tilt commands
8. Camera moves → loop

```bash
fsoc-sim -t circular -d 30
```

### Video Mode

Process an external video file:
1. Video decoder reads frames
2. Perception detects beacon in each frame
3. Tracker estimates position
4. Metrics are computed against ground truth (if available)

```bash
fsoc-bench -i benchmark_video.mp4 -v
```

### Live Camera Mode

Real-time webcam processing:
1. Camera captures frames
2. Perception + tracking in real-time
3. Control commands displayed (not sent to physical camera)

```bash
python -c "
from fsoc_tracker.pipeline.sources import LiveSource
from fsoc_tracker.pipeline.pipeline import TrackingPipeline
from fsoc_tracker.perception.classical_engine import ClassicalBeaconDetector
from fsoc_tracker.tracking.tracker import KalmanTracker

source = LiveSource(camera_id=0)
pipeline = TrackingPipeline(
    perception=ClassicalBeaconDetector(),
    tracker=KalmanTracker(),
)
pipeline.set_source(source)
pipeline.start()
while pipeline.running:
    result = pipeline.step()
    if result:
        print(f'Frame {result.frame_index}: {result.tracking.state.name}')
pipeline.stop()
"
```

---

## 5. GUI Overview

The GUI provides a real-time aerospace HUD with:

- **Camera View** — Live camera feed with detection overlay
- **World View** — 2000x2000 global radar with trajectory trail
- **Telemetry** — Real-time tracking and control metrics
- **Scorecard** — SIH threshold evaluation
- **Error Plots** — Live X/Y/Euclidean error graphs
- **Event Log** — Color-coded tracking events
- **Control Panel** — Configuration and mode switching

### Launch

```bash
python -m fsoc_tracker --gui
```

### World workflow (simulation mode)

There are no preset scenes. Every simulation run starts from an
explicitly created world:

1. Top bar, WORLD menu: **New empty world** or **Random world (seed)**
   (uses the seed spin box; same seed reproduces the same world).
2. Place Terminal A (3D view context action or worker API) — position
   and orientation are independent; the camera never auto-aims.
3. Add beacons at independent positions; assign each beacon its own
   motion model, parameters, and seed.
4. Choose one PRIMARY BEACON (starred in the beacon list). Changing it
   never moves other beacons or the camera.
5. Configure disturbances, then press START. START with no world is
   refused with a logged error.

---

## 6. Benchmark Evaluation

### Running benchmarks

```bash
# Synthetic benchmark (closed-loop)
fsoc-sim -t circular -d 30 --output runs/bench_synthetic

# Video benchmark
fsoc-bench -i test_video.mp4 -v --output runs/bench_video

# Generated-world benchmark (replaces the retired numbered suite)
python -m fsoc_tracker.cli.run_benchmark sim --method kalman_expert \
    --world nominal --seed 42 --frames 300 --output runs/bench_world
```

### Output files

Each run produces:
- `metadata.json` — Session configuration and timing
- `errors.csv` — Per-frame tracking error
- `summary.txt` — Human-readable summary
- `sih_report.json` — (validation suite) Threshold evaluation

### Interpreting results

Key metrics:
- **Acquisition time** — Time to first lock (target: ≤ 2s)
- **RMSE** — Root-mean-square tracking error (target: ≤ 10px)
- **Loss percentage** — Fraction of frames with lost track (target: < 5%)
- **Reacquisition time** — Time to re-lock after loss (target: ≤ 1s)
- **Processing FPS** — Pipeline throughput (target: ≥ 20 FPS)

---

## 7. Advanced Features

Enable in `configs/production.yaml`:

```yaml
advanced:
  enabled: true
  quality_analysis: true      # Image quality assessment
  uncertainty_estimation: true # Multi-source uncertainty
  adaptive_perception: true   # ROI-based detection
  fusion_enabled: true        # Classical+AI fusion
  adaptive_kalman: true       # Q/R adaptation
  maneuver_detection: true    # Motion classification
  search_controller: true     # Progressive search
  lock_quality: true          # Multi-factor lock score
  adaptive_control: true      # Gain scheduling
```

---

## 8. Troubleshooting

### No detection in simulation

- Ensure target z > camera z (target must be in front of camera)
- Check perception threshold (`threshold_value` in config)
- Use `threshold_mode: global` with `threshold_value: 20.0` for simulation

### Low FPS

- Disable advanced features: `advanced.enabled: false`
- Reduce image resolution: `camera.width: 320, camera.height: 240`
- Use simpler trajectory: `-t straight_line`

### Video benchmark fails

- Ensure OpenCV is installed: `pip install opencv-python`
- Check video format is supported (MP4, AVI, MKV, MOV)
- Try: `fsoc-bench -i video.mp4 -v` for verbose output

---

## 9. Command Reference

| Command | Description |
|---------|-------------|
| `python -m fsoc_tracker` | Smoke test (real pipeline, 5s) |
| `python -m fsoc_tracker --gui` | Launch GUI |
| `python -m fsoc_tracker -c CONFIG` | Smoke test with config |
| `fsoc-sim` | Headless simulation |
| `fsoc-sim -t TRAJ -d SEC` | Simulation with trajectory and duration |
| `fsoc-bench -i VIDEO` | Video benchmark |
| `pytest` | Run all tests |
| `pytest --cov=fsoc_tracker` | Run tests with coverage |
| `ruff check src/ tests/` | Lint code |
