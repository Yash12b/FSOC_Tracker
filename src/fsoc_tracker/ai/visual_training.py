"""Optional real image-based training for the visual beacon model.

This module deliberately imports PyTorch only inside execution paths. The
desktop runtime and deterministic NumPy baseline do not require it.
"""

from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from fsoc_tracker.ai.config import AIModelConfig
from fsoc_tracker.ai.coordinates import decode_heatmap_center
from fsoc_tracker.ai.dataset import DatasetSplit
from fsoc_tracker.ai.neural import build_visual_heatmap_model


@dataclass(frozen=True)
class VisualTrainingResult:
    epochs: int
    best_validation_loss: float
    checkpoint: str
    train_samples: int
    validation_samples: int


@dataclass(frozen=True)
class VisualEvaluationResult:
    samples: int
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    centroid_rmse_px: float
    centroid_mae_px: float
    p95_centroid_error_px: float
    mean_latency_ms: float


def _require_torch() -> tuple[Any, Any, Any]:
    try:
        import torch
        from torch import nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for visual training. Install the optional "
            "ai-train dependency; no model artifact was produced."
        ) from exc
    return torch, nn, (DataLoader, TensorDataset)


def _heatmap_targets(
    split: DatasetSplit,
    config: AIModelConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    images: list[np.ndarray] = []
    heatmaps: list[np.ndarray] = []
    presence: list[float] = []
    y_grid, x_grid = np.mgrid[
        0 : config.input_height,
        0 : config.input_width,
    ]
    for sample in split.samples:
        image = sample.image.astype(np.float32) / 255.0
        if image.shape != (config.input_height, config.input_width):
            resized = np.asarray(
                cv2.resize(
                    image,
                    (config.input_width, config.input_height),
                    interpolation=cv2.INTER_AREA,
                ),
                dtype=np.float32,
            )
        else:
            resized = image
        images.append(resized[None, :, :])
        if sample.label.visible:
            x = sample.label.center_x * config.input_width / image.shape[1]
            y = sample.label.center_y * config.input_height / image.shape[0]
            sigma = max(config.heatmap_sigma, sample.label.target_size_px / 4.0)
            heatmaps.append(
                np.exp(-((x_grid - x) ** 2 + (y_grid - y) ** 2) / (2.0 * sigma**2))
                .astype(np.float32)
            )
            presence.append(1.0)
        else:
            heatmaps.append(
                np.zeros((config.input_height, config.input_width), dtype=np.float32)
            )
            presence.append(0.0)
    return (
        np.stack(images),
        np.stack(heatmaps),
        np.asarray(presence, dtype=np.float32),
    )


def train_visual_model(
    train_split: DatasetSplit,
    validation_split: DatasetSplit,
    output: str | Path,
    model_config: AIModelConfig | None = None,
    epochs: int = 10,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    seed: int = 42,
) -> VisualTrainingResult:
    """Train on rendered sensor images and save the best checkpoint."""
    if epochs <= 0 or batch_size <= 0 or learning_rate <= 0:
        raise ValueError("epochs, batch_size, and learning_rate must be positive")
    torch, nn, loader_types = _require_torch()
    data_loader, tensor_dataset = loader_types
    torch.manual_seed(seed)
    config = model_config or AIModelConfig()
    train_x, train_h, train_p = _heatmap_targets(train_split, config)
    val_x, val_h, val_p = _heatmap_targets(validation_split, config)
    train_loader = data_loader(
        tensor_dataset(
            torch.from_numpy(train_x),
            torch.from_numpy(train_h),
            torch.from_numpy(train_p),
        ),
        batch_size=batch_size,
        shuffle=True,
    )
    model = build_visual_heatmap_model()
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    best_loss = float("inf")
    best_state: dict[str, Any] | None = None
    for _ in range(epochs):
        model.train()
        for images, targets, labels in train_loader:
            output_values = model(images)
            heatmap_logits = output_values["heatmap"].squeeze(1)
            heatmap_weights = torch.where(targets > 0.05, 8.0, 1.0)
            heatmap_loss = nn.functional.binary_cross_entropy_with_logits(
                heatmap_logits,
                targets,
                weight=heatmap_weights,
            )
            presence_loss = nn.functional.binary_cross_entropy_with_logits(
                output_values["presence"],
                labels,
                weight=torch.where(labels > 0.5, 1.0, 4.0),
            )
            loss = heatmap_loss + presence_loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_output = model(torch.from_numpy(val_x))
            validation_presence_loss = nn.functional.binary_cross_entropy_with_logits(
                validation_output["presence"],
                torch.from_numpy(val_p),
                weight=torch.where(torch.from_numpy(val_p) > 0.5, 1.0, 4.0),
            )
            validation_targets = torch.from_numpy(val_h)
            validation_heatmap_loss = nn.functional.binary_cross_entropy_with_logits(
                validation_output["heatmap"].squeeze(1),
                validation_targets,
                weight=torch.where(validation_targets > 0.05, 8.0, 1.0),
            )
            validation_value = float(validation_heatmap_loss + validation_presence_loss)
        if validation_value < best_loss:
            best_loss = validation_value
            best_state = deepcopy(model.state_dict())
    if best_state is None:
        raise RuntimeError("visual training produced no checkpoint")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, destination)
    metadata = {
        "model": "TinyVisualBeaconNet",
        "input_width": config.input_width,
        "input_height": config.input_height,
        "seed": seed,
        "epochs": epochs,
        "train_samples": len(train_split.samples),
        "validation_samples": len(validation_split.samples),
        "best_validation_loss": best_loss,
    }
    destination.with_suffix(".json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return VisualTrainingResult(
        epochs=epochs,
        best_validation_loss=best_loss,
        checkpoint=str(destination),
        train_samples=len(train_split.samples),
        validation_samples=len(validation_split.samples),
    )


def evaluate_visual_checkpoint(
    checkpoint: str | Path,
    dataset: DatasetSplit,
    model_config: AIModelConfig | None = None,
    center_tolerance_px: float = 5.0,
    presence_threshold: float = 0.5,
) -> VisualEvaluationResult:
    """Evaluate a saved visual checkpoint on an untouched split."""
    if not 0.0 <= presence_threshold <= 1.0:
        raise ValueError("presence_threshold must be in [0, 1]")
    torch, _, _ = _require_torch()
    config = model_config or AIModelConfig()
    model = build_visual_heatmap_model()
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    images, _, _ = _heatmap_targets(dataset, config)
    true_positive = false_positive = true_negative = false_negative = 0
    errors: list[float] = []
    latencies: list[float] = []
    with torch.no_grad():
        for index, sample in enumerate(dataset.samples):
            started = time.perf_counter()
            output = model(torch.from_numpy(images[index : index + 1]))
            probability = float(torch.sigmoid(output["presence"])[0])
            heatmap = torch.sigmoid(output["heatmap"])[0, 0].numpy()
            pred_x, pred_y, _ = decode_heatmap_center(
                heatmap, sample.image.shape[1], sample.image.shape[0]
            )
            latencies.append((time.perf_counter() - started) * 1000.0)
            detected = probability >= presence_threshold
            if sample.label.visible and detected:
                error = float(
                    np.hypot(
                        pred_x - sample.label.center_x,
                        pred_y - sample.label.center_y,
                    )
                )
                errors.append(error)
                if error <= center_tolerance_px:
                    true_positive += 1
                else:
                    false_negative += 1
            elif sample.label.visible:
                false_negative += 1
            elif detected:
                false_positive += 1
            else:
                true_negative += 1
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    return VisualEvaluationResult(
        samples=len(dataset.samples),
        precision=precision,
        recall=recall,
        f1=2.0 * precision * recall / max(precision + recall, 1e-9),
        false_positive_rate=false_positive / max(false_positive + true_negative, 1),
        centroid_rmse_px=float(np.sqrt(np.mean(np.square(errors)))) if errors else 0.0,
        centroid_mae_px=float(np.mean(errors)) if errors else 0.0,
        p95_centroid_error_px=float(np.percentile(errors, 95)) if errors else 0.0,
        mean_latency_ms=float(np.mean(latencies)) if latencies else 0.0,
    )
