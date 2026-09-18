# Model evaluation

Acceptance requires held-out data, comparison with the classical/Kalman
baseline, CPU latency, memory, and closed-loop behavior. The current
feature-model artifacts have independent synthetic validation/test metrics,
but no claim of superiority or physical-video generalization is made.

Models are classified as:

- **PRODUCTION:** deterministic classical perception, Kalman tracking, and
  bounded controller.
- **EXPERIMENTAL:** learned feature models, NumPy heatmap CNN, and optional
  PyTorch visual/temporal architectures.
- **REJECTED:** none yet; rejection requires a completed benchmark showing
  unacceptable quality or cost.
