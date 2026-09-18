"""Image quality analysis for adaptive perception.

Lightweight image statistics that drive perception policy decisions.
No neural models — pure image statistics for real-time operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np


class QualityLevel(Enum):
    EXCELLENT = auto()
    GOOD = auto()
    DEGRADED = auto()
    POOR = auto()
    CRITICAL = auto()


@dataclass
class QualityState:
    """Complete image quality assessment for one frame.

    All values are in [0, 1] range where applicable, unless noted.
    This is an internal perception-quality assessment, NOT physical
    atmospheric classification.
    """

    level: QualityLevel = QualityLevel.GOOD

    mean_brightness: float = 0.0
    contrast: float = 0.0
    dynamic_range: float = 0.0
    saturation_pct: float = 0.0
    noise_estimate: float = 0.0
    blur_score: float = 0.0
    edge_density: float = 0.0
    signal_to_background: float = 0.0
    beacon_quality: float = 0.0

    brightness_ok: bool = True
    contrast_ok: bool = True
    noise_ok: bool = True
    blur_ok: bool = True

    def to_dict(self) -> dict:
        return {
            "level": self.level.name,
            "mean_brightness": round(self.mean_brightness, 3),
            "contrast": round(self.contrast, 3),
            "dynamic_range": round(self.dynamic_range, 1),
            "saturation_pct": round(self.saturation_pct, 1),
            "noise_estimate": round(self.noise_estimate, 3),
            "blur_score": round(self.blur_score, 3),
            "edge_density": round(self.edge_density, 3),
            "signal_to_background": round(self.signal_to_background, 3),
            "beacon_quality": round(self.beacon_quality, 3),
        }


@dataclass
class QualityThresholds:
    """Configurable thresholds for quality classification."""

    min_brightness: float = 10.0
    max_brightness: float = 240.0
    min_contrast: float = 15.0
    max_noise: float = 30.0
    max_blur: float = 0.7

    excellent_brightness: tuple[float, float] = (40.0, 200.0)
    excellent_contrast: float = 50.0
    excellent_noise: float = 5.0

    poor_brightness: tuple[float, float] = (5.0, 250.0)
    poor_contrast: float = 8.0
    poor_noise: float = 50.0


class ImageQualityAnalyzer:
    """Estimates lightweight image quality metrics.

    Computes brightness, contrast, noise, blur, edge density,
    and signal-to-background ratio.  Drives adaptive perception
    decisions without expensive neural models.
    """

    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self._thresholds = thresholds or QualityThresholds()

    def analyze(
        self,
        image: np.ndarray,
        detection_region: tuple[int, int, int, int] | None = None,
    ) -> QualityState:
        """Analyze image quality.

        Args:
            image: Grayscale uint8 image (H, W).
            detection_region: Optional (x1, y1, x2, y2) bounding box
                around detected beacon for signal-to-background calc.

        Returns:
            QualityState with all metrics.
        """
        if image is None or image.size == 0:
            return QualityState(level=QualityLevel.CRITICAL)

        img = image.astype(np.float64)
        if img.ndim == 3:
            img = np.mean(img, axis=2)

        state = QualityState()

        state.mean_brightness = float(np.mean(img))
        state.contrast = float(np.std(img))
        state.dynamic_range = float(np.max(img) - np.min(img))

        total_pixels = img.size
        if total_pixels > 0:
            state.saturation_pct = float(
                np.sum((img <= 1) | (img >= 254)) / total_pixels * 100.0
            )
        else:
            state.saturation_pct = 100.0

        state.noise_estimate = self._estimate_noise(img)
        state.blur_score = self._estimate_blur(img)
        state.edge_density = self._estimate_edge_density(img)

        if detection_region is not None:
            state.signal_to_background = self._estimate_sbr(img, detection_region)
            state.beacon_quality = self._estimate_beacon_quality(img, detection_region)
        else:
            state.signal_to_background = 0.0
            state.beacon_quality = 0.0

        state.brightness_ok = self._thresholds.min_brightness <= state.mean_brightness <= self._thresholds.max_brightness
        state.contrast_ok = state.contrast >= self._thresholds.min_contrast
        state.noise_ok = state.noise_estimate <= self._thresholds.max_noise
        state.blur_ok = state.blur_score <= self._thresholds.max_blur

        state.level = self._classify(state)

        return state

    def _estimate_noise(self, img: np.ndarray) -> float:
        """Estimate noise using median absolute deviation of Laplacian."""
        try:
            np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
            h, w = img.shape
            if h < 3 or w < 3:
                return 0.0
            laplacian = np.zeros_like(img)
            laplacian[1:-1, 1:-1] = (
                img[:-2, 1:-1] + img[2:, 1:-1]
                + img[1:-1, :-2] + img[1:-1, 2:]
                - 4.0 * img[1:-1, 1:-1]
            )
            return float(np.median(np.abs(laplacian[1:-1, 1:-1])) / 1.4826)
        except Exception:
            return 0.0

    def _estimate_blur(self, img: np.ndarray) -> float:
        """Estimate blur using variance of Laplacian (lower = blurrier)."""
        try:
            h, w = img.shape
            if h < 3 or w < 3:
                return 1.0
            laplacian = np.zeros_like(img)
            laplacian[1:-1, 1:-1] = (
                img[:-2, 1:-1] + img[2:, 1:-1]
                + img[1:-1, :-2] + img[1:-1, 2:]
                - 4.0 * img[1:-1, 1:-1]
            )
            lap_var = float(np.var(laplacian[1:-1, 1:-1]))
            return 1.0 - min(1.0, lap_var / 500.0)
        except Exception:
            return 0.5

    def _estimate_edge_density(self, img: np.ndarray) -> float:
        """Estimate edge density using Sobel magnitude."""
        try:
            h, w = img.shape
            if h < 3 or w < 3:
                return 0.0
            gx = np.zeros_like(img)
            gy = np.zeros_like(img)
            gx[1:-1, 1:-1] = (
                -img[:-2, :-2] - 2.0 * img[1:-1, :-2] - img[2:, :-2]
                + img[:-2, 2:] + 2.0 * img[1:-1, 2:] + img[2:, 2:]
            )
            gy[1:-1, 1:-1] = (
                -img[:-2, :-2] - 2.0 * img[:-2, 1:-1] - img[:-2, 2:]
                + img[2:, :-2] + 2.0 * img[2:, 1:-1] + img[2:, 2:]
            )
            magnitude = np.sqrt(gx * gx + gy * gy)
            edge_pixels = np.sum(magnitude > 50.0)
            total = (h - 2) * (w - 2)
            return float(edge_pixels / total) if total > 0 else 0.0
        except Exception:
            return 0.0

    def _estimate_sbr(self, img: np.ndarray, region: tuple[int, int, int, int]) -> float:
        """Estimate signal-to-background ratio in detection region."""
        x1, y1, x2, y2 = region
        h, w = img.shape
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))

        beacon = img[y1:y2, x1:x2]
        if beacon.size == 0:
            return 0.0

        signal = float(np.max(beacon))

        margin = 10
        bx1 = max(0, x1 - margin)
        by1 = max(0, y1 - margin)
        bx2 = min(w, x2 + margin)
        by2 = min(h, y2 + margin)

        outer = np.concatenate([
            img[by1:y1, bx1:bx2].ravel(),
            img[y2:by2, bx1:bx2].ravel(),
            img[y1:y2, bx1:x1].ravel(),
            img[y1:y2, x2:bx2].ravel(),
        ])
        bg = float(np.mean(outer)) if outer.size > 0 else 5.0

        if bg < 1.0:
            bg = 1.0
        return signal / bg

    def _estimate_beacon_quality(
        self, img: np.ndarray, region: tuple[int, int, int, int]
    ) -> float:
        """Estimate beacon quality based on circularity and contrast."""
        x1, y1, x2, y2 = region
        h, w = img.shape
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(x1 + 1, min(x2, w))
        y2 = max(y1 + 1, min(y2, h))

        roi = img[y1:y2, x1:x2]
        if roi.size == 0 or roi.size < 4:
            return 0.0

        mean_val = float(np.mean(roi))
        max_val = float(np.max(roi))
        if max_val <= mean_val:
            return 0.0

        threshold = (max_val + mean_val) / 2.0
        bright = roi > threshold
        area = float(np.sum(bright))
        total = float(roi.size)
        if area < 1.0:
            return 0.0

        fill_ratio = area / total

        rh, rw = roi.shape
        center_y, center_x = rh / 2.0, rw / 2.0
        yy, xx = np.mgrid[:rh, :rw]
        dist = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
        mean_dist = float(np.mean(dist[bright])) if np.any(bright) else 0.0
        max_dist = max(rh, rw) / 2.0
        centering = 1.0 - min(1.0, mean_dist / max_dist) if max_dist > 0 else 0.0

        return float(np.clip(fill_ratio * 0.5 + centering * 0.5, 0.0, 1.0))

    def _classify(self, state: QualityState) -> QualityLevel:
        """Classify overall quality level from individual metrics."""
        t = self._thresholds
        issues = 0

        if not state.brightness_ok:
            issues += 2
        elif state.mean_brightness < t.excellent_brightness[0] or state.mean_brightness > t.excellent_brightness[1]:
            issues += 1

        if state.contrast < t.poor_contrast:
            issues += 2
        elif state.contrast < t.excellent_contrast:
            issues += 1

        if state.noise_estimate > t.poor_noise:
            issues += 2
        elif state.noise_estimate > t.excellent_noise:
            issues += 1

        if not state.blur_ok:
            issues += 2
        elif state.blur_score > 0.4:
            issues += 1

        if issues == 0:
            return QualityLevel.EXCELLENT
        elif issues <= 1:
            return QualityLevel.GOOD
        elif issues <= 3:
            return QualityLevel.DEGRADED
        elif issues <= 5:
            return QualityLevel.POOR
        else:
            return QualityLevel.CRITICAL
