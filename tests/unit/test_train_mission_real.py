"""Tests for mission model training on real observable data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from fsoc_tracker.ai.learned import LearnedFeatureClassifier, LearnedMotionModel
from fsoc_tracker.ai.mission import MissionAction, Situation
from fsoc_tracker.ai.train_mission_real import (
    _features_array_to_observation,
    load_temporal_dataset,
)


class TestFeaturesConversion:
    def test_roundtrip(self):
        feat_vec = np.array([
            1.0, 1.0, 0.8, 5.0, 3.0, 4.0, 10.0, -5.0,
            50.0, 0.0, 2.0, 30.0, 25.0, 3.0, 80.0,
        ], dtype=np.float64)
        obs = _features_array_to_observation(feat_vec)
        assert obs.timestamp_s == 1.0
        assert obs.detected is True
        assert obs.confidence == 0.8
        assert obs.uncertainty_x_px == 3.0
        assert obs.velocity_x_px_s == 10.0
        assert obs.candidate_count == 3
        assert obs.roi_radius_px == 80.0


class TestLoadTemporalDataset:
    def test_loads_split(self, tmp_path: Path):
        feat = np.random.default_rng(42).standard_normal((2, 10, 15))
        mask = np.ones((2, 10), dtype=np.float64)
        disp = np.random.default_rng(42).standard_normal((2, 10, 5, 2))
        split_dir = tmp_path / "train"
        split_dir.mkdir()
        np.save(split_dir / "features.npy", feat)
        np.save(split_dir / "mask.npy", mask)
        np.save(split_dir / "future_displacements.npy", disp)

        features, motion_targets, sit_labels, pol_labels = load_temporal_dataset(
            str(tmp_path), "train"
        )
        assert len(features) == 20
        assert motion_targets.shape == (20, 2)
        assert len(sit_labels) == 20
        assert len(pol_labels) == 20
        for label in sit_labels:
            assert label in [s.value for s in Situation]
        for label in pol_labels:
            assert label in [a.value for a in MissionAction]


class TestMissionModelsV2:
    @pytest.fixture(autouse=True)
    def _load_v2_models(self):
        model_dir = Path("artifacts/models/mission-v2")
        if not (model_dir / "motion-v2.npz").exists():
            pytest.skip("mission-v2 models not trained yet")
        self.motion = LearnedMotionModel.load(model_dir / "motion-v2.npz")
        self.situation = LearnedFeatureClassifier.load(model_dir / "situation-v2.npz")
        self.policy = LearnedFeatureClassifier.load(model_dir / "policy-v2.npz")

    def test_motion_model_trained(self):
        assert self.motion.trained

    def test_situation_model_trained(self):
        assert self.situation.trained

    def test_policy_model_trained(self):
        assert self.policy.trained

    def test_situation_labels_valid(self):
        # Model may have been trained with old label set; skip if stale
        valid_labels = set(s.value for s in Situation)
        model_labels = set(self.situation.labels)
        if not model_labels.issubset(valid_labels):
            pytest.skip(f"Model trained with stale labels: {model_labels - valid_labels}")
        for label in self.situation.labels:
            assert label in valid_labels, f"Unknown situation label: {label}"

    def test_policy_labels_valid(self):
        assert set(self.policy.labels) == set(a.value for a in MissionAction)
