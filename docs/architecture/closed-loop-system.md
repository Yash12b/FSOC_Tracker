# Closed-Loop Control System Architecture

## Overview

The closed-loop control system forms the inner loop of the FSOC tracker: TrackingState → Controller → Actuator → Camera → New Frame → Perception → Tracker → Controller (repeat).

## System Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Perception  │────▶│   Tracker    │────▶│  Controller  │────▶│   Actuator   │
│  (Stage 5)   │     │  (Stage 6)   │     │  (Stage 7)   │     │  (Stage 7)   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
        ▲                                                              │
        │                                                              ▼
┌───────┴──────┐                                              ┌──────────────┐
│    Frame     │◀─────────────────────────────────────────────│    Camera    │
│  (sensor)    │                                               │  (Stage 3)   │
└──────────────┘                                              └──────────────┘
```

## Module Dependencies

```
fsoc_tracker/
├── perception/          # Stage 5: BeaconDetection output
├── tracking/            # Stage 6: TrackingState output
├── control/             # Stage 7: ControlCommand, ControlTelemetry
│   ├── config.py        # ControllerConfig, ControlMode
│   ├── pid.py           # PIDController (reusable)
│   ├── command.py       # ControlCommand, ControlTelemetry
│   └── controller.py    # CoarsePointingController, CameraActuator
└── simulation/
    ├── camera/          # Stage 3: VirtualCamera, CameraIntrinsics
    └── sensor/          # Stage 4: VirtualSensorRenderer
```

## Data Flow

| Step | Input | Output | Module |
|------|-------|--------|--------|
| 1 | RenderedFrame | BeaconDetection[] | perception |
| 2 | BeaconDetection[] | TrackingState | tracking |
| 3 | TrackingState + CameraIntrinsics | ControlCommand + ControlTelemetry | control |
| 4 | ControlCommand + dt | Camera updated | control (actuator) |
| 5 | Camera + WorldTargetState | RenderedFrame | simulation |

## Key Design Decisions

### Ground-Truth Isolation
- Controller and tracker never access ground truth
- Only perception evaluation code uses ground truth
- This matches real hardware where ground truth is unavailable

### Rate Commands, Not Position
- Controller outputs rate commands (deg/s), not absolute angles
- Matches physical actuator behavior (speed-limited servos)
- VirtualCamera enforces rate limits via `update(dt)`

### FPS Independence
- All dt values come from timestamps, never hardcoded
- PID controller tested at 10-120 Hz
- Consistent behavior across frame rates

### Modular Architecture
- Each stage is independently testable
- Stages can be replaced (e.g., AI perception for classical)
- Clear interfaces between modules

## SIH26169 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Acquisition time | ≤ 2 s | 0.1 s (sim) |
| Tracking error | ≤ 10 px | ~19 px (sim) |
| Target loss | < 5 % | N/A |
| Re-acquisition | ≤ 1 s | N/A |
| Processing rate | ≥ 20 FPS | 0.28 ms/frame |

## Control Loop Timing

At 30 Hz control rate:
- dt = 33.3 ms
- Controller compute: ~0.03 ms
- Actuator apply: ~0.01 ms
- Total control overhead: ~0.04 ms (< 1.5% of frame budget)

## Test Coverage

92 tests covering:
- PID controller (basic, P/I/D terms, anti-windup, deadband, saturation, reset, edge cases)
- Controller modes (disabled, track, predict, safe stop)
- Pixel-to-angle conversion
- Telemetry generation
- Camera actuator
- Closed-loop convergence
- Variable FPS stability
- Tracker integration
- SIH26169 target compliance
