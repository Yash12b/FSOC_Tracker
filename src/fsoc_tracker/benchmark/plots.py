"""Post-run plot visualizations.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from fsoc_tracker.benchmark.collector import FrameMetrics
from fsoc_tracker.benchmark.models import BenchmarkResult


def generate_plots(
    result: BenchmarkResult,
    frames: list[FrameMetrics],
    output_dir: str,
) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[str] = []

    errors = [f.error_px for f in frames if f.error_px is not None]
    errors_idx = [f.timestamp_s for f in frames if f.error_px is not None]

    if errors:
        fig, ax = plt.subplots(figsize=(12, 4))
        ax.plot(errors_idx[:len(errors)], errors, color="#00d4ff", linewidth=0.8)
        ax.axhline(y=10, color="#e74c3c", linestyle="--", alpha=0.7, label="10px threshold")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Centroid Error (px)")
        ax.set_title("Tracking Error vs Time")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = str(out / "error_vs_time.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated.append(path)

    if errors:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(errors, bins=50, color="#00d4ff", alpha=0.7, edgecolor="#16213e")
        ax.axvline(x=10, color="#e74c3c", linestyle="--", alpha=0.7, label="10px threshold")
        ax.set_xlabel("Centroid Error (px)")
        ax.set_ylabel("Count")
        ax.set_title("Error Distribution")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = str(out / "error_histogram.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated.append(path)

    if errors:
        ex = [f.error_x for f in frames if f.error_x is not None]
        ey = [f.error_y for f in frames if f.error_y is not None]
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6))
        ax1.plot(errors_idx[:len(ex)], ex, color="#00d4ff", linewidth=0.8)
        ax1.axhline(y=0, color="#666", linestyle="-", alpha=0.5)
        ax1.set_ylabel("X Error (px)")
        ax1.set_title("X Error vs Time")
        ax1.grid(True, alpha=0.3)
        ax2.plot(errors_idx[:len(ey)], ey, color="#ff6b6b", linewidth=0.8)
        ax2.axhline(y=0, color="#666", linestyle="-", alpha=0.5)
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Y Error (px)")
        ax2.set_title("Y Error vs Time")
        ax2.grid(True, alpha=0.3)
        fig.tight_layout()
        path = str(out / "xy_error_vs_time.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated.append(path)

    if frames:
        track_x = [f.track_x for f in frames]
        track_y = [f.track_y for f in frames]
        true_x = [f.true_x for f in frames if f.true_x is not None]
        true_y = [f.true_y for f in frames if f.true_y is not None]
        fig, ax = plt.subplots(figsize=(8, 8))
        ax.plot(track_x, track_y, color="#00d4ff", linewidth=0.8, label="Estimated")
        if true_x and true_y:
            ax.plot(true_x, true_y, color="#2ecc71", linewidth=0.8, label="Ground Truth")
        ax.set_xlabel("X (px)")
        ax.set_ylabel("Y (px)")
        ax.set_title("Target vs Estimated Centroid")
        ax.legend()
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = str(out / "centroid_path.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated.append(path)

    if frames:
        proc_ms = [f.processing_time_ms for f in frames if f.processing_time_ms > 0]
        if proc_ms:
            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(proc_ms, color="#ff6b6b", linewidth=0.8)
            ax.axhline(y=np.mean(proc_ms), color="#2ecc71", linestyle="--", alpha=0.7, label=f"Mean: {np.mean(proc_ms):.1f}ms")
            ax.set_xlabel("Frame")
            ax.set_ylabel("Processing Time (ms)")
            ax.set_title("Processing Latency vs Frame")
            ax.legend()
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            path = str(out / "latency_vs_frame.png")
            fig.savefig(path, dpi=150)
            plt.close(fig)
            generated.append(path)

    if frames:
        lock = [1 if f.lock_status else 0 for f in frames]
        fig, ax = plt.subplots(figsize=(12, 2))
        ax.fill_between(range(len(lock)), lock, color="#2ecc71", alpha=0.5)
        ax.set_xlabel("Frame")
        ax.set_ylabel("Lock")
        ax.set_title("Lock State vs Time")
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Unlocked", "Locked"])
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = str(out / "lock_state.png")
        fig.savefig(path, dpi=150)
        plt.close(fig)
        generated.append(path)

    return generated
