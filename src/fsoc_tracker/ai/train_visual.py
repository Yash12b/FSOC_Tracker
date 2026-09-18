"""Command-line entry point for optional image-based visual training."""

from __future__ import annotations

import argparse
import json

from fsoc_tracker.ai.config import AIModelConfig, DatasetConfig
from fsoc_tracker.ai.dataset import generate_split
from fsoc_tracker.ai.visual_training import train_visual_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the visual beacon model")
    parser.add_argument("--output", default="artifacts/models/beacon-visual-v1.pt")
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--validation-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--input-width", type=int, default=128)
    parser.add_argument("--input-height", type=int, default=128)
    args = parser.parse_args()
    dataset_config = DatasetConfig(
        num_samples=max(10, args.samples),
        image_width=640,
        image_height=480,
        train_seed=args.seed,
        val_seed=args.seed + 1000,
    )
    train_split = generate_split(
        "train", args.samples, dataset_config, args.seed, include_disturbances=True
    )
    validation_split = generate_split(
        "validation",
        args.validation_samples,
        dataset_config,
        args.seed + 1000,
        include_disturbances=True,
    )
    result = train_visual_model(
        train_split,
        validation_split,
        args.output,
        AIModelConfig(
            input_width=args.input_width,
            input_height=args.input_height,
        ),
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
    )
    print(json.dumps(result.__dict__, indent=2))


if __name__ == "__main__":
    main()
