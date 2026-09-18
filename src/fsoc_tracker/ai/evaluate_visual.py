"""Evaluate a trained visual checkpoint on test and hard-test splits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from fsoc_tracker.ai.config import AIModelConfig
from fsoc_tracker.ai.dataset import BeaconLabel, DatasetSample, DatasetSplit
from fsoc_tracker.ai.visual_training import evaluate_visual_checkpoint


def _load(root: Path, name: str) -> DatasetSplit:
    split_dir = root / name
    images = np.load(split_dir / "images.npy")
    labels = json.loads((split_dir / "labels.json").read_text(encoding="utf-8"))
    return DatasetSplit(
        [
            DatasetSample(images[index], BeaconLabel(**label), index)
            for index, label in enumerate(labels)
        ],
        name,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a visual checkpoint")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--dataset", default="artifacts/datasets/beacon-v2")
    parser.add_argument("--input-width", type=int, default=64)
    parser.add_argument("--input-height", type=int, default=64)
    parser.add_argument("--presence-threshold", type=float, default=0.5)
    parser.add_argument("--output", default="")
    parser.add_argument("--debug-dir", default="")
    parser.add_argument("--debug-count", type=int, default=12)
    args = parser.parse_args()
    config = AIModelConfig(
        input_width=args.input_width,
        input_height=args.input_height,
    )
    report = {
        name: evaluate_visual_checkpoint(
            args.checkpoint,
            _load(Path(args.dataset), name),
            config,
            presence_threshold=args.presence_threshold,
        ).__dict__
        for name in ("test", "hard_test")
    }
    if args.debug_dir:
        _write_debug_examples(
            Path(args.checkpoint),
            _load(Path(args.dataset), "hard_test"),
            config,
            Path(args.debug_dir),
            args.debug_count,
        )
    output = json.dumps(report, indent=2)
    print(output)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")


def _write_debug_examples(
    checkpoint: str,
    dataset: DatasetSplit,
    config: AIModelConfig,
    output: Path,
    count: int,
) -> None:
    """Write offline-only overlays with labels and model predictions."""
    import torch

    from fsoc_tracker.ai.coordinates import decode_heatmap_center
    from fsoc_tracker.ai.neural import build_visual_heatmap_model

    output.mkdir(parents=True, exist_ok=True)
    model = build_visual_heatmap_model()
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    for index, sample in enumerate(dataset.samples[: max(0, count)]):
        image = sample.image
        resized = cv2.resize(
            image.astype(np.float32) / 255.0,
            (config.input_width, config.input_height),
            interpolation=cv2.INTER_AREA,
        )
        with torch.no_grad():
            result = model(torch.from_numpy(resized[None, None]))
            heatmap = torch.sigmoid(result["heatmap"])[0, 0].numpy()
            probability = float(torch.sigmoid(result["presence"])[0])
        pred_x, pred_y, _ = decode_heatmap_center(
            heatmap, image.shape[1], image.shape[0]
        )
        canvas = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if sample.label.visible:
            cv2.drawMarker(
                canvas,
                (round(sample.label.center_x), round(sample.label.center_y)),
                (0, 255, 0),
                cv2.MARKER_CROSS,
                12,
                1,
            )
        cv2.drawMarker(
            canvas,
            (round(pred_x), round(pred_y)),
            (0, 0, 255),
            cv2.MARKER_TILTED_CROSS,
            12,
            1,
        )
        cv2.putText(
            canvas,
            f"p={probability:.3f} gt={sample.label.visible}",
            (8, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )
        cv2.imwrite(str(output / f"{index:04d}.png"), canvas)


if __name__ == "__main__":
    main()
