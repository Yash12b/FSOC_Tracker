# Training pipeline

Synthetic labels are generated from the simulator, while runtime inputs are
restricted to rendered pixels and observable detector/tracker features.
Artifacts record dataset version, training seed, independent validation/test
seeds, sample counts, and metrics in `experiment.json`.

PyTorch is optional and loaded lazily. The normal desktop runtime does not
require a training framework.
