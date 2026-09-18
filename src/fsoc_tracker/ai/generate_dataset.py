"""Generate reproducible visual beacon datasets."""

from __future__ import annotations

import argparse
import json

from fsoc_tracker.ai.config import DatasetConfig
from fsoc_tracker.ai.dataset import generate_full_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate visual beacon datasets")
    parser.add_argument("--output", default="artifacts/datasets/beacon-v2")
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--validation-samples", type=int, default=1000)
    parser.add_argument("--test-samples", type=int, default=1000)
    parser.add_argument("--hard-test-samples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=1000)
    args = parser.parse_args()
    config = DatasetConfig(
        num_samples=args.samples,
        val_samples=args.validation_samples,
        test_samples=args.test_samples,
        hard_test_samples=args.hard_test_samples,
        train_seed=args.seed,
        val_seed=args.seed + 1000,
        test_seed=args.seed + 2000,
        hard_test_seed=args.seed + 3000,
        output_dir=args.output,
    )
    splits = generate_full_dataset(config, save=True)
    print(json.dumps({name: split.statistics() for name, split in splits.items()}, indent=2))


if __name__ == "__main__":
    main()
