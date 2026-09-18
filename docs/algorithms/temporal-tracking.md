# Temporal Tracking Algorithm

## Overview

The temporal tracker transforms independent single-frame detections into a robust, continuous estimate of the target's position and velocity. It uses a Kalman filter for state estimation and an explicit finite state machine for track lifecycle management.

The tracker is **perception-agnostic**: it consumes `Detection` objects from any backend (classical, AI, hybrid) and never sees ground truth.

## Architecture

```
Detection[]  ──▶  Association/Gate  ──▶  Kalman Filter  ──▶  TrackingState
                      │                       │
                      ▼                       ▼
                 State Machine          Track Quality
                      │
                      ▼
                 TrackingEvent[]
```

## State Machine

```
NO_TRACK  ──▶  SEARCHING  ──▶  ACQUIRING  ──▶  TRACKING
                                                │    ▲
                                                ▼    │
                    SEARCHING  ◀──  LOST  ◀──────────┘
                        ▲              │
                        │              ▼
                        └────  REACQUIRING  ──▶  TRACKING
```

### Valid Transitions

| From | To | Trigger |
|------|----|---------|
| NO_TRACK | SEARCHING | Tracker initialized, no detection |
| NO_TRACK | ACQUIRING | Detection appears at initialization |
| SEARCHING | ACQUIRING | Detection appears near expected position |
| ACQUIRING | TRACKING | `min_consecutive_hits` reached |
| ACQUIRING | SEARCHING | `acquisition_timeout_s` exceeded |
| TRACKING | LOST | `max_prediction_duration_s` exceeded without measurement |
| TRACKING | SEARCHING | Prediction window exceeded (long loss) |
| LOST | REACQUIRING | Valid detection returns within gate |
| LOST | SEARCHING | `reacquisition_timeout_s` exceeded |
| REACQUIRING | TRACKING | Stable detection confirmed |
| REACQUIRING | SEARCHING | Timeout or no valid association |

## Kalman Filter Model

### State Vector

```
x = [px, py, vx, vy]^T
```

- `px, py`: target position in image pixels
- `vx, vy`: target velocity in px/s

### State Transition (Constant Velocity)

```
px(k+1) = px(k) + vx(k) · dt
py(k+1) = py(k) + vy(k) · dt
vx(k+1) = vx(k)
vy(k+1) = vy(k)
```

Matrix form:

```
F = [1  0  dt  0 ]    Q = process noise matrix
    [0  1  0   dt]
    [0  0  1   0 ]
    [0  0  0   1 ]
```

### Measurement Model

```
z = [px, py]^T    (measured position only)
H = [1 0 0 0]    (observation matrix)
    [0 1 0 0]
```

### Process Noise (Q)

The process noise covariance models how much the target can accelerate between frames:

```
Q = G · G^T · σ²

where G is the discrete-time noise input matrix:
G = [dt²/2  0    ]
    [0      dt²/2]
    [dt     0    ]
    [0      dt   ]
```

Two tunable parameters:
- `process_noise_pos` (σ²_pos): Position process noise — higher = filter trusts measurements more
- `process_noise_vel` (σ²_vel): Velocity process noise — higher = filter adapts faster to velocity changes

### Measurement Noise (R)

```
R = [σ²_meas_x   0      ]
    [0           σ²_meas_y]
```

- `measurement_noise_x/y`: Detector precision in pixels²

### Filter Equations

**Predict:**
```
x̂⁻ = F · x̂
P⁻ = F · P · F^T + Q
```

**Update (with Joseph form for numerical stability):**
```
y = z - H · x̂⁻                    (innovation)
S = H · P⁻ · H^T + R              (innovation covariance)
K = P⁻ · H^T · S⁻¹               (Kalman gain)
x̂ = x̂⁻ + K · y                   (updated state)
P = (I - K·H) · P⁻ · (I - K·H)^T + K · R · K^T   (Joseph form)
```

## Adaptive dt

The filter derives `dt` from frame timestamps using `compute_dt()`. It handles:

- **Small dt** (< 1e-9s): Uses nominal or fallback dt
- **Large dt** (> 5s): Policy-dependent (clamp, reject, or reset)
- **Timestamp rollback**: Detected and handled gracefully
- **Irregular timestamps**: Handled naturally through dt computation

## Association and Gating

### Strategy: Nearest Neighbor

For each incoming detection:
1. Compute Euclidean distance to predicted position
2. Apply Euclidean gate: `distance ≤ association_gate_px`
3. If Mahalanobis gating enabled: compute Mahalanobis distance
4. Apply Mahalanobis gate: `d² ≤ association_gate_mahal` (chi-squared threshold)
5. Select nearest valid candidate

### Mahalanobis Distance

```
d² = y^T · S⁻¹ · y

where y = z - H · x̂⁻  (innovation)
      S = H · P⁻ · H^T + R  (innovation covariance)
```

Accounts for filter uncertainty — allows larger Euclidean distances when uncertainty is high.

## Target Loss Detection

Loss is determined by **time since last valid measurement**, not frame count:

```
time_since_measurement = current_time - last_measurement_time

if time_since_measurement > max_prediction_duration_s:
    state → LOST
```

This is FPS-independent. At 30 FPS with `max_prediction_duration_s=1.0`, approximately 30 frames can be missed. At 60 FPS, approximately 60 frames.

## Reacquisition

When target is lost:
1. Continue Kalman prediction
2. Search incoming detections near predicted position (within gate)
3. If valid detection found → REACQUIRING
4. If stable detections confirmed → TRACKING
5. If `reacquisition_timeout_s` exceeded → SEARCHING

## Track Quality

Quality is a normalized score [0, 1] combining:
- Detection confidence
- Position uncertainty (lower = higher quality)
- Consecutive detection streak
- Miss penalty

## Lock Status

`locked = True` when:
- State is TRACKING
- Quality ≥ `lock_quality_threshold`
- No consecutive misses

## Performance Logging

Events are emitted as structured `TrackingEvent` objects:
- `TRACK_INITIALIZED`, `TRACK_ACQUIRED`, `TRACK_UPDATED`
- `TRACK_PREDICTED`, `TRACK_LOST`, `TRACK_REACQUIRED`
- `ASSOCIATION_FAILED`, `GATE_REJECTED`

Each event carries a timestamp and optional metadata (acquisition time, miss duration, etc.).
