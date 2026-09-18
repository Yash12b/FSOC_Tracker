"""Temporal GRU predictor training.

Trains the GRU-based multi-horizon displacement predictor from neural.py
on temporal observable sequences.

Usage:
    python -m fsoc_tracker.ai.temporal_training --dataset artifacts/datasets/temporal-v1 --output artifacts/models/temporal-v1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from fsoc_tracker.ai.neural import build_temporal_predictor, torch_backend_available
from fsoc_tracker.ai.temporal_dataset import FEATURE_DIM, HORIZONS_S


def _load_split(dataset_dir: str, split: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Load features, displacements, mask from a temporal dataset split."""
    base = Path(dataset_dir) / split
    features = np.load(base / "features.npy").astype(np.float32)
    displacements = np.load(base / "future_displacements.npy").astype(np.float32)
    mask = np.load(base / "mask.npy").astype(np.float32)
    situation = np.load(base / "situation_labels.npy").astype(np.float32)
    return features, displacements, mask, situation


def train_temporal_predictor(
    dataset_dir: str = "artifacts/datasets/temporal-v1",
    output_dir: str = "artifacts/models/temporal-v1",
    epochs: int = 30,
    batch_size: int = 8,
    learning_rate: float = 1e-3,
    hidden_dim: int = 32,
    sequence_length: int = 20,
    seed: int = 42,
) -> dict[str, Any]:
    """Train temporal GRU predictor and save checkpoint."""
    if not torch_backend_available():
        raise RuntimeError("PyTorch is required for temporal predictor training")

    import torch
    from torch import nn

    torch.manual_seed(seed)
    np.random.seed(seed)

    print(f"[TEMPORAL] Loading dataset from {dataset_dir}")
    train_feat, train_disp, train_mask, _ = _load_split(dataset_dir, "train")
    val_feat, val_disp, val_mask, _ = _load_split(dataset_dir, "validation")

    n_train, t_max, _ = train_feat.shape
    n_val = val_feat.shape[0]
    len(HORIZONS_S)
    T = t_max

    print(f"[TEMPORAL] Train: {n_train} seqs, Val: {n_val} seqs, T={t_max}")

    model = build_temporal_predictor(
        feature_dim=FEATURE_DIM,
        hidden_dim=hidden_dim,
        horizons_s=tuple(HORIZONS_S),
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    loss_fn = nn.MSELoss(reduction="none")

    best_val_loss = float("inf")
    best_state: dict[str, Any] | None = None
    patience = 10
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        indices = np.random.default_rng(seed + epoch).permutation(n_train)
        epoch_losses = []

        for start in range(0, n_train, batch_size):
            batch_idx = indices[start:start + batch_size]
            x = torch.from_numpy(train_feat[batch_idx])

            y_all = torch.from_numpy(train_disp[batch_idx])  # (B, T, H, 2)
            m_all = torch.from_numpy(train_mask[batch_idx])  # (B, T)

            # Sample a random valid timestep per sequence (NOT the last frame).
            # The last frame has zero displacement because there is no future.
            # We need at least 16 frames after the current frame for the
            # longest horizon (500ms at 30 FPS = ~15 frames).
            batch_size_actual = x.shape[0]
            max_valid_t = T - 16  # ensure future frames exist for all horizons
            rng = np.random.default_rng(seed + epoch + start)
            sampled_t = rng.integers(0, max(1, max_valid_t), size=batch_size_actual)
            # Verify each sampled timestep has a valid mask
            for bi in range(batch_size_actual):
                if m_all[bi, sampled_t[bi]] < 0.5:
                    # Find any valid timestep before max_valid_t
                    valid_ts = np.where(m_all[bi, :max_valid_t] > 0.5)[0]
                    if len(valid_ts) > 0:
                        sampled_t[bi] = valid_ts[-1]  # use latest valid before cutoff
                    else:
                        sampled_t[bi] = 0

            y_target = y_all[torch.arange(batch_size_actual), sampled_t]  # (B, H, 2)

            output = model(x)
            pred = output["displacement"]  # (B, H, 2)

            loss = loss_fn(pred, y_target).mean()

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            epoch_losses.append(float(loss.detach()))

        model.eval()
        with torch.no_grad():
            x_val = torch.from_numpy(val_feat)
            y_val_all = torch.from_numpy(val_disp)  # (N_val, T, H, 2)
            torch.from_numpy(val_mask)  # (N_val, T)

            # Use a fixed mid-sequence timestep for validation (frame 150 of 300)
            val_t = min(150, T - 16)
            n_val = x_val.shape[0]
            y_val_target = y_val_all[torch.arange(n_val), val_t]  # (N_val, H, 2)

            val_output = model(x_val)
            val_pred = val_output["displacement"]  # (N_val, H, 2)
            val_loss = loss_fn(val_pred, y_val_target).mean()

        train_loss = float(np.mean(epoch_losses))

        if val_loss < best_val_loss:
            best_val_loss = float(val_loss)
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}: train_loss={train_loss:.6f} val_loss={float(val_loss):.6f}")

        if patience_counter >= patience:
            print(f"  Early stopping at epoch {epoch+1}")
            break

    if best_state is None:
        raise RuntimeError("No checkpoint saved")

    model.load_state_dict(best_state)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, out / "temporal_gru.pt")
    metadata = {
        "model": "TemporalBeaconPredictor",
        "feature_dim": FEATURE_DIM,
        "hidden_dim": hidden_dim,
        "horizons_s": HORIZONS_S,
        "sequence_length": sequence_length,
        "epochs": epoch + 1,
        "best_val_loss": best_val_loss,
        "train_samples": n_train,
        "val_samples": n_val,
        "seed": seed,
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"[TEMPORAL] Saved to {out}, best_val_loss={best_val_loss:.6f}")
    return {"best_val_loss": best_val_loss, "epochs": epoch + 1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train temporal GRU predictor")
    parser.add_argument("--dataset", default="artifacts/datasets/temporal-v1")
    parser.add_argument("--output", default="artifacts/models/temporal-v1")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = train_temporal_predictor(
        args.dataset, args.output, args.epochs, args.batch_size,
        args.lr, args.hidden_dim, seed=args.seed,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
