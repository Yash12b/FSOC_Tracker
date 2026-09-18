# Beacon Detection Algorithm

## Overview

The classical bright-spot beacon detector identifies the FSOC beacon in rendered sensor images using thresholding, connected component analysis, and weighted centroid estimation.

## Pipeline

```
Input Image → Preprocessing → Thresholding → Connected Components
    → Feature Extraction → Scoring → Centroid Estimation → Detection Output
```

### 1. Preprocessing

- **Grayscale conversion**: BGR images converted to single-channel.
- **Background estimation**: Percentile-based (default 10th percentile) to estimate ambient light level.
- **Noise estimation**: MAD (Median Absolute Deviation) of image residuals.
- **Gaussian blur**: Optional pre-smoothing (disabled by default for synthetic images).
- **Denoising**: Optional Non-Local Means denoising (disabled by default).

### 2. Thresholding

Three modes available:

| Mode | Description | Best For |
|------|-------------|----------|
| `PERCENTILE` | Threshold = background + dynamic_range × (percentile/100) | Varying illumination |
| `GLOBAL` | Fixed threshold value | Known, stable intensity |
| `ADAPTIVE` | OpenCV adaptive Gaussian threshold | Complex backgrounds |

The percentile mode adapts to the image's dynamic range: if the brightest pixel is 200 and background is 10, the threshold at 90% = 10 + 190 × 0.9 = 181.

### 3. Connected Component Analysis

After thresholding, OpenCV `connectedComponents` identifies contiguous bright regions. Candidates are filtered by area bounds (`min_candidate_area` to `max_candidate_area`).

### 4. Feature Extraction

For each candidate region:

| Feature | Description |
|---------|-------------|
| `centroid_x/y` | Geometric centroid (mean of pixel coordinates) |
| `area` | Number of pixels in region |
| `bbox` | Bounding box `(x_min, y_min, x_max, y_max)` |
| `width/height` | Bounding box dimensions |
| `aspect_ratio` | width/height (1.0 = square) |
| `circularity` | 4π × area / perimeter² (1.0 = perfect circle) |
| `mean_intensity` | Average pixel value in region |
| `max_intensity` | Peak pixel value |
| `integrated_intensity` | Sum of all pixel values |
| `local_contrast` | Mean intensity difference between region and surrounding border |

### 5. Scoring

Each candidate receives a weighted score combining four components:

```
score = (w_i × S_intensity + w_s × S_size + w_sh × S_shape + w_c × S_contrast) / (w_i + w_s + w_sh + w_c)
```

| Component | Weight | What it measures |
|-----------|--------|------------------|
| `S_intensity` | 0.30 | Peak brightness relative to 255 |
| `S_size` | 0.25 | Area match to expected beacon size |
| `S_shape` | 0.25 | Circularity and aspect ratio |
| `S_contrast` | 0.20 | Local contrast against background |

A candidate with area ≤ 0 immediately scores 0.0.

### 6. Centroid Estimation

Two methods available (configured via `centroid_method`):

- **`INTENSITY_WEIGHTED`**: Centroid = Σ(pixel_value × position) / Σ(pixel_value) — biases toward brightest pixels, better for sub-pixel accuracy on real sensors.
- **`GEOMETRIC`**: Centroid = mean(pixel_positions) — treats all pixels equally, better for uniform-intensity synthetic beacons.

### 7. Detection Decision

- Candidates are ranked by score (descending).
- The top candidate is accepted if its score ≥ `min_confidence` (default 0.3).
- Multiple candidates are stored but only the best becomes the `primary_detection`.

## Configuration

```yaml
perception:
  threshold_mode: percentile    # percentile | global | adaptive
  percentile_value: 90.0        # 0-100, higher = more selective
  min_candidate_area: 5.0
  max_candidate_area: 2000.0
  expected_size_px: 10.0        # nominal beacon diameter in pixels
  size_tolerance_px: 8.0
  min_confidence: 0.3           # 0-1, minimum score to accept
  centroid_method: intensity_weighted  # intensity_weighted | geometric
  w_intensity: 0.3              # scoring weights
  w_size: 0.25
  w_shape: 0.25
  w_contrast: 0.2
```

## Performance Characteristics

- **Deterministic**: Same input always produces same output.
- **FPS-independent**: Detection is per-frame; no temporal state.
- **Sub-pixel**: Intensity-weighted centroid achieves <1px error on synthetic images.
- **Processing time**: ~1-3ms per 640×480 frame (varies by number of candidates).

## Limitations

- Single-bright-spot assumption: designed for one primary beacon.
- No temporal tracking: each frame is independent.
- No motion prediction or Kalman filtering.
- No AI/ML: purely classical computer vision.
- Sensitive to extreme noise or saturation (handled gracefully with status codes).

## Ground Truth Separation

The detector NEVER receives ground truth. Ground truth comparison is handled exclusively by `perception/evaluation.py`:
- `compare_detection_to_ground_truth(detection, gt)` → `GroundTruthMetrics`
- `compute_rmse(errors)` → float
- `compute_centroid_error(det_x, det_y, gt_x, gt_y)` → (ex, ey, err)
