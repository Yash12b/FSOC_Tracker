# AI Beacon Perception

## Overview

The AI beacon perception subsystem provides a learned detector for small bright beacons in grayscale camera images. It uses a tiny convolutional neural network that predicts a heatmap, with the peak location indicating the beacon center.

## Architecture

### BeaconCNN

A 3-layer convolutional network with 2 fully-connected layers:

```
Input: (1, 128, 128) grayscale image normalized to [0, 1]

Conv1(1→16, 3×3) → ReLU → MaxPool(2×2)    → (16, 64, 64)
Conv2(16→16, 3×3) → ReLU → MaxPool(2×2)   → (16, 32, 32)
Conv3(16→16, 3×3) → ReLU → MaxPool(2×2)   → (16, 16, 16)

Flatten → 4096
FC(4096→256) → ReLU
FC(256→256) → reshape(1, 16, 16)

Bilinear upscale → (128, 128)
Sigmoid → heatmap ∈ [0, 1]
```

**Parameters**: ~15,872  
**Inference**: ~1-3 ms (NumPy on CPU)  
**Model size**: ~63 KB  

### Output Processing

1. **Sigmoid activation**: Converts raw logits to [0, 1] probability heatmap
2. **Peak finding**: Non-maximum suppression with `min_distance=5` pixels
3. **Coordinate mapping**: Heatmap peak (r, c) → image coordinates via bilinear interpolation
4. **Confidence**: Sigmoid value at peak location

### Coordinate Mapping

For an input image of size (H, W) and model input size (model_H, model_W):

```python
scale_x = W / model_W
scale_y = H / model_H
image_x = heatmap_peak_x * scale_x
image_y = heatmap_peak_y * scale_y
```

## Training Pipeline

### Dataset Generation

Synthetic training data is generated using the existing Stage 2-4 simulator:

1. Place beacons at random positions within the camera frame
2. Apply varying beacon sizes (5-20 px), brightness levels, and backgrounds
3. Inject disturbances: noise, fog, haze, low-light, camera jitter
4. Generate ground-truth Gaussian heatmap labels (σ=2 px)
5. Split into train/val/test with separate random seeds

**Dataset format**: `.npz` files containing `images.npy` (N, 128, 128) and `labels.npy` (N, 128, 128)

### Training Loop

- **Loss**: MSE between predicted and ground-truth heatmaps
- **Optimizer**: Gradient descent with numerical gradients (no PyTorch at runtime)
- **Early stopping**: Patience-based, monitoring validation loss
- **Metrics**: Precision (peak within threshold of ground truth)

## Hybrid Fusion

The `HybridBeaconDetector` combines classical and AI detection:

### Fusion Policies

| Policy | Description |
|--------|-------------|
| `BOTH_AGREE` | Only detect if both agree (high precision) |
| `EITHER` | Detect if either detects (high recall) |
| `AI_OR_CLASSICAL` | AI preferred, fallback to classical (default) |
| `AI_WITH_CLASSICAL_CONFIRM` | AI primary, classical must confirm nearby |
| `CLASSICAL_WITH_AI_CONFIRM` | Classical primary, AI must confirm nearby |
| `AI_UNLESS_CONFLICT` | AI always unless classical has much higher confidence |

### Proximity Check

When both detectors produce results, they are considered "agreeing" if the Euclidean distance between centroids is ≤ `proximity_threshold` (default: 10 px).

### Fallback

If the AI model fails to load (missing weights, import error), the hybrid detector automatically falls back to classical-only mode.

## Benchmark Framework

Compares detectors on the same dataset split:

```python
from fsoc_tracker.ai.benchmark import compare_detectors, benchmark_detector
from fsoc_tracker.ai.dataset import generate_split

dataset = generate_split("test", 100, config, seed=3000)

classical = ClassicalBeaconDetector()
ai = AIBeaconDetector(model_config)
hybrid = HybridBeaconDetector(model_config)

results = compare_detectors([classical, ai, hybrid], dataset)
for r in results:
    print(r.summary())
```

### Metrics Reported

- **Detection**: Precision, Recall, F1, TP/FP/TN/FN
- **Centroid**: Mean error, RMSE, P50/P90/P95/P99, max error
- **Latency**: Mean, P95, throughput (FPS)
- **Breakdowns**: By target size (small/medium/large), by disturbance type

## Model Export

### NumPy format (default)

```python
from fsoc_tracker.ai.export import save_model, load_model

save_model(model, "checkpoints/beacon_cnn/")
loaded = load_model("checkpoints/beacon_cnn/")
```

### ONNX export (optional)

```python
from fsoc_tracker.ai.export import export_onnx

export_onnx(model, "beacon_cnn.onnx")
```

Requires PyTorch for export. ONNX runtime can be used for inference.
