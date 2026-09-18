# Disturbance Pipeline Architecture

## Overview

The disturbance pipeline provides a composable system for degrading clean virtual images with realistic environmental effects. It separates geometric (pre-render) from image-space (post-render) disturbances.

## Pipeline Flow

```
NOMINAL CAMERA POSE
        │
        ▼
┌─────────────────────────────────┐
│   PRE-RENDER DISTURBANCES       │
│                                 │
│   Camera Jitter ──┐             │
│                    ├──► angular │
│   Platform Motion ─┘    offset  │
└─────────────┬───────────────────┘
              │
              ▼
     EFFECTIVE CAMERA POSE
              │
              ▼
     SENSOR RENDERER
              │
              ▼
     CLEAN RENDERED IMAGE
              │
              ▼
┌─────────────────────────────────┐
│   POST-RENDER DISTURBANCES      │
│                                 │
│   Turbulence Warp               │
│        │                        │
│        ▼                        │
│   Atmospheric Effects           │
│   ├── Haze                      │
│   ├── Fog                       │
│   ├── Rain                      │
│   └── Low Light                 │
│        │                        │
│        ▼                        │
│   Sensor Noise                  │
│   ├── Gaussian                  │
│   ├── Poisson                   │
│   └── Salt-and-Pepper           │
└─────────────┬───────────────────┘
              │
              ▼
     DISTURBED IMAGE
              │
              ▼
     PERCEPTION → TRACKING → CONTROL
```

## Key Design Decisions

### 1. Ground-Truth Invariance

Disturbances modify:
- Effective camera pose
- Rendered image
- Apparent visibility

Disturbances MUST NOT corrupt:
- World target positions
- Target trajectories
- Evaluator ground truth

### 2. Separation of Domains

| Domain | Type | Location |
|--------|------|----------|
| Camera Jitter | Geometric | Pre-render |
| Platform Motion | Geometric | Pre-render |
| Turbulence | Geometric warp | Post-render |
| Atmospheric | Image intensity | Post-render |
| Sensor Noise | Image intensity | Post-render |

### 3. Deterministic Reproducibility

Each disturbance uses a separate RNG stream:
```python
rng = np.random.default_rng(seed + frame_index * DOMAIN_OFFSET)
```

### 4. Runtime Reconfigurability

All parameters can be changed at runtime without restarting:
```python
pipeline.set_config(new_config)
```

## API

### DisturbancePipeline

```python
pipeline = DisturbancePipeline(config)

# Pre-render
effective_pose = pipeline.compute_effective_pose(nominal_pose, context)

# Post-render
disturbed_image = pipeline.apply_to_image(clean_image, context)

# Telemetry
telemetry = pipeline.last_telemetry
performance = pipeline.last_performance
```

### DisturbanceContext

Typed data model containing:
- `timestamp_s`, `dt`, `frame_index`
- `image_width`, `image_height`
- `camera_pose`, `platform_state`, `environment`
- `random_seed`

### EffectiveCameraPose

```python
@dataclass
class EffectiveCameraPose:
    position_x/y/z: float
    pan_deg, tilt_deg, roll_deg: float
    jitter_offset_x_px, jitter_offset_y_px: float
    platform_offset_x_px, platform_offset_y_px: float
```

## Configuration

```python
DisturbanceConfig(
    enabled=True,
    noise=NoiseConfig(
        enabled=True,
        gaussian_sigma=5.0,
        salt_pepper_density=0.05,
        poisson_enabled=True,
        poisson_scale=1.5,
    ),
    atmosphere=AtmosphereConfig(
        enabled=True,
        mode=AtmosphereMode.FOG,
        fog_strength=0.3,
        rain_density=0.2,
        low_light_factor=0.8,
    ),
    jitter=JitterConfig(
        enabled=True,
        model=JitterModel.BOUNDED,
        amplitude_px=5.0,
    ),
    platform_motion=PlatformMotionConfig(
        enabled=True,
        type=PlatformMotionType.CIRCULAR,
        amplitude_x_px=10.0,
        amplitude_y_px=8.0,
    ),
    turbulence=TurbulenceConfig(
        enabled=True,
        strength=2.0,
        spatial_scale=50.0,
    ),
)
```

## Severity Presets

| Preset | Noise σ | SP | Haze | Fog | Rain | LowLight | Jitter px | Platform px |
|--------|---------|-----|------|-----|------|----------|-----------|-------------|
| OFF | 0 | 0 | 0 | 0 | 0 | 1.0 | 0 | 0 |
| CLEAR | 0 | 0 | 0 | 0 | 0 | 1.0 | 0 | 0 |
| LIGHT | 2 | 0.02 | 0.15 | 0 | 0 | 1.0 | 2 | 0 |
| MODERATE | 5 | 0.05 | 0.2 | 0.3 | 0 | 1.0 | 5 | 5 |
| SEVERE | 10 | 0.10 | 0.3 | 0.5 | 0.3 | 0.7 | 10 | 10 |
| EXTREME | 20 | 0.15 | 0.5 | 0.7 | 0.6 | 0.4 | 20 | 20 |

## Performance

Per-stage timing is tracked in `DisturbancePerformance`:
- `total_ms`: Total pipeline time
- `geometry_ms`: Pre-render computation
- `atmosphere_ms`: Atmospheric effects
- `noise_ms`: Sensor noise
- `turbulence_ms`: Turbulence warp

## Integration with Simulation

```
SimulationEngine.step(dt)
    │
    ▼
WorldState (target positions)
    │
    ├──▶ VirtualSensorRenderer.render(camera, targets)
    │         │
    │         ▼
    │    RenderedFrame (clean image)
    │         │
    │         ▼
    │    DisturbancePipeline.apply_to_image(clean, context)
    │         │
    │         ▼
    │    Disturbed Image ──▶ Perception ──▶ Tracking ──▶ Control
    │
    └──▶ CameraActuator.apply(command, dt)
              │
              ▼
         Camera moves (nominal pose)
```

## Test Coverage

94 tests covering:
- Noise models (Gaussian, Poisson, Salt-and-Pepper, combinations)
- Atmospheric models (Haze, Fog, Rain, LowLight, combinations)
- Motion disturbances (Jitter models, Platform motion types)
- Turbulence (field generation, warp)
- Pipeline (pre-render, post-render, disabled, composition)
- Config validation
- Deterministic reproducibility
- FPS independence (10/30/60/120 Hz)
- Severity presets
- Ground-truth invariance
- Telemetry and performance
- Closed-loop tracking under disturbances
- Enable/disable runtime toggle
