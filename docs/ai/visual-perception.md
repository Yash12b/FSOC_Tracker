# Visual perception

The authoritative runtime detector is the classical beacon detector. The
existing NumPy heatmap CNN accepts only the camera image, but its default
weights are random (`weights_source=random`) and are therefore experimental.
Loaded weights are marked `trained` and exposed in diagnostics.

An optional PyTorch `TinyVisualBeaconNet` is available in
`fsoc_tracker.ai.neural`. It predicts an image heatmap, presence probability,
and uncertainty. It is not enabled by default until image-level held-out
benchmarks demonstrate an improvement over the classical detector.
