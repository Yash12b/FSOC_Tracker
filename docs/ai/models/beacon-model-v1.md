# Beacon visual model v1

## Status

**Experimental.** A real checkpoint was trained on 1,000 rendered images with
200 validation images and evaluated on independent 200-image test and
hard-test splits. It is not promoted by default because hard-test quality is
poor.

## Architecture

`TinyVisualBeaconNet` is a small image-only convolutional network. It accepts a
normalized grayscale sensor image and returns a spatial heatmap, presence
logit, and two positive uncertainty values. Heatmap coordinates are mapped
from model dimensions to source-image dimensions by the same width/height
scale factors used by `AIBeaconDetector`.

## Training

Training uses rendered sensor images from `DatasetSplit`. Ground-truth center
coordinates are used only to create Gaussian heatmap labels. Hard negatives,
subpixel centers, target sizes from 5–20 px, distractors, and configured
disturbances are included. The model never receives target state or simulator
coordinates as input.

Run with the optional training dependency:

```bash
pip install -e ".[ai-train]"
python -m fsoc_tracker.ai.train_visual
```

The command fails explicitly when PyTorch is unavailable and does not create a
pretend trained artifact.

## Acceptance requirements

Before promotion, record held-out precision, recall, F1, centroid MAE/RMSE,
P50/P90/P95/P99/max error, target-size and disturbance breakdowns, CPU
latency, memory, and comparison against classical and hybrid perception.
## Measured checkpoint

The current measured artifact is
`artifacts/models/beacon-visual-v1/checkpoint.pt`.

Standard test:

- precision: `0.814`
- recall: `0.597`
- F1: `0.689`
- centroid RMSE: `167.72 px`
- centroid MAE: `65.29 px`
- centroid P95: `486.85 px`
- mean CPU latency: `2.37 ms`

Hard test:

- precision: `0.254`
- recall: `0.284`
- F1: `0.268`
- false-positive rate: `1.000`
- centroid RMSE: `360.05 px`
- centroid MAE: `275.97 px`
- centroid P95: `637.67 px`
- mean CPU latency: `2.40 ms`

These results demonstrate that training and evaluation are real, but also
demonstrate that this checkpoint is not suitable for production tracking.
