"""Optional visual and temporal neural architectures.

The runtime baseline remains NumPy-only.  These builders intentionally load
PyTorch lazily so the desktop application remains offline and CPU-capable
without making a training framework a mandatory dependency.

The visual model consumes only image tensors.  The temporal model consumes a
sequence of model-observable features and returns future displacement and
uncertainty for fixed horizons.  Neither model accepts simulator state,
ground-truth coordinates, disturbance labels, or trajectory identifiers.
"""

# The optional PyTorch API is intentionally typed as a backend-defined module.
# Its concrete types cannot be imported when the optional dependency is absent.
# ruff: noqa: ANN401

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def torch_backend_available() -> bool:
    """Return whether the optional PyTorch backend can be imported."""
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def _torch() -> Any:
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for optional neural training/inference; "
            "the deterministic NumPy baseline remains available"
        ) from exc
    return torch, nn


def build_visual_heatmap_model(
    base_channels: int = 16,
) -> Any:
    """Build a small image-only beacon heatmap network.

    Input shape is ``(N, 1, H, W)``.  The output dictionary contains a
    full-resolution heatmap, presence probability, and positive uncertainty.
    """
    if base_channels < 4:
        raise ValueError("base_channels must be at least 4")
    _, nn = _torch()

    class TinyVisualBeaconNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, base_channels, 3, padding=1),
                nn.GroupNorm(4, base_channels),
                nn.ReLU(inplace=True),
                nn.Conv2d(base_channels, base_channels * 2, 3, padding=1),
                nn.GroupNorm(4, base_channels * 2),
                nn.ReLU(inplace=True),
                nn.Conv2d(base_channels * 2, base_channels * 2, 3, padding=1),
                nn.ReLU(inplace=True),
            )
            self.heatmap = nn.Conv2d(base_channels * 2, 1, 1)
            self.presence = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),
                nn.Linear(base_channels * 2, 1),
            )
            self.uncertainty = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Flatten(),
                nn.Linear(base_channels * 2, 2),
            )

        def forward(self, image: Any) -> dict[str, Any]:
            features = self.features(image)
            return {
                "heatmap": self.heatmap(features),
                "presence": self.presence(features).squeeze(-1),
                "uncertainty": nn.functional.softplus(
                    self.uncertainty(features)
                ),
            }

    return TinyVisualBeaconNet()


def build_temporal_predictor(
    feature_dim: int = 15,
    hidden_dim: int = 32,
    horizons_s: Sequence[float] = (0.025, 0.05, 0.1, 0.25, 0.5),
) -> Any:
    """Build a GRU predictor for observable feature histories.

    Input shape is ``(N, T, feature_dim)``.  Outputs have shape
    ``(N, len(horizons), 2)`` for displacement and uncertainty.
    """
    if feature_dim <= 0 or hidden_dim <= 0:
        raise ValueError("feature_dim and hidden_dim must be positive")
    if not horizons_s or any(horizon <= 0 for horizon in horizons_s):
        raise ValueError("horizons_s must contain positive values")
    _, nn = _torch()
    horizon_count = len(tuple(horizons_s))

    class TemporalBeaconPredictor(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.gru = nn.GRU(feature_dim, hidden_dim, batch_first=True)
            self.displacement = nn.Linear(hidden_dim, horizon_count * 2)
            self.uncertainty = nn.Linear(hidden_dim, horizon_count * 2)

        def forward(self, sequence: Any) -> dict[str, Any]:
            _, hidden = self.gru(sequence)
            state = hidden[-1]
            shape = (sequence.shape[0], horizon_count, 2)
            return {
                "displacement": self.displacement(state).reshape(shape),
                "uncertainty": nn.functional.softplus(
                    self.uncertainty(state).reshape(shape)
                ),
            }

    return TemporalBeaconPredictor()
