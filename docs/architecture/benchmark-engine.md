# Benchmark Engine Architecture

## Overview

The benchmark engine provides quantitative evaluation of the entire FSOC tracking pipeline. It supports four modes:

1. **Synthetic** — full closed-loop simulation with ground truth
2. **External Video** — MP4/AVI/MKV input directly to perception (bypasses virtual camera)
3. **Live Camera** — webcam/USB camera performance testing
4. **Offline Dataset** — pre-recorded frame sequences

## Architecture

```
BenchmarkSession
      │
      ├──▶ FrameSource (Synthetic / Video / Live)
      │         │
      │         ▼
      │      Frame { image, timestamp_s, frame_index }
      │         │
      │         ├──▶ PerceptionEngine.detect()
      │         │         │
      │         │         ▼
      │         │    PerceptionResult { detections, centroid }
      │         │         │
      │         │         ▼
      │         │    KalmanTracker.update()
      │         │         │
      │         │         ▼
      │         │    TrackingState { estimated_x/y, locked }
      │         │
      │         └──▶ MetricsCollector.record_frame()
      │
      ├──▶ GroundTruthProvider (optional)
      │         │
      │         └──▶ MetricsCollector (ground truth comparison)
      │
      ▼
BenchmarkResult
      │
      ├──▶ export_json()
      ├──▶ export_csv()
      ├──▶ export_event_log()
      ├──▶ generate_html_report()
      └──▶ generate_plots()
```

## Ground Truth Separation (Strict Rule)

Ground truth is **NEVER** consumed by perception, tracking, or control. The data flow is:

```
Frame ──▶ Perception ──▶ Tracker ──▶ Controller  (algorithm path)

Frame metadata ──▶ GroundTruthProvider ──▶ MetricsCollector  (evaluation path)
```

Ground truth joins **only** for evaluation in the MetricsCollector.

## Benchmark Modes

### Mode A: Synthetic Closed-Loop

```
World ──▶ Camera ──▶ Sensor ──▶ Disturbances ──▶ Frame
                                                  │
                                          Perception ──▶ Tracker ──▶ Controller
                                                  │
                                          Ground Truth ──▶ Metrics
```

Full simulation with configurable trajectories, disturbances, and ground truth.

### Mode B: External Video

```
MP4/AVI/MKV ──▶ VideoBenchmarkSource ──▶ Frame
                                            │
                                    Perception ──▶ Tracker
                                            │
                                    Ground Truth (optional sidecar) ──▶ Metrics
```

Bypasses virtual camera. Video represents what the camera actually sees.

### Mode C: Live Camera

```
Webcam ──▶ LiveCameraSource ──▶ Frame ──▶ Perception ──▶ Tracker ──▶ Metrics
```

No ground truth. Reports NOT_EVALUABLE for accuracy metrics.

### Mode D: Offline Dataset

Pre-recorded frame sequences processed identically to external video.

## Timestamp Strategy

1. **Prefer source timestamps** (container/presentation timestamps)
2. **Fallback to nominal FPS** when timestamps unavailable
3. **Never assume dt = 1/30**

Metadata records `timestamp_source` ("source" or "derived_from_nominal_fps").

## Frame Metrics

Per-frame data collected:
- Timestamps, dt, source FPS
- Perception: detected, confidence, centroid
- Tracking: estimated position, state, lock, uncertainty
- Control: pan/tilt error and commands
- Ground truth: true position, error
- Timing: per-stage processing time

## Export Formats

- `benchmark_result.json` — machine-readable summary
- `frame_metrics.csv` — per-frame data
- `event_log.csv` — acquisition/loss/reacquisition events
- `report.html` — human-readable HTML report
- `plots/` — PNG visualizations (error, latency, lock state)
