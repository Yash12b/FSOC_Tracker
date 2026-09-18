# Perception-to-Tracking Pipeline

## Overview

This document describes the data flow from raw image to tracking state estimate. Ground truth **never** enters the runtime tracker.

## Pipeline

```
FrameSource.read()
    │
    ▼
Frame { image, timestamp_s, source_id }
    │
    ├──▶ PerceptionEngine.detect(frame)
    │        │
    │        ▼
    │    PerceptionResult {
    │        detections: [BeaconDetection],
    │        primary_detection,
    │        processing_time_ms,
    │        status
    │    }
    │        │
    │        ▼
    │    KalmanTracker.update(detections, timestamp_s)
    │        │
    │        ├──▶ Association (nearest-neighbor + gating)
    │        ├──▶ Kalman predict(dt)
    │        ├──▶ Kalman update(measurement)
    │        └──▶ State machine transition
    │        │
    │        ▼
    │    TrackingState {
    │        state: TrackState,
    │        estimated_x/y: float,
    │        velocity_x/y: float,
    │        quality: float,
    │        locked: bool,
    │        ...
    │    }
    │        │
    │        ▼
    │    [FUTURE: Controller consumes TrackingState]
    │
    └──▶ TrackingMetricsCollector (evaluation only)
```

## Key Interfaces

### Frame → Perception

```python
frame: Frame = source.read()
result: PerceptionResult = perception_engine.detect(
    image=frame.image,
    timestamp_s=frame.timestamp_s,
    frame_index=frame.frame_index,
)
```

### Perception → Tracker

```python
state: TrackingState = tracker.update(
    detections=result.detections,
    timestamp_s=result.frame_timestamp,
    frame_metadata={"frame_index": result.frame_index},
)
```

### Tracker → Controller (Future)

```python
if state.locked:
    controller.update(state.estimated_x, state.estimated_y)
```

## Ground Truth Separation

Ground truth is used **only** by evaluation code, never by the tracker:

| Component | Uses Ground Truth? |
|-----------|-------------------|
| PerceptionEngine | No |
| KalmanTracker | No |
| EvaluationMetrics | Yes (comparison only) |
| SIH Benchmark | Yes (comparison only) |
| Controller | No |

## Tracker Output

`TrackingState` provides everything the controller needs:

| Field | Description |
|-------|-------------|
| `state` | FSM state (TRACKING, LOST, etc.) |
| `estimated_x/y` | Kalman-filtered position (px) |
| `velocity_x/y` | Estimated velocity (px/s) |
| `predicted_x/y` | One-step-ahead prediction |
| `quality` | Normalized quality score [0, 1] |
| `locked` | True if tracking is stable |
| `residual_x/y` | Innovation (measurement - prediction) |
| `uncertainty_x/y` | Position standard deviations |
| `track_age_s` | How long the track has existed |
| `acquisition_time_s` | Time to acquire the target |
| `prediction_only` | True if no measurement was used |

## Detection Interface

The tracker consumes `BeaconDetection` objects, which are the common interface for all perception backends:

```python
@dataclass
class BeaconDetection:
    detected: bool
    center_x: float
    center_y: float
    confidence: float
    timestamp_s: float
    ...
```

This interface is independent of:
- Classical CV (thresholding, centroid)
- AI detection (YOLO, custom model)
- Hybrid approaches
- External video sources
