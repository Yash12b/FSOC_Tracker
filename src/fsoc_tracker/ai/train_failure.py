"""Train failure predictor on temporal observable data.

Usage:
    python -m fsoc_tracker.ai.train_failure --dataset artifacts/datasets/temporal-v1 --output artifacts/models/failure-v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from fsoc_tracker.ai.failure_predictor import FailurePredictor
from fsoc_tracker.ai.mission import ObservationFeatures


def _load_windows(
    dataset_dir: str, split: str, window_size: int = 10
) -> tuple[list[list[ObservationFeatures]], list[bool]]:
    """Load temporal dataset and create sliding windows with failure labels."""
    base = Path(dataset_dir) / split
    features = np.load(base / "features.npy")
    mask = np.load(base / "mask.npy")
    failure = np.load(base / "failure_labels.npy")

    n_seq, t_max = features.shape[:2]
    windows: list[list[ObservationFeatures]] = []
    labels: list[bool] = []

    for i in range(n_seq):
        valid_count = int(mask[i].sum())
        for j in range(window_size, valid_count):
            window_feats = []
            for k in range(j - window_size, j):
                fv = features[i, k]
                window_feats.append(ObservationFeatures(
                    timestamp_s=float(fv[0]),
                    detected=bool(fv[1]),
                    confidence=float(fv[2]),
                    residual_px=float(fv[3]),
                    uncertainty_x_px=float(fv[4]),
                    uncertainty_y_px=float(fv[5]),
                    velocity_x_px_s=float(fv[6]),
                    velocity_y_px_s=float(fv[7]),
                    distance_from_center_px=float(fv[8]),
                    time_since_detection_s=float(fv[9]),
                    latency_ms=float(fv[10]),
                    source_fps=float(fv[11]),
                    processing_fps=float(fv[12]),
                    candidate_count=int(fv[13]),
                    roi_radius_px=float(fv[14]),
                ))
            windows.append(window_feats)
            labels.append(bool(failure[i, j]))

    return windows, labels


def train_failure_predictor(
    dataset_dir: str = "artifacts/datasets/temporal-v1",
    output_dir: str = "artifacts/models/failure-v1",
    window_size: int = 10,
    seed: int = 42,
) -> dict[str, float]:
    """Train failure predictor and save."""
    print(f"[FAILURE] Loading dataset from {dataset_dir}")
    train_w, train_l = _load_windows(dataset_dir, "train", window_size)
    val_w, val_l = _load_windows(dataset_dir, "validation", window_size)
    test_w, test_l = _load_windows(dataset_dir, "test", window_size)

    print(f"[FAILURE] Train: {len(train_w)}, Val: {len(val_w)}, Test: {len(test_w)} windows")
    print(f"[FAILURE] Train failure rate: {sum(train_l)/len(train_l):.3f}")

    fp = FailurePredictor(window_size=window_size, ridge=1e-3)
    train_acc = fp.fit(train_w, train_l)
    val_metrics = fp.evaluate(val_w, val_l)
    test_metrics = fp.evaluate(test_w, test_l)

    print(f"  Train acc: {train_acc:.3f}")
    print(f"  Val: acc={val_metrics['accuracy']:.3f} f1={val_metrics['f1']:.3f}")
    print(f"  Test: acc={test_metrics['accuracy']:.3f} f1={test_metrics['f1']:.3f}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fp.save(out / "failure-v1.npz")
    metadata = {
        "model": "FailurePredictor-logistic-v1",
        "window_size": window_size,
        "train_samples": len(train_w),
        "val_samples": len(val_w),
        "test_samples": len(test_w),
        "train_failure_rate": sum(train_l) / len(train_l),
        "train_accuracy": train_acc,
        "val": val_metrics,
        "test": test_metrics,
        "seed": seed,
    }
    (out / "experiment.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"[FAILURE] Saved to {out}")
    return {"val_accuracy": val_metrics["accuracy"], "val_f1": val_metrics["f1"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train failure predictor")
    parser.add_argument("--dataset", default="artifacts/datasets/temporal-v1")
    parser.add_argument("--output", default="artifacts/models/failure-v1")
    parser.add_argument("--window-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = train_failure_predictor(args.dataset, args.output, args.window_size, args.seed)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
