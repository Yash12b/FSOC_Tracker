"""AI vs Classical benchmark framework.

Compares perception backends on the same test dataset.
Reports precision, recall, F1, centroid error, latency, etc.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from fsoc_tracker.ai.dataset import DatasetSplit
from fsoc_tracker.perception.base import PerceptionEngine


@dataclass
class CentroidMetrics:
    """Centroid localization metrics."""

    mean_error_px: float = 0.0
    rmse_px: float = 0.0
    p50_px: float = 0.0
    p90_px: float = 0.0
    p95_px: float = 0.0
    p99_px: float = 0.0
    max_error_px: float = 0.0
    mae_x: float = 0.0
    mae_y: float = 0.0


@dataclass
class BenchmarkResult:
    """Results from benchmarking one detector on one dataset."""

    detector_name: str = ""
    num_samples: int = 0
    num_with_target: int = 0
    num_without_target: int = 0

    # Detection metrics
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0

    # Centroid metrics (for true positives only)
    centroid: CentroidMetrics = field(default_factory=CentroidMetrics)

    # Latency
    mean_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    throughput_fps: float = 0.0

    # Per-size breakdown
    by_size: dict[str, dict[str, float]] = field(default_factory=dict)

    # Per-disturbance breakdown
    by_disturbance: dict[str, dict[str, float]] = field(default_factory=dict)

    # Per-sample details
    details: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> str:
        """Return a formatted summary string."""
        lines = [
            f"Benchmark: {self.detector_name}",
            f"  Samples: {self.num_samples} ({self.num_with_target} with target, {self.num_without_target} negative)",
            f"  TP={self.true_positives} FP={self.false_positives} TN={self.true_negatives} FN={self.false_negatives}",
            f"  Precision={self.precision:.3f}  Recall={self.recall:.3f}  F1={self.f1:.3f}",
            f"  Centroid RMSE={self.centroid.rmse_px:.2f}px  P95={self.centroid.p95_px:.2f}px  Max={self.centroid.max_error_px:.2f}px",
            f"  Latency: mean={self.mean_latency_ms:.2f}ms  P95={self.p95_latency_ms:.2f}ms  FPS={self.throughput_fps:.1f}",
        ]

        if self.by_size:
            lines.append("  By target size:")
            for size_key, metrics in sorted(self.by_size.items()):
                lines.append(
                    f"    {size_key}: P={metrics['precision']:.3f} R={metrics['recall']:.3f} "
                    f"RMSE={metrics['rmse']:.2f}px"
                )

        if self.by_disturbance:
            lines.append("  By disturbance:")
            for dist_key, metrics in sorted(self.by_disturbance.items()):
                lines.append(
                    f"    {dist_key}: P={metrics['precision']:.3f} R={metrics['recall']:.3f}"
                )

        return "\n".join(lines)


def _centroid_error(
    pred_x: float, pred_y: float,
    true_x: float, true_y: float,
) -> float:
    """Euclidean centroid error in pixels."""
    return math.sqrt((pred_x - true_x) ** 2 + (pred_y - true_y) ** 2)


def benchmark_detector(
    detector: PerceptionEngine,
    dataset: DatasetSplit,
    detection_threshold: float = 0.3,
    center_tolerance_px: float = 5.0,
) -> BenchmarkResult:
    """Benchmark a perception engine on a dataset split.

    Args:
        detector: PerceptionEngine to benchmark
        dataset: test dataset split
        detection_threshold: minimum confidence for positive detection
        center_tolerance_px: max centroid error to count as true positive

    Returns:
        BenchmarkResult with all metrics.
    """
    tp = 0
    fp = 0
    tn = 0
    fn = 0
    centroid_errors = []
    latencies = []
    details = []

    for sample in dataset.samples:
        result = detector.detect(sample.image, timestamp_s=0.0, frame_index=sample.sample_id)

        has_target = sample.label.visible
        detected = result.detected and result.primary_detection is not None
        confidence = result.primary_detection.confidence if detected else 0.0

        # Determine TP/FP/TN/FN
        if has_target and detected:
            # Check centroid accuracy
            pred_x = result.primary_detection.center_x
            pred_y = result.primary_detection.center_y
            error = _centroid_error(pred_x, pred_y, sample.label.center_x, sample.label.center_y)

            if error <= center_tolerance_px and confidence >= detection_threshold:
                tp += 1
                centroid_errors.append(error)
            else:
                fn += 1
                centroid_errors.append(error if error else float("inf"))
        elif has_target and not detected:
            fn += 1
            centroid_errors.append(float("inf"))
        elif not has_target and detected:
            fp += 1
        else:
            tn += 1

        latencies.append(result.processing_time_ms)

        details.append({
            "sample_id": sample.sample_id,
            "has_target": has_target,
            "detected": detected,
            "confidence": confidence,
            "centroid_error": centroid_errors[-1] if centroid_errors else 0.0,
            "latency_ms": result.processing_time_ms,
            "target_size": sample.label.target_size_px,
            "disturbances": sample.label.disturbance_types,
        })

    # Compute metrics
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-6)

    # Centroid metrics
    valid_errors = [e for e in centroid_errors if e < float("inf")]
    centroid = CentroidMetrics()
    if valid_errors:
        errors_arr = np.array(valid_errors)
        centroid.mean_error_px = float(np.mean(errors_arr))
        centroid.rmse_px = float(np.sqrt(np.mean(errors_arr ** 2)))
        centroid.p50_px = float(np.percentile(errors_arr, 50))
        centroid.p90_px = float(np.percentile(errors_arr, 90))
        centroid.p95_px = float(np.percentile(errors_arr, 95))
        centroid.p99_px = float(np.percentile(errors_arr, 99))
        centroid.max_error_px = float(np.max(errors_arr))

    # Latency
    lat_arr = np.array(latencies) if latencies else np.array([0.0])
    mean_lat = float(np.mean(lat_arr))
    p95_lat = float(np.percentile(lat_arr, 95))

    # Per-size breakdown
    by_size = {}
    size_groups = {"small_5px": [], "medium_10px": [], "large_20px": []}
    for d in details:
        sz = d["target_size"]
        if sz <= 7:
            size_groups["small_5px"].append(d)
        elif sz <= 14:
            size_groups["medium_10px"].append(d)
        else:
            size_groups["large_20px"].append(d)

    for size_key, group in size_groups.items():
        if not group:
            continue
        g_tp = sum(1 for d in group if d["has_target"] and d["detected"] and d["centroid_error"] <= center_tolerance_px)
        g_fn = sum(1 for d in group if d["has_target"] and (not d["detected"] or d["centroid_error"] > center_tolerance_px))
        g_fp = sum(1 for d in group if not d["has_target"] and d["detected"])
        g_p = g_tp / max(g_tp + g_fp, 1)
        g_r = g_tp / max(g_tp + g_fn, 1)
        g_errors = [d["centroid_error"] for d in group if d["has_target"] and d["centroid_error"] < float("inf")]
        g_rmse = float(np.sqrt(np.mean(np.array(g_errors) ** 2))) if g_errors else 0.0
        by_size[size_key] = {"precision": g_p, "recall": g_r, "rmse": g_rmse, "count": len(group)}

    # Per-disturbance breakdown
    by_disturbance = {}
    for d in details:
        for dist_type in d["disturbances"] or ["clean"]:
            if dist_type not in by_disturbance:
                by_disturbance[dist_type] = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
            if d["has_target"] and d["detected"] and d["centroid_error"] <= center_tolerance_px:
                by_disturbance[dist_type]["tp"] += 1
            elif d["has_target"]:
                by_disturbance[dist_type]["fn"] += 1
            elif d["detected"]:
                by_disturbance[dist_type]["fp"] += 1
            else:
                by_disturbance[dist_type]["tn"] += 1

    for dist_type, counts in by_disturbance.items():
        p = counts["tp"] / max(counts["tp"] + counts["fp"], 1)
        r = counts["tp"] / max(counts["tp"] + counts["fn"], 1)
        by_disturbance[dist_type] = {"precision": p, "recall": r, **counts}

    return BenchmarkResult(
        detector_name=detector.name,
        num_samples=len(dataset.samples),
        num_with_target=sum(1 for s in dataset.samples if s.label.visible),
        num_without_target=sum(1 for s in dataset.samples if not s.label.visible),
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        centroid=centroid,
        mean_latency_ms=mean_lat,
        p95_latency_ms=p95_lat,
        throughput_fps=1000.0 / max(mean_lat, 0.001),
        by_size=by_size,
        by_disturbance=by_disturbance,
        details=details,
    )


def compare_detectors(
    detectors: list[PerceptionEngine],
    dataset: DatasetSplit,
    detection_threshold: float = 0.3,
) -> list[BenchmarkResult]:
    """Compare multiple detectors on the same dataset.

    Args:
        detectors: list of PerceptionEngine to compare
        dataset: test dataset
        detection_threshold: confidence threshold

    Returns:
        List of BenchmarkResult, one per detector.
    """
    results = []
    for detector in detectors:
        result = benchmark_detector(detector, dataset, detection_threshold)
        results.append(result)
    return results
