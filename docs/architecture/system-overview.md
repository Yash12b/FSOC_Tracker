# FSOC Tracker - System Architecture

## Overview

The FSOC Tracker implements an AI-based virtual camera tracking system for coarse alignment of mobile Free Space Optical Communication (FSOC) terminals, as specified in SIH26169.

The system is designed around a **source-agnostic frame pipeline** that supports synthetic simulation, video files, live cameras, and network streams through a unified interface.

## System Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                     │
│  ┌─────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   CLI   │  │    GUI/HUD   │  │  Benchmark Engine │   │
│  └────┬────┘  └──────┬───────┘  └────────┬─────────┘   │
│       │              │                    │              │
├───────┴──────────────┴────────────────────┴──────────────┤
│                   PIPELINE LAYER                          │
│                                                          │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐     │
│  │ FrameSource │───▶│Perception  │───▶│  Tracking   │     │
│  └────────────┘    └────────────┘    └─────┬──────┘     │
│       │                                     │            │
│       ▼                                     ▼            │
│  ┌────────────┐                    ┌────────────┐       │
│  │   Frame    │                    │  Control   │       │
│  └────────────┘                    └─────┬──────┘       │
│                                          │               │
│                                          ▼               │
│                                    ┌────────────┐        │
│                                    │ VirtualPTZ │        │
│                                    └────────────┘        │
├──────────────────────────────────────────────────────────┤
│                    SUPPORT LAYER                         │
│  ┌──────┐ ┌─────────┐ ┌──────────┐ ┌──────────────┐    │
│  │Config│ │ Logging │ │  Metrics │ │  Time/Clock  │    │
│  └──────┘ └─────────┘ └──────────┘ └──────────────┘    │
└──────────────────────────────────────────────────────────┘
```

## Core Modules

| Module | Purpose |
|--------|---------|
| `core/` | Domain models, interfaces, exceptions, time utilities |
| `config/` | YAML configuration with Pydantic validation |
| `io/` | Frame source adapters (synthetic, video, camera, stream) |
| `perception/` | Target detection (classical CV) — **Stage 5 complete** |
| `ai/` | AI beacon perception: heatmap CNN, hybrid fusion, benchmark — **Stage 9 complete** |
| `tracking/` | State estimation, Kalman filter, target loss machine — **Stage 6 complete** |
| `control/` | PID, rate limiting, pan/tilt command generation — **Stage 7 complete** |
| `simulation/` | Virtual 3D environment, beacon trajectories |
| `simulation/camera/` | Virtual PTZ camera, projection, geometry |
| `simulation/sensor/` | Virtual optical sensor, beacon image formation, PSF |
| `disturbances/` | Noise, atmospheric, motion, turbulence models — **Stage 8 complete** |
| `metrics/` | Performance statistics (RMSE, acquisition time, etc.) |
| `benchmark/` | Standardized evaluation engine |
| `visualization/` | HUD overlay, tactical display, plots |
| `utils/` | Shared utilities including logging |
| `app/` | Entry points and lifecycle management |

## Data Flow

```
FrameSource.read()
    │
    ▼
  Frame { image, timestamp_s, source_id, ... }
    │
    ├──▶ PerceptionEngine.detect(frame)
    │        │
    │        ▼
    │    Detection { x, y, confidence }
    │        │
    │        ▼
    │    Tracker.update(detection, dt)
    │        │
    │        ▼
    │    TrackingState { status, estimated_x/y, error }
    │        │
    │        ▼
    │    Controller.compute(tracking_state, camera_state)
    │        │
    │        ▼
    │    ControlCommand { pan_speed, tilt_speed }
    │        │
    │        ▼
    │    VirtualCamera.apply(command)
    │        │
    │        └──▶ next FrameSource.read()
    │
    └──▶ MetricsCollector.record(frame, detection, tracking_state, command)
```

## Frame Lifecycle

1. **FrameSource** produces a `Frame` with a timestamp from the source.
2. The pipeline computes `dt` from consecutive frame timestamps (never hardcoded).
3. **Perception** analyzes the frame image and returns detections.
4. **Tracking** updates its state estimate using detections and dt.
5. **Control** computes pan/tilt commands to center the target.
6. **VirtualCamera** adjusts the viewport for the next frame.
7. **Metrics** records performance data for this frame.

## Time Model

**Critical design principle: dt is NEVER hardcoded to 1/30.**

```
Frame.timestamp_s  ──▶  compute_dt(current, previous)  ──▶  dt
                         │
                         ├── timestamps valid? ──▶ use actual dt
                         ├── timestamps identical? ──▶ use nominal_dt
                         ├── timestamps suspicious? ──▶ use fallback_dt
                         └── no nominal? ──▶ use fallback_dt (default 1/30)
```

This allows:
- 24/25/30/50/60/120 FPS sources
- Variable-FPS media with timestamps
- Live camera input
- Deterministic simulation stepping
- Frame-by-frame replay

## Dependency Direction

Dependencies flow **inward** toward `core/`:
- `app/` depends on everything
- `io/`, `perception/`, `tracking/`, `control/` depend on `core/`
- `core/` depends on nothing except `numpy`
- `config/` depends on `pydantic` and `yaml`

No circular imports are permitted. Each module communicates through typed interfaces defined in `core/`.

## Extension Points

| Extension Point | Interface | Purpose |
|----------------|-----------|---------|
| New frame source | `FrameSource` | Add video, camera, stream adapters |
| New detector | `PerceptionEngine` | Add AI/classical/hybrid detectors |
| New tracker | `Tracker` | Add Kalman, correlation, deep tracker |
| New controller | `Controller` | Add MPC, adaptive, feed-forward |
| New disturbance | `DisturbanceModel` | Add atmospheric, vibration models |

All extensions implement abstract interfaces from `core/interfaces.py`.

## Why 30 FPS Is Not Hard-Coded

30 FPS is one supported operating condition, not a system assumption. The SIH PS specifies "30 Hz minimum" as a performance target, not a design constraint. By deriving dt from frame timestamps:

1. The system works at any frame rate
2. Variable-FPS sources are handled gracefully
3. Simulation can run faster or slower than real-time
4. Benchmark videos at non-standard rates are supported
5. Tests can use any arbitrary FPS
6. Controllers receive accurate timing regardless of source
