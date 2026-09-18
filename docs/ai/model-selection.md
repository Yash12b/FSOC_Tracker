# Model Selection for AI Beacon Perception

## Problem Statement

Detect small bright beacons (5-20 px diameter) in 640×480 grayscale camera images. The target is a localized bright spot, not a complex object. The system must run at ≥20 FPS on CPU with ≤10 px centroid error.

## Candidate Architectures

### 1. YOLO-family (YOLOv8-nano, YOLOv11-nano)

| Aspect | Assessment |
|--------|-----------|
| Target task fit | Bounding-box detection — designed for larger objects with complex shapes |
| Small-target performance | Poor: anchor boxes and NMS degrade for <10px targets |
| Model size | 3-6M params, 6-12 MB |
| Inference speed | ~15-30ms on CPU (too slow for 20 FPS pipeline) |
| Centroid accuracy | Bounding-box mAP does not measure centroid precision |
| Dependencies | Requires PyTorch + ultralytics at inference time |

**Verdict**: Not suitable. Overkill architecture for a centroid prediction task.

### 2. MobileNet-v2/v3

| Aspect | Assessment |
|--------|-----------|
| Target task fit | Image classification — wrong output format for localization |
| Small-target performance | Would need detection head addition |
| Model size | 2-4M params, 3-8 MB |
| Inference speed | ~10-20ms on CPU |
| Dependencies | Requires PyTorch/TFLite at inference time |

**Verdict**: Classification backbone, not a detection system. Would require significant adaptation.

### 3. Custom CNN with Detection Head

| Aspect | Assessment |
|--------|-----------|
| Target task fit | Purpose-built for heatmap centroid prediction |
| Small-target performance | Optimized conv layers + heatmap regression |
| Model size | ~15K params, 60 KB |
| Inference speed | ~1-3ms on CPU (NumPy) |
| Dependencies | Only NumPy for inference |

**Verdict**: Best fit. Tiny, fast, purpose-built for the exact task.

## Chosen Architecture: Heatmap CNN

```
Input: (1, 128, 128) grayscale
  ↓
Conv1: (16, 3×3, pad=1) → ReLU → MaxPool(2×2)    → (16, 64, 64)
Conv2: (16, 3×3, pad=1) → ReLU → MaxPool(2×2)    → (16, 32, 32)
Conv3: (16, 3×3, pad=1) → ReLU → MaxPool(2×2)    → (16, 16, 16)
  ↓
Flatten: 4096
  ↓
FC1: 4096 → 256 → ReLU
FC2: 256 → 256 → reshape → (1, 16, 16) heatmap
  ↓
Bilinear upscale → (128, 128) sigmoid heatmap
  ↓
Peak detection → (x, y, confidence)
```

### Key Design Decisions

1. **Heatmap output, not bounding box**: For a single small beacon, predicting a heatmap peak is more precise than bounding-box regression. The peak location directly gives sub-pixel centroid.

2. **8× downsampling then upscale**: The FC layer predicts a coarse 16×16 heatmap, which is bilinearly upscaled to 128×128. This is computationally efficient while preserving localization accuracy.

3. **Pure NumPy inference**: No PyTorch dependency at inference time. All operations (conv2d, maxpool, FC, sigmoid) are implemented in NumPy. This ensures the system runs on any platform with Python + NumPy.

4. **Sigmoid activation**: Output heatmap is in [0,1], representing beacon probability at each pixel. This provides both localization and confidence.

5. **He initialization**: Weight initialization uses He et al. (2015) for ReLU layers, ensuring stable forward pass magnitudes from the start.

## Training

- **Loss**: MSE between predicted heatmap and ground-truth Gaussian peak (σ=2 px)
- **Optimizer**: Gradient descent with numerical gradients (no PyTorch dependency)
- **Dataset**: Synthetic, generated from Stage 2-4 simulator + Stage 8 disturbances
- **Input normalization**: Pixel values normalized to [0, 1] (uint8 / 255)

## Why Not the Others

| Approach | Fatal Flaw |
|----------|-----------|
| YOLO | 3M+ params, anchor boxes wrong for 5-20px targets |
| MobileNet | Classification backbone, not a localization system |
| Template matching | Brittle to scale/rotation, no learned features |
| Threshold + centroid | Already implemented as classical baseline — no improvement |

## Performance Target

| Metric | Target | Classical Baseline |
|--------|--------|-------------------|
| Centroid RMSE | <10 px | ~15-25 px (varies by conditions) |
| Inference time | <5 ms | ~1-2 ms |
| Model size | <100 KB | N/A |
| Parameters | <20K | N/A |
