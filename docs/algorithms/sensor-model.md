# Sensor Model (Stage 4)

## Overview

The sensor module converts mathematically projected 3D beacons into realistic 2D camera images that future perception algorithms can process. It separates **camera geometry** (projection) from **sensor image formation** (beacon rendering).

## Architecture

```
VirtualCamera (projection)
      │
      v
VirtualSensorRenderer
      │
      ├── background image
      ├── beacon deposit (per target)
      ├── PSF blur (optional)
      ├── clipping to dynamic range
      │
      v
  RenderedFrame
      ├── image (uint8 ndarray)  →  perception
      ├── ground_truths (metadata only)  →  evaluation
      └── metadata
```

## Image Representation

- **Default**: Monochrome uint8, shape `(height, width)`
- **640×480** at default SIH26169 configuration
- Optional colour modes supported via config

## Beacon Image Formation

### Shapes
- **Square**: Hard-edged or soft-edged rectangular beacon
- **Circular**: Hard-edged or Gaussian-softened circular spot

### Soft Edges (Default)
Gaussian intensity profile where FWHM matches the requested apparent size:
```
FWHM = 2√(2ln2) · σ ≈ 2.355 · σ
σ = half_size / 2.355
```

### Hard Edges
Binary deposit: all pixels within the beacon footprint get peak intensity.

### Sub-Pixel Location
Beacon center is a floating-point coordinate. Anti-aliased deposition ensures the centroid is not forced to integer pixels. This enables sub-pixel accuracy evaluation.

## Apparent Size Policy

### MODE A — Fixed Pixel Size (Default)
Returns configured `beacon_default_size_px` (default: 10 px).
Clamped to `[minimum_beacon_size_px, maximum_beacon_size_px]` (5-20 px).

### MODE B — Distance-Based (Interface)
Future: `apparent_size = 2 · focal_length_px · tan(angular_size / 2)`

## Point-Spread Function

2D Gaussian kernel:
```
G(x,y) ∝ exp(-(x²+y²) / (2σ²))
```

- Configurable sigma in pixels
- Applied only to beacon region (efficient)
- Normalized (sums to 1.0)

## Intensity Model

| Parameter | Default | Description |
|-----------|---------|-------------|
| background_level | 5.0 | Uniform background intensity |
| beacon_peak_intensity | 255.0 | Maximum beacon brightness |
| max_intensity | 255.0 | Sensor saturation limit |

Output clipped to `[0, max_intensity]`.

## Clipping States

| State | Condition |
|-------|-----------|
| VISIBLE | Entirely within frame |
| PARTIAL | Partially outside frame |
| OUTSIDE | Entirely outside frame |
| BEHIND_CAMERA | depth ≤ 0 |

## Ground Truth Metadata

Ground truth is **metadata only** — never drawn into the perception image.

```python
GroundTruth:
    target_id
    target_visible
    visibility          # VISIBLE/PARTIAL/OUTSIDE/BEHIND_CAMERA
    target_world_position
    target_camera_position
    target_pixel_x      # sub-pixel float
    target_pixel_y      # sub-pixel float
    target_bbox         # integer (x1, y1, x2, y2)
    target_size_px
    horizontal_angle_deg
    vertical_angle_deg
    depth
    brightness
```

## Rendering Pipeline

1. Initialize image with background level
2. Add optional background noise (deterministic per seed)
3. For each target:
   a. Project via Stage-3 camera model
   b. Determine visibility state
   c. Compute apparent size
   d. Deposit beacon onto image
   e. Record ground truth metadata
4. Apply PSF if enabled
5. Clip to dynamic range
6. Convert to uint8

## Simplifications

- No physical optical propagation model
- PSF is a mathematical Gaussian, not measured PSF
- No inverse-square attenuation (yet)
- No exposure/gain simulation (yet)
- No atmospheric effects (Stage 9)
- No sensor noise beyond optional background noise

## API Usage

```python
from fsoc_tracker.simulation.sensor import VirtualSensorRenderer, SensorConfig

config = SensorConfig(beacon_default_size_px=10.0, enable_psf=True, psf_sigma=1.5)
renderer = VirtualSensorRenderer(config)

rendered = renderer.render(camera, targets, timestamp_s)
image = rendered.image  # uint8 for perception
gt = rendered.ground_truths  # evaluation metadata only
```
