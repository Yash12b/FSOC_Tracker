# Learned-model audit

## Current feature-model baseline

The mission models in `fsoc_tracker.ai.learned` consume an encoded
`ObservationFeatures` record. The vector contains detection/confidence,
tracker residual and uncertainty, estimated velocity, time since detection,
latency/FPS, candidate count, and ROI radius. It does not contain simulator
target coordinates, future coordinates, trajectory identifiers, or hidden
disturbance state.

The current motion target is:

```text
[velocity_x_px_s * 0.1, velocity_y_px_s * 0.1]
```

This explains the approximately `6e-10 px` test error: the target is an
exactly deterministic function of an input feature, and ridge regression
recovers that relationship. It is a useful serialization and plumbing test,
but it is not evidence of temporal understanding, image-based prediction, or
generalization. It does not beat a constant-velocity baseline because it is
the same baseline expressed as a supervised regression task.

The trained artifacts therefore remain optional and are not enabled as the
authoritative controller.

## Visual and temporal neural path

`fsoc_tracker.ai.neural` provides optional small architectures:

- an image-only CNN that predicts a full-resolution beacon heatmap, presence,
  and uncertainty;
- a GRU that consumes histories of observable model features and predicts
  displacement and uncertainty at 25, 50, 100, 250, and 500 ms.

PyTorch is loaded lazily. The deterministic NumPy application continues to
work when PyTorch is absent. These architectures have not been selected for
production and require held-out image/sequence data, CPU latency measurements,
and closed-loop comparison against classical perception plus Kalman tracking.

## Leakage boundary

Ground truth may be used to generate labels and evaluate predictions only.
Runtime model inputs are restricted to pixels, detector/tracker estimates,
timestamps, uncertainty, and image-quality observations. Hidden simulator
state must never be passed to `ObservationFeatures`, the neural builders, or
the mission brain.
