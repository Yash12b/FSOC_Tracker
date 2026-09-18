# Coarse Pointing Control Algorithm

## Overview

The coarse pointing controller is a closed-loop PID controller that converts pixel-space tracking errors into pan/tilt rate commands for the virtual camera. It consumes `TrackingState` from the Kalman tracker and never uses ground truth.

## Architecture

```
TrackingState  ──▶  Pixel→Angle  ──▶  PID Controller  ──▶  ControlCommand
                       │                     │
                       ▼                     ▼
                  CameraIntrinsics     ControlTelemetry
```

## Control Loop

```
1. Receive TrackingState (estimated position, quality, state)
2. Convert pixel error to angular error via camera intrinsics
3. Run separate PID for pan (horizontal) and tilt (vertical)
4. Apply deadband, output saturation, anti-windup
5. Emit ControlCommand (rate commands) + ControlTelemetry
```

## Pixel-to-Angle Conversion

Uses the pinhole camera model from Stage 3:

```
h_angle = atan2(pixel_x - cx, fx)
v_angle = atan2(-(pixel_y - cy), fy)
```

Where `(fx, fy)` are focal lengths derived from FOV, and `(cx, cy)` is the principal point (image center).

## PID Controller

### Equation

```
u(t) = Kp * e(t) + Ki * ∫e(t)dt + Kd * d_filtered(e)/dt
```

### Features

| Feature | Description |
|---------|-------------|
| Anti-windup | Integral is clamped and reduced when output saturates |
| Derivative filtering | Low-pass filter on derivative term: `d_f = α * d_f_prev + (1-α) * d_raw` |
| Deadband | Errors within deadband produce zero output |
| Output saturation | Rate commands clamped to `max_pan_rate_deg_s` / `max_tilt_rate_deg_s` |
| NaN protection | NaN/inf errors produce zero output |

### Default Gains (SIH26169)

| Parameter | Pan | Tilt |
|-----------|-----|------|
| Kp | 0.5 | 0.5 |
| Ki | 0.01 | 0.01 |
| Kd | 0.1 | 0.1 |
| Output limit | 5.0 deg/s | 5.0 deg/s |
| Integral limit | 10.0 deg | 10.0 deg |
| Derivative α | 0.5 | 0.5 |

## Control Modes

| Mode | Description | Trigger |
|------|-------------|---------|
| DISABLED | Zero output | Tracker SEARCHING/ACQUIRING, or `enabled=False` |
| TRACK | PID active | Tracker TRACKING or REACQUIRING |
| PREDICT | PID using predicted position | Tracker LOST, within prediction window |
| SAFE_STOP | Zero output | Tracker LOST, prediction expired |

## State Flow

```
SEARCHING ──▶ [DISABLED]
ACQUIRING ──▶ [DISABLED]
TRACKING  ──▶ [TRACK]
REACQUIRING ──▶ [TRACK]
LOST      ──▶ [PREDICT] ──(expires)──▶ [SAFE_STOP]
NO_TRACK  ──▶ [DISABLED]
```

## Safety Properties

1. **Ground-truth isolation**: Controller never accesses ground truth
2. **Rate limiting**: Output clamped to actuator limits
3. **Anti-windup**: Integral accumulator prevented from windup
4. **NaN safety**: Invalid inputs produce zero output
5. **Prediction timeout**: Prediction mode has configurable maximum duration
6. **Quality gating**: Low-quality tracks can be rejected

## Telemetry

The controller produces `ControlTelemetry` per update, containing:

- Pixel error (x, y)
- Angular error (pan, tilt)
- PID terms (P, I, D for each axis)
- Saturated/deadband flags
- Tracking quality and state
- Control mode

## Configuration

All parameters in `ControllerConfig` (Pydantic model):

```python
ControllerConfig(
    enabled=True,
    mode=ControlMode.TRACK,
    pan_kp=0.5, pan_ki=0.01, pan_kd=0.1,
    tilt_kp=0.5, tilt_ki=0.01, tilt_kd=0.1,
    max_pan_rate_deg_s=5.0,
    max_tilt_rate_deg_s=5.0,
    deadband_deg=0.0,
    integral_limit_pan=10.0,
    integral_limit_tilt=10.0,
    derivative_filter_alpha=0.5,
    prediction_control_enabled=True,
    max_prediction_control_duration_s=0.5,
    minimum_tracking_quality=0.2,
    nan_protection=True,
)
```

## FPS Independence

The controller is fully FPS-independent:
- dt comes from timestamps or explicit time values, never hardcoded
- PID terms scale correctly with variable dt
- Tested at 10, 15, 24, 30, 60, 120 Hz

## Integration

```
Perception ──▶ Tracker ──▶ Controller ──▶ Actuator ──▶ Camera
                                    │
                                    ▼
                              ControlTelemetry
```
