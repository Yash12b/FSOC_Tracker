"""Small supervised ML models for the mission brain.

These models use NumPy only so offline inference does not require a training
framework. They are deliberately simple, inspectable baselines: linear
regression for motion and regularized multinomial linear classification for
situation/policy decisions.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from fsoc_tracker.ai.mission import (
    MissionAction,
    ObservationFeatures,
    Situation,
)


def observation_vector(features: ObservationFeatures) -> np.ndarray:
    """Convert observable runtime state to a stable numeric feature vector."""
    return np.array(
        [
            1.0,
            float(features.detected),
            features.confidence,
            features.residual_px,
            features.uncertainty_x_px,
            features.uncertainty_y_px,
            features.velocity_x_px_s,
            features.velocity_y_px_s,
            features.distance_from_center_px,
            features.time_since_detection_s,
            features.latency_ms,
            features.source_fps,
            features.processing_fps,
            float(features.candidate_count),
            features.roi_radius_px,
        ],
        dtype=np.float64,
    )


@dataclass
class MotionModelMetrics:
    rmse_x: float
    rmse_y: float
    rmse_euclidean: float
    p95_euclidean: float


class LearnedMotionModel:
    """Regularized linear future-displacement predictor."""

    version = "MotionNet-linear-v1"

    def __init__(self, ridge: float = 1e-3) -> None:
        if ridge < 0:
            raise ValueError("ridge must be non-negative")
        self.ridge = ridge
        self._weights: np.ndarray | None = None
        self._residual_std = np.ones(2, dtype=np.float64)

    @property
    def trained(self) -> bool:
        return self._weights is not None

    def fit(
        self,
        features: Sequence[ObservationFeatures],
        future_displacements: np.ndarray,
    ) -> MotionModelMetrics:
        x = np.stack([observation_vector(item) for item in features])
        y = np.asarray(future_displacements, dtype=np.float64)
        if y.ndim != 2 or y.shape != (len(features), 2):
            raise ValueError("future_displacements must have shape (N, 2)")
        reg = self.ridge * np.eye(x.shape[1], dtype=np.float64)
        reg[0, 0] = 0.0
        self._weights = np.linalg.solve(x.T @ x + reg, x.T @ y)
        residuals = y - x @ self._weights
        self._residual_std = np.maximum(np.std(residuals, axis=0), 1e-6)
        errors = np.linalg.norm(residuals, axis=1)
        return MotionModelMetrics(
            rmse_x=float(np.sqrt(np.mean(residuals[:, 0] ** 2))),
            rmse_y=float(np.sqrt(np.mean(residuals[:, 1] ** 2))),
            rmse_euclidean=float(np.sqrt(np.mean(errors ** 2))),
            p95_euclidean=float(np.percentile(errors, 95)),
        )

    def predict(self, features: ObservationFeatures) -> tuple[float, float, float, float]:
        if self._weights is None:
            raise RuntimeError("motion model is not trained")
        displacement = observation_vector(features) @ self._weights
        return (
            float(displacement[0]),
            float(displacement[1]),
            float(self._residual_std[0]),
            float(self._residual_std[1]),
        )

    def evaluate(
        self,
        features: Sequence[ObservationFeatures],
        future_displacements: np.ndarray,
    ) -> MotionModelMetrics:
        """Measure generalization without changing the fitted model."""
        if not self.trained:
            raise RuntimeError("motion model is not trained")
        y = np.asarray(future_displacements, dtype=np.float64)
        if y.shape != (len(features), 2):
            raise ValueError("future_displacements must have shape (N, 2)")
        predictions = np.asarray(
            [self.predict(item)[:2] for item in features], dtype=np.float64
        )
        residuals = y - predictions
        errors = np.linalg.norm(residuals, axis=1)
        return MotionModelMetrics(
            rmse_x=float(np.sqrt(np.mean(residuals[:, 0] ** 2))),
            rmse_y=float(np.sqrt(np.mean(residuals[:, 1] ** 2))),
            rmse_euclidean=float(np.sqrt(np.mean(errors**2))),
            p95_euclidean=float(np.percentile(errors, 95)),
        )

    def save(self, path: str | Path) -> None:
        if self._weights is None:
            raise RuntimeError("cannot save an untrained motion model")
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            output,
            weights=self._weights,
            residual_std=self._residual_std,
            metadata=json.dumps({"version": self.version, "ridge": self.ridge}),
        )

    @classmethod
    def load(cls, path: str | Path) -> LearnedMotionModel:
        data = np.load(path)
        metadata = json.loads(str(data["metadata"]))
        model = cls(float(metadata["ridge"]))
        model._weights = np.asarray(data["weights"], dtype=np.float64)
        model._residual_std = np.asarray(data["residual_std"], dtype=np.float64)
        return model


class LearnedFeatureClassifier:
    """Regularized multiclass linear classifier with softmax confidence."""

    def __init__(self, labels: Sequence[str], ridge: float = 1e-3) -> None:
        if not labels:
            raise ValueError("at least one label is required")
        self.labels = tuple(labels)
        self.ridge = ridge
        self._weights: np.ndarray | None = None

    @property
    def trained(self) -> bool:
        return self._weights is not None

    def fit(self, features: Sequence[ObservationFeatures], labels: Sequence[str]) -> float:
        if len(features) != len(labels):
            raise ValueError("features and labels must have equal length")
        unknown = set(labels) - set(self.labels)
        if unknown:
            raise ValueError(f"unknown labels: {sorted(unknown)}")
        x = np.stack([observation_vector(item) for item in features])
        y = np.zeros((len(labels), len(self.labels)), dtype=np.float64)
        for row, label in enumerate(labels):
            y[row, self.labels.index(label)] = 1.0
        reg = self.ridge * np.eye(x.shape[1], dtype=np.float64)
        reg[0, 0] = 0.0
        self._weights = np.linalg.solve(x.T @ x + reg, x.T @ y)
        return self.accuracy(features, labels)

    def predict(self, features: ObservationFeatures) -> tuple[str, float]:
        if self._weights is None:
            raise RuntimeError("classifier is not trained")
        scores = observation_vector(features) @ self._weights
        scores -= np.max(scores)
        probabilities = np.exp(scores)
        probabilities /= np.sum(probabilities)
        index = int(np.argmax(probabilities))
        return self.labels[index], float(probabilities[index])

    def accuracy(self, features: Sequence[ObservationFeatures], labels: Sequence[str]) -> float:
        if not labels:
            return 0.0
        return sum(
            self.predict(item)[0] == label
            for item, label in zip(features, labels, strict=True)
        ) / len(labels)

    def evaluate(
        self, features: Sequence[ObservationFeatures], labels: Sequence[str]
    ) -> float:
        """Measure accuracy on a held-out set without refitting."""
        if not self.trained:
            raise RuntimeError("classifier is not trained")
        return self.accuracy(features, labels)

    def save(self, path: str | Path) -> None:
        if self._weights is None:
            raise RuntimeError("cannot save an untrained classifier")
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            output,
            weights=self._weights,
            metadata=json.dumps({"labels": self.labels, "ridge": self.ridge}),
        )

    @classmethod
    def load(cls, path: str | Path) -> LearnedFeatureClassifier:
        data = np.load(path)
        metadata = json.loads(str(data["metadata"]))
        model = cls(metadata["labels"], float(metadata["ridge"]))
        model._weights = np.asarray(data["weights"], dtype=np.float64)
        return model


def situation_labels() -> tuple[str, ...]:
    return tuple(item.value for item in Situation)


def policy_labels() -> tuple[str, ...]:
    return tuple(item.value for item in MissionAction)
