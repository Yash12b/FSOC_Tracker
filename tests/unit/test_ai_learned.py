from __future__ import annotations

import numpy as np

from fsoc_tracker.ai.learned import (
    LearnedFeatureClassifier,
    LearnedMotionModel,
    policy_labels,
    situation_labels,
)
from fsoc_tracker.ai.mission import ObservationFeatures
from fsoc_tracker.ai.neural import (
    build_temporal_predictor,
    build_visual_heatmap_model,
    torch_backend_available,
)


def features(confidence: float, velocity: float) -> ObservationFeatures:
    return ObservationFeatures(
        timestamp_s=0.0,
        detected=confidence > 0,
        confidence=confidence,
        residual_px=1.0,
        uncertainty_x_px=1.0,
        uncertainty_y_px=1.0,
        velocity_x_px_s=velocity,
        velocity_y_px_s=0.0,
        distance_from_center_px=2.0,
        time_since_detection_s=0.0,
        latency_ms=1.0,
        source_fps=30.0,
        processing_fps=30.0,
        candidate_count=1,
    )


def test_motion_model_trains_predicts_and_roundtrips(tmp_path):
    inputs = [features(0.8, value) for value in (1.0, 2.0, 3.0, 4.0)]
    targets = np.array([[value * 0.1, -0.2] for value in (1.0, 2.0, 3.0, 4.0)])
    model = LearnedMotionModel()
    metrics = model.fit(inputs, targets)
    assert metrics.rmse_euclidean < 0.01
    path = tmp_path / "motion.npz"
    model.save(path)
    restored = LearnedMotionModel.load(path)
    assert restored.predict(features(0.8, 2.0))[0] == model.predict(features(0.8, 2.0))[0]
    assert model.evaluate(inputs, targets).rmse_euclidean < 0.01


def test_feature_classifier_trains_and_roundtrips(tmp_path):
    inputs = [features(0.9, 1.0), features(0.0, 0.0), features(0.2, 1.0)]
    labels = ["normal_tracking", "target_lost", "low_confidence"]
    model = LearnedFeatureClassifier(situation_labels())
    assert model.fit(inputs, labels) > 0.5
    assert model.evaluate(inputs, labels) > 0.5
    path = tmp_path / "situation.npz"
    model.save(path)
    assert LearnedFeatureClassifier.load(path).predict(inputs[0])[0] in situation_labels()


def test_policy_label_space_is_explicit():
    assert "track" in policy_labels()
    assert "safe_stop" in policy_labels()


def test_observable_feature_vector_has_no_ground_truth_fields():
    from fsoc_tracker.ai.learned import observation_vector

    vector = observation_vector(features(0.8, 2.0))
    assert vector.shape == (15,)
    assert not hasattr(features(0.8, 2.0), "ground_truth")


def test_optional_neural_backend_is_explicit_when_unavailable():
    if torch_backend_available():
        visual = build_visual_heatmap_model()
        temporal = build_temporal_predictor()
        assert visual is not None
        assert temporal is not None
    else:
        import pytest

        with pytest.raises(RuntimeError, match="PyTorch is required"):
            build_visual_heatmap_model()
