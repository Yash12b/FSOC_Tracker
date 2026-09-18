"""Train mission models on real observable tracking data.

Replaces the random-data training in train_models.py with data
from the temporal observable dataset generator.

Usage:
    python -m fsoc_tracker.ai.train_mission_real --dataset artifacts/datasets/temporal-v1 --output artifacts/models/mission-v2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from fsoc_tracker.ai.learned import (
    LearnedFeatureClassifier,
    LearnedMotionModel,
)
from fsoc_tracker.ai.mission import (
    ExpertPolicy,
    MissionAction,
    ObservationFeatures,
    Situation,
    SituationClassifier,
)
from fsoc_tracker.ai.temporal_dataset import HORIZONS_S


def _features_array_to_observation(feat_vec: np.ndarray) -> ObservationFeatures:
    """Convert a 15-dim feature vector back to ObservationFeatures."""
    return ObservationFeatures(
        timestamp_s=float(feat_vec[0]),
        detected=bool(feat_vec[1]),
        confidence=float(feat_vec[2]),
        residual_px=float(feat_vec[3]),
        uncertainty_x_px=float(feat_vec[4]),
        uncertainty_y_px=float(feat_vec[5]),
        velocity_x_px_s=float(feat_vec[6]),
        velocity_y_px_s=float(feat_vec[7]),
        distance_from_center_px=float(feat_vec[8]),
        time_since_detection_s=float(feat_vec[9]),
        latency_ms=float(feat_vec[10]),
        source_fps=float(feat_vec[11]),
        processing_fps=float(feat_vec[12]),
        candidate_count=int(feat_vec[13]),
        roi_radius_px=float(feat_vec[14]),
    )


def load_temporal_dataset(
    dataset_dir: str,
    split: str = "train",
) -> tuple[list[ObservationFeatures], np.ndarray, list[str], list[str]]:
    """Load temporal dataset and convert to ObservationFeatures + labels.

    Returns:
        (features, motion_targets, situation_labels, policy_labels)
    """
    base = Path(dataset_dir) / split
    feat_arr = np.load(base / "features.npy")
    mask_arr = np.load(base / "mask.npy")
    disp_arr = np.load(base / "future_displacements.npy")

    n_seq, t_max = feat_arr.shape[:2]

    all_features: list[ObservationFeatures] = []
    all_motion_targets: list[np.ndarray] = []
    all_situation_labels: list[str] = []
    all_policy_labels: list[str] = []

    classifier = SituationClassifier()
    expert = ExpertPolicy()

    for i in range(n_seq):
        for j in range(t_max):
            if mask_arr[i, j] < 0.5:
                continue
            feat_vec = feat_arr[i, j]
            obs = _features_array_to_observation(feat_vec)

            horizon_idx = HORIZONS_S.index(0.1) if 0.1 in HORIZONS_S else 2
            motion_target = disp_arr[i, j, horizon_idx]

            sit_label = classifier.classify(obs).value
            policy_decision = expert.decide(obs)
            pol_label = policy_decision.action.value

            all_features.append(obs)
            all_motion_targets.append(motion_target)
            all_situation_labels.append(sit_label)
            all_policy_labels.append(pol_label)

    motion_targets = np.array(all_motion_targets, dtype=np.float64)
    return all_features, motion_targets, all_situation_labels, all_policy_labels


def train_mission_real(
    dataset_dir: str = "artifacts/datasets/temporal-v1",
    output_dir: str = "artifacts/models/mission-v2",
    seed: int = 42,
) -> dict[str, float]:
    """Train all mission models on real observable data.

    Returns metrics dict.
    """
    print(f"[TRAIN] Loading temporal dataset from {dataset_dir}")
    train_feat, train_motion, train_sit, train_pol = load_temporal_dataset(dataset_dir, "train")
    val_feat, val_motion, val_sit, val_pol = load_temporal_dataset(dataset_dir, "validation")
    test_feat, test_motion, test_sit, test_pol = load_temporal_dataset(dataset_dir, "test")

    print(f"[TRAIN] Train: {len(train_feat)}, Val: {len(val_feat)}, Test: {len(test_feat)} samples")

    # 1. Train motion model
    print("[TRAIN] Training motion model...")
    motion = LearnedMotionModel(ridge=1e-3)
    motion_metrics = motion.fit(train_feat, train_motion)
    motion_val = motion.evaluate(val_feat, val_motion)
    motion_test = motion.evaluate(test_feat, test_motion)
    print(f"  Train RMSE: {motion_metrics.rmse_euclidean:.4f} px")
    print(f"  Val RMSE:   {motion_val.rmse_euclidean:.4f} px")
    print(f"  Test RMSE:  {motion_test.rmse_euclidean:.4f} px")

    # 2. Train situation classifier
    print("[TRAIN] Training situation classifier...")
    situation = LearnedFeatureClassifier(
        labels=tuple(item.value for item in Situation),
        ridge=1e-3,
    )
    sit_train_acc = situation.fit(train_feat, train_sit)
    sit_val_acc = situation.evaluate(val_feat, val_sit)
    sit_test_acc = situation.evaluate(test_feat, test_sit)
    print(f"  Train acc: {sit_train_acc:.3f}")
    print(f"  Val acc:   {sit_val_acc:.3f}")
    print(f"  Test acc:  {sit_test_acc:.3f}")

    # 3. Train policy classifier
    print("[TRAIN] Training policy classifier...")
    policy = LearnedFeatureClassifier(
        labels=tuple(item.value for item in MissionAction),
        ridge=1e-3,
    )
    pol_train_acc = policy.fit(train_feat, train_pol)
    pol_val_acc = policy.evaluate(val_feat, val_pol)
    pol_test_acc = policy.evaluate(test_feat, test_pol)
    print(f"  Train acc: {pol_train_acc:.3f}")
    print(f"  Val acc:   {pol_val_acc:.3f}")
    print(f"  Test acc:  {pol_test_acc:.3f}")

    # Save models
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    motion.save(out / "motion-v2.npz")
    situation.save(out / "situation-v2.npz")
    policy.save(out / "policy-v2.npz")

    metadata = {
        "dataset_version": "temporal-observable-v1",
        "dataset_dir": dataset_dir,
        "model_versions": {
            "motion": "MotionNet-linear-v2",
            "situation": "SituationNet-linear-v2",
            "policy": "PolicyNet-linear-v2",
        },
        "train_samples": len(train_feat),
        "val_samples": len(val_feat),
        "test_samples": len(test_feat),
        "seed": seed,
        "motion": {
            "train_rmse_euclidean": motion_metrics.rmse_euclidean,
            "val_rmse_euclidean": motion_val.rmse_euclidean,
            "test_rmse_euclidean": motion_test.rmse_euclidean,
            "train_p95_euclidean": motion_metrics.p95_euclidean,
            "val_p95_euclidean": motion_val.p95_euclidean,
            "test_p95_euclidean": motion_test.p95_euclidean,
        },
        "situation": {
            "train_accuracy": sit_train_acc,
            "val_accuracy": sit_val_acc,
            "test_accuracy": sit_test_acc,
        },
        "policy": {
            "train_accuracy": pol_train_acc,
            "val_accuracy": pol_val_acc,
            "test_accuracy": pol_test_acc,
        },
    }
    (out / "experiment.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    metrics = {
        "motion_train_rmse": motion_metrics.rmse_euclidean,
        "motion_val_rmse": motion_val.rmse_euclidean,
        "motion_test_rmse": motion_test.rmse_euclidean,
        "situation_train_acc": sit_train_acc,
        "situation_val_acc": sit_val_acc,
        "situation_test_acc": sit_test_acc,
        "policy_train_acc": pol_train_acc,
        "policy_val_acc": pol_val_acc,
        "policy_test_acc": pol_test_acc,
    }
    print(f"\n[TRAIN] Saved to {out}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Train mission models on real observable data")
    parser.add_argument("--dataset", default="artifacts/datasets/temporal-v1")
    parser.add_argument("--output", default="artifacts/models/mission-v2")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    metrics = train_mission_real(args.dataset, args.output, args.seed)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
