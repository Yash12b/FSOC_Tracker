"""Model export and loading utilities.

Supports saving/loading model weights in NumPy .npz format.
Optional ONNX export when the model is trained with PyTorch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from fsoc_tracker.ai.config import AIModelConfig
from fsoc_tracker.ai.model import BeaconCNN


def save_model(
    model: BeaconCNN,
    path: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save model weights and metadata.

    Args:
        model: trained BeaconCNN
        path: directory path to save into
        metadata: optional metadata dict
    """
    save_dir = Path(path)
    save_dir.mkdir(parents=True, exist_ok=True)

    # Save weights
    weights = model.get_weights()
    np.savez(save_dir / "weights.npz", **weights)

    # Save config
    config_dict = model.config.model_dump()
    with open(save_dir / "config.json", "w") as f:
        json.dump(config_dict, f, indent=2)

    # Save metadata
    meta = {
        "num_parameters": model.count_parameters(),
        "model_size_bytes": model.model_size_bytes(),
        "architecture": model.config.architecture.value,
    }
    if metadata:
        meta.update(metadata)

    with open(save_dir / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)


def load_model(
    path: str,
    config: AIModelConfig | None = None,
) -> BeaconCNN:
    """Load model weights from directory.

    Args:
        path: directory containing weights.npz and config.json
        config: optional config override (uses saved config if None)

    Returns:
        Loaded BeaconCNN model.
    """
    load_dir = Path(path)

    # Load config if not provided
    if config is None:
        config_path = load_dir / "config.json"
        if config_path.exists():
            with open(config_path) as f:
                config_dict = json.load(f)
            config = AIModelConfig(**config_dict)
        else:
            config = AIModelConfig()

    # Create and load model
    model = BeaconCNN(config)
    weights_path = load_dir / "weights.npz"
    data = np.load(weights_path)
    weights = {k: data[k] for k in data.files}
    model.set_weights(weights)

    return model


def export_onnx(
    model: BeaconCNN,
    path: str,
    input_shape: tuple[int, ...] | None = None,
) -> str:
    """Export model to ONNX format (requires torch).

    Args:
        model: trained BeaconCNN
        path: output .onnx file path
        input_shape: input tensor shape (default: (1, 1, H, W))

    Returns:
        Path to exported ONNX file.

    Raises:
        ImportError: if PyTorch is not available.
    """
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        raise ImportError(
            "PyTorch is required for ONNX export. "
            "Install with: pip install torch"
        ) from None

    class _Wrapper(nn.Module):
        def __init__(self, beacon_model: BeaconCNN):
            super().__init__()
            self.model = beacon_model

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # Run through NumPy model
            x_np = x.detach().numpy()
            outputs = []
            for i in range(x_np.shape[0]):
                out = self.model.forward(x_np[i, 0])
                outputs.append(out.heatmap[np.newaxis, :, :])
            return torch.tensor(np.stack(outputs))

    if input_shape is None:
        input_shape = (1, 1, model.config.input_height, model.config.input_width)

    wrapper = _Wrapper(model)
    wrapper.eval()

    dummy = torch.randn(*input_shape)
    torch.onnx.export(
        wrapper,
        dummy,
        path,
        input_names=["input"],
        output_names=["heatmap"],
        dynamic_axes={"input": {0: "batch"}, "heatmap": {0: "batch"}},
    )

    return path
