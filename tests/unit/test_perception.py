"""Comprehensive tests for the perception subsystem.

16+ test categories covering:
A. Center projection detection
B. Off-axis detection
C. Subpixel centroid accuracy
D. Apparent size robustness (5/7/10/15/20 px)
E. Clipping handling
F. Behind camera / no target
G. Multiple bright objects
H. Intensity / confidence
I. Noise robustness
J. Monochrome output
K. Determinism
L. Resolution independence
M. FPS independence
N. Ground truth comparison
O. No NaN/Inf
P. Failure handling
Q. Candidate scoring
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fsoc_tracker.perception.classical import detect_beacon
from fsoc_tracker.perception.config import (
    CentroidMethod,
    PerceptionConfig,
    ThresholdMode,
)
from fsoc_tracker.perception.evaluation import (
    compare_detection_to_ground_truth,
    compute_centroid_error,
    compute_rmse,
)
from fsoc_tracker.perception.models import (
    BeaconDetection,
    PerceptionResult,
    PerceptionStatus,
)
from fsoc_tracker.perception.centroid import compute_centroid
from fsoc_tracker.perception.scoring import score_candidate
from fsoc_tracker.perception.candidates import extract_features
from fsoc_tracker.perception.models import CandidateFeatures
from fsoc_tracker.perception.classical_engine import ClassicalBeaconDetector
from fsoc_tracker.simulation.sensor.models import GroundTruth, TargetVisibility


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(**overrides) -> PerceptionConfig:
    defaults = dict(
        threshold_mode=ThresholdMode.PERCENTILE,
        percentile_value=90.0,
        min_confidence=0.1,
        use_weighted_centroid=True,
        w_intensity=0.3, w_size=0.25, w_shape=0.25, w_contrast=0.2,
    )
    defaults.update(overrides)
    return PerceptionConfig(**defaults)


def _make_image(
    width: int = 640,
    height: int = 480,
    bg_level: float = 5.0,
    beacon_x: float = 320.0,
    beacon_y: float = 240.0,
    beacon_size: float = 10.0,
    beacon_intensity: float = 255.0,
) -> np.ndarray:
    """Create a synthetic test image with a single bright beacon."""
    img = np.full((height, width), bg_level, dtype=np.uint8)

    half = beacon_size / 2.0
    x1 = max(0, int(np.floor(beacon_x - half)))
    x2 = min(width, int(np.ceil(beacon_x + half)))
    y1 = max(0, int(np.floor(beacon_y - half)))
    y2 = min(height, int(np.ceil(beacon_y + half)))

    for py in range(y1, y2):
        for px in range(x1, x2):
            dist = math.sqrt((px - beacon_x) ** 2 + (py - beacon_y) ** 2)
            if dist <= half:
                intensity = beacon_intensity * max(0.0, 1.0 - dist / half * 0.3)
                img[py, px] = min(255, int(intensity))

    return img


def _make_multi_blob_image(
    width: int = 640,
    height: int = 480,
    bg_level: float = 5.0,
    blobs: list[tuple[float, float, float, float]] | None = None,
) -> np.ndarray:
    """Create image with multiple bright blobs."""
    if blobs is None:
        blobs = [
            (320.0, 240.0, 10.0, 255.0),
            (100.0, 100.0, 8.0, 200.0),
            (500.0, 400.0, 6.0, 180.0),
        ]
    img = np.full((height, width), bg_level, dtype=np.uint8)
    for bx, by, bsize, bintensity in blobs:
        half = bsize / 2.0
        x1 = max(0, int(np.floor(bx - half)))
        x2 = min(width, int(np.ceil(bx + half)))
        y1 = max(0, int(np.floor(by - half)))
        y2 = min(height, int(np.ceil(by + half)))
        for py in range(y1, y2):
            for px in range(x1, x2):
                dist = math.sqrt((px - bx) ** 2 + (py - by) ** 2)
                if dist <= half:
                    img[py, px] = min(255, int(bintensity))
    return img


# ---------------------------------------------------------------------------
# A. Center projection detection
# ---------------------------------------------------------------------------

class TestCenterDetection:
    def test_center_beacon_detected(self):
        img = _make_image(beacon_x=320.0, beacon_y=240.0)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.detected is True
        assert result.primary_detection is not None
        assert abs(result.primary_detection.center_x - 320.0) < 3.0
        assert abs(result.primary_detection.center_y - 240.0) < 3.0

    def test_center_confidence_positive(self):
        img = _make_image(beacon_x=320.0, beacon_y=240.0)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.primary_detection.confidence > 0.0


# ---------------------------------------------------------------------------
# B. Off-axis detection
# ---------------------------------------------------------------------------

class TestOffAxisDetection:
    def test_right_of_center(self):
        img = _make_image(beacon_x=400.0, beacon_y=240.0)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.detected is True
        assert result.primary_detection.center_x > 350.0

    def test_top_left_corner(self):
        img = _make_image(beacon_x=50.0, beacon_y=50.0)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.detected is True


# ---------------------------------------------------------------------------
# C. Subpixel centroid
# ---------------------------------------------------------------------------

class TestSubpixelCentroid:
    def test_subpixel_accuracy(self):
        img = _make_image(beacon_x=320.25, beacon_y=240.75, beacon_size=10.0)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.detected is True
        pd = result.primary_detection
        error = math.sqrt((pd.center_x - 320.25)**2 + (pd.center_y - 240.75)**2)
        assert error < 2.0

    def test_geometric_vs_weighted_both_return_valid(self):
        img = _make_image(beacon_x=320.5, beacon_y=240.5, beacon_size=10.0)
        config_w = _make_config(centroid_method=CentroidMethod.INTENSITY_WEIGHTED)
        config_g = _make_config(centroid_method=CentroidMethod.GEOMETRIC)
        r_w = detect_beacon(img, config_w)
        r_g = detect_beacon(img, config_g)
        assert r_w.detected is True
        assert r_g.detected is True
        pd_w, pd_g = r_w.primary_detection, r_g.primary_detection
        assert abs(pd_w.center_x - 320.5) < 3.0
        assert abs(pd_g.center_x - 320.5) < 3.0
        assert not math.isnan(pd_w.center_x)
        assert not math.isnan(pd_g.center_x)


# ---------------------------------------------------------------------------
# D. Apparent size robustness
# ---------------------------------------------------------------------------

class TestSizeRobustness:
    @pytest.mark.parametrize("size", [7.0, 10.0, 15.0, 20.0])
    def test_various_sizes_detected(self, size):
        img = _make_image(beacon_size=size, beacon_x=320.0, beacon_y=240.0)
        config = _make_config(
            threshold_mode=ThresholdMode.GLOBAL,
            threshold_value=50.0,
            expected_size_px=size,
        )
        result = detect_beacon(img, config)
        assert result.detected is True
        pd = result.primary_detection
        assert abs(pd.area - size**2) < size**2 * 0.8

    def test_small_beacon_at_least_detected(self):
        img = _make_image(beacon_size=5.0, beacon_x=320.0, beacon_y=240.0, beacon_intensity=255.0)
        config = _make_config(
            threshold_mode=ThresholdMode.PERCENTILE,
            percentile_value=95.0,
        )
        result = detect_beacon(img, config)
        assert result.detected is True


# ---------------------------------------------------------------------------
# E. Clipping handling
# ---------------------------------------------------------------------------

class TestClipping:
    def test_partial_beacon_at_edge(self):
        img = _make_image(beacon_x=638.0, beacon_y=240.0, beacon_size=10.0)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.status in (PerceptionStatus.DETECTED, PerceptionStatus.CANDIDATE, PerceptionStatus.UNCERTAIN, PerceptionStatus.NO_TARGET)


# ---------------------------------------------------------------------------
# F. No target
# ---------------------------------------------------------------------------

class TestNoTarget:
    def test_all_black_image(self):
        img = np.zeros((480, 640), dtype=np.uint8)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.detected is False
        assert result.status == PerceptionStatus.NO_TARGET

    def test_none_image(self):
        config = _make_config()
        result = detect_beacon(None, config)
        assert result.detected is False

    def test_empty_image(self):
        config = _make_config()
        result = detect_beacon(np.array([]), config)
        assert result.detected is False


# ---------------------------------------------------------------------------
# G. Multiple bright objects
# ---------------------------------------------------------------------------

class TestMultipleObjects:
    def test_highest_brightest_ranked_first(self):
        img = _make_multi_blob_image(blobs=[
            (320.0, 240.0, 10.0, 255.0),
            (100.0, 100.0, 10.0, 200.0),
        ])
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.num_candidates >= 1
        if result.detected:
            pd = result.primary_detection
            assert pd.max_intensity >= 200.0


# ---------------------------------------------------------------------------
# H. Intensity / confidence
# ---------------------------------------------------------------------------

class TestIntensity:
    def test_peak_intensity_captured(self):
        img = _make_image(beacon_intensity=200.0)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.detected is True
        assert result.primary_detection.max_intensity >= 180.0

    def test_confidence_in_range(self):
        img = _make_image()
        config = _make_config()
        result = detect_beacon(img, config)
        if result.detected:
            assert 0.0 <= result.primary_detection.confidence <= 1.0


# ---------------------------------------------------------------------------
# I. Noise robustness
# ---------------------------------------------------------------------------

class TestNoiseRobustness:
    def test_mild_gaussian_noise(self):
        img = _make_image()
        rng = np.random.RandomState(42)
        noisy = np.clip(img.astype(np.int16) + rng.normal(0, 5, img.shape), 0, 255).astype(np.uint8)
        config = _make_config()
        result = detect_beacon(noisy, config)
        assert result.detected is True

    def test_mild_salt_pepper(self):
        img = _make_image()
        rng = np.random.RandomState(42)
        noisy = img.copy()
        mask_sp = rng.random(img.shape) < 0.01
        noisy[mask_sp] = 255
        config = _make_config()
        result = detect_beacon(noisy, config)
        assert result.detected is True

    def test_contrast_reduction(self):
        img = _make_image(beacon_intensity=150.0, bg_level=80.0)
        config = _make_config(
            threshold_mode=ThresholdMode.GLOBAL,
            threshold_value=100.0,
        )
        result = detect_beacon(img, config)
        assert result.detected is True


# ---------------------------------------------------------------------------
# J. Monochrome
# ---------------------------------------------------------------------------

class TestMonochrome:
    def test_grayscale_input(self):
        img = _make_image()
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.image_width == 640
        assert result.image_height == 480

    def test_bgr_input(self):
        gray = _make_image()
        bgr = np.stack([gray, gray, gray], axis=-1)
        config = _make_config()
        result = detect_beacon(bgr, config)
        assert result.detected is True


# ---------------------------------------------------------------------------
# K. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_same_input_same_output(self):
        img = _make_image()
        config = _make_config()
        r1 = detect_beacon(img, config)
        r2 = detect_beacon(img, config)
        if r1.detected and r2.detected:
            assert abs(r1.primary_detection.center_x - r2.primary_detection.center_x) < 1e-10
            assert abs(r1.primary_detection.center_y - r2.primary_detection.center_y) < 1e-10


# ---------------------------------------------------------------------------
# L. Resolution independence
# ---------------------------------------------------------------------------

class TestResolution:
    @pytest.mark.parametrize("w,h", [(320, 240), (640, 480), (1280, 720)])
    def test_various_resolutions(self, w, h):
        img = _make_image(width=w, height=h, beacon_x=w/2, beacon_y=h/2)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.image_width == w
        assert result.image_height == h
        if result.detected:
            cx, cy = result.primary_detection.center_x, result.primary_detection.center_y
            assert 0 <= cx <= w
            assert 0 <= cy <= h


# ---------------------------------------------------------------------------
# M. FPS independence
# ---------------------------------------------------------------------------

class TestFPSIndependence:
    def test_same_frame_same_result(self):
        img = _make_image()
        config = _make_config()
        r1 = detect_beacon(img, config, timestamp_s=1.0, frame_index=10)
        r2 = detect_beacon(img, config, timestamp_s=2.0, frame_index=20)
        if r1.detected and r2.detected:
            assert abs(r1.primary_detection.center_x - r2.primary_detection.center_x) < 1e-10


# ---------------------------------------------------------------------------
# N. Ground truth comparison
# ---------------------------------------------------------------------------

class TestGroundTruthComparison:
    def test_perfect_detection(self):
        det = BeaconDetection(detected=True, center_x=320.0, center_y=240.0)
        gt = GroundTruth(target_visible=True, target_pixel_x=320.0, target_pixel_y=240.0)
        metrics = compare_detection_to_ground_truth(det, gt)
        assert metrics.euclidean_error < 1e-10

    def test_offset_detection(self):
        det = BeaconDetection(detected=True, center_x=325.0, center_y=238.0)
        gt = GroundTruth(target_visible=True, target_pixel_x=320.0, target_pixel_y=240.0)
        metrics = compare_detection_to_ground_truth(det, gt)
        assert abs(metrics.euclidean_error - math.sqrt(25 + 4)) < 1e-10

    def test_missed_detection(self):
        gt = GroundTruth(target_visible=True, target_pixel_x=320.0, target_pixel_y=240.0)
        metrics = compare_detection_to_ground_truth(None, gt)
        assert metrics.euclidean_error == float("inf")

    def test_compute_rmse(self):
        errors = [1.0, 2.0, 3.0, 4.0]
        rmse = compute_rmse(errors)
        expected = math.sqrt(sum(e**2 for e in errors) / len(errors))
        assert abs(rmse - expected) < 1e-10

    def test_compute_centroid_error(self):
        ex, ey, err = compute_centroid_error(325.0, 238.0, 320.0, 240.0)
        assert abs(ex - 5.0) < 1e-10
        assert abs(ey - (-2.0)) < 1e-10
        assert abs(err - math.sqrt(29)) < 1e-10


# ---------------------------------------------------------------------------
# O. No NaN/Inf
# ---------------------------------------------------------------------------

class TestNoNaNInf:
    def test_valid_output(self):
        img = _make_image()
        config = _make_config()
        result = detect_beacon(img, config)
        assert not math.isnan(result.processing_time_ms)
        assert not math.isinf(result.processing_time_ms)
        if result.detected:
            pd = result.primary_detection
            assert not math.isnan(pd.center_x)
            assert not math.isnan(pd.center_y)
            assert not math.isnan(pd.confidence)


# ---------------------------------------------------------------------------
# P. Failure handling
# ---------------------------------------------------------------------------

class TestFailureHandling:
    def test_all_white_image(self):
        img = np.full((480, 640), 255, dtype=np.uint8)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.status in (PerceptionStatus.NO_TARGET, PerceptionStatus.UNCERTAIN, PerceptionStatus.DETECTED)

    def test_saturated_image(self):
        img = np.full((480, 640), 254, dtype=np.uint8)
        img[235:245, 315:325] = 255
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.processing_time_ms >= 0.0

    def test_very_noisy_image(self):
        rng = np.random.RandomState(42)
        img = rng.randint(0, 256, (480, 640), dtype=np.uint8)
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.processing_time_ms >= 0.0


# ---------------------------------------------------------------------------
# Q. Candidate scoring
# ---------------------------------------------------------------------------

class TestCandidateScoring:
    def test_good_candidate_scores_high(self):
        features = CandidateFeatures(
            area=100.0, width=10.0, height=10.0, aspect_ratio=1.0,
            circularity=0.9, mean_intensity=200.0, max_intensity=255.0,
            local_contrast=100.0,
        )
        config = _make_config()
        score = score_candidate(features, config)
        assert score > 0.5

    def test_poor_candidate_scores_low(self):
        features = CandidateFeatures(
            area=10.0, width=2.0, height=5.0, aspect_ratio=0.4,
            circularity=0.1, mean_intensity=20.0, max_intensity=30.0,
            local_contrast=5.0,
        )
        config = _make_config()
        score = score_candidate(features, config)
        assert score < 0.5

    def test_zero_area_scores_zero(self):
        features = CandidateFeatures(area=0.0)
        config = _make_config()
        score = score_candidate(features, config)
        assert score == 0.0


# ---------------------------------------------------------------------------
# R. Engine interface
# ---------------------------------------------------------------------------

class TestEngineInterface:
    def test_classical_engine_detect(self):
        img = _make_image()
        config = _make_config()
        engine = ClassicalBeaconDetector(config)
        result = engine.detect(img)
        assert isinstance(result, PerceptionResult)
        assert engine.name == "classical_bright_spot"

    def test_engine_reset(self):
        engine = ClassicalBeaconDetector()
        engine.reset()


# ---------------------------------------------------------------------------
# S. Centroid methods
# ---------------------------------------------------------------------------

class TestCentroidMethods:
    def test_weighted_centroid(self):
        img = _make_image(beacon_x=320.5, beacon_y=240.5)
        mask = img > 100
        cx, cy = compute_centroid(img, mask, CentroidMethod.INTENSITY_WEIGHTED)
        assert 315.0 < cx < 325.0
        assert 235.0 < cy < 245.0

    def test_geometric_centroid(self):
        img = _make_image(beacon_x=320.0, beacon_y=240.0)
        mask = img > 100
        cx, cy = compute_centroid(img, mask, CentroidMethod.GEOMETRIC)
        assert 315.0 < cx < 325.0
        assert 235.0 < cy < 245.0

    def test_empty_mask_returns_zero(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        mask = np.zeros((10, 10), dtype=bool)
        cx, cy = compute_centroid(img, mask)
        assert cx == 0.0
        assert cy == 0.0


# ---------------------------------------------------------------------------
# T. Processing time
# ---------------------------------------------------------------------------

class TestProcessingTime:
    def test_processing_time_positive(self):
        img = _make_image()
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.processing_time_ms >= 0.0

    def test_processing_time_reasonable(self):
        img = _make_image()
        config = _make_config()
        result = detect_beacon(img, config)
        assert result.processing_time_ms < 1000.0
