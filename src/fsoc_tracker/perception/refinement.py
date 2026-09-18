"""Coarse-to-fine perception and subpixel beacon refinement.

Two-stage localization:
    FULL FRAME -> fast detection -> candidate center
    ROI CROP -> high-quality centroid refinement

Supports intensity-weighted centroid, Gaussian peak fitting,
and PSF-aware estimation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import numpy as np


class RefinementMethod(Enum):
    INTENSITY_WEIGHTED = auto()
    GAUSSIAN_FIT = auto()
    PSF_AWARE = auto()
    MOMENTS = auto()


@dataclass
class RefinedCentroid:
    """Subpixel-refined centroid result."""

    x: float = 0.0
    y: float = 0.0
    method: RefinementMethod = RefinementMethod.INTENSITY_WEIGHTED
    confidence: float = 0.0
    fit_residual: float = 0.0
    refinement_delta_x: float = 0.0
    refinement_delta_y: float = 0.0
    roi_size: tuple[int, int] = (0, 0)
    succeeded: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefinementConfig:
    """Configuration for centroid refinement."""

    method: RefinementMethod = RefinementMethod.INTENSITY_WEIGHTED
    roi_half_size: int = 15
    min_roi_pixels: int = 4
    background_subtraction: bool = True
    gaussian_fit_max_iterations: int = 20
    psf_sigma: float = 2.0
    max_refinement_delta: float = 5.0


class CoarseToFineRefiner:
    """Two-stage coarse-to-fine centroid refinement.

    Stage 1: Full-frame detection provides coarse center.
    Stage 2: ROI crop around coarse center, subpixel refinement.
    """

    def __init__(self, config: RefinementConfig | None = None) -> None:
        self._config = config or RefinementConfig()

    def refine(
        self,
        image: np.ndarray,
        coarse_x: float,
        coarse_y: float,
    ) -> RefinedCentroid:
        """Refine a coarse detection to subpixel accuracy.

        Args:
            image: Grayscale uint8 image.
            coarse_x: Coarse detection center x.
            coarse_y: Coarse detection center y.

        Returns:
            RefinedCentroid with subpixel position.
        """
        if image is None or image.size == 0:
            return RefinedCentroid(x=coarse_x, y=coarse_y)

        img = image.astype(np.float64)
        if img.ndim == 3:
            img = np.mean(img, axis=2)

        h, w = img.shape
        half = self._config.roi_half_size

        x1 = max(0, int(coarse_x) - half)
        y1 = max(0, int(coarse_y) - half)
        x2 = min(w, int(coarse_x) + half + 1)
        y2 = min(h, int(coarse_y) + half + 1)

        roi = img[y1:y2, x1:x2]

        if roi.size < self._config.min_roi_pixels:
            return RefinedCentroid(x=coarse_x, y=coarse_y, roi_size=(x2-x1, y2-y1))

        if self._config.background_subtraction:
            bg = float(np.percentile(roi, 10))
            roi = roi - bg
            roi = np.clip(roi, 0, None)

        if np.max(roi) < 1.0:
            return RefinedCentroid(x=coarse_x, y=coarse_y, roi_size=(x2-x1, y2-y1))

        method = self._config.method

        if method == RefinementMethod.INTENSITY_WEIGHTED:
            result = self._intensity_weighted(roi, x1, y1)
        elif method == RefinementMethod.GAUSSIAN_FIT:
            result = self._gaussian_fit(roi, x1, y1)
        elif method == RefinementMethod.MOMENTS:
            result = self._moment_based(roi, x1, y1)
        else:
            result = self._intensity_weighted(roi, x1, y1)

        result.roi_size = (x2 - x1, y2 - y1)
        result.method = method
        result.refinement_delta_x = result.x - coarse_x
        result.refinement_delta_y = result.y - coarse_y

        delta = math.sqrt(result.refinement_delta_x ** 2 + result.refinement_delta_y ** 2)
        if delta > self._config.max_refinement_delta:
            result.x = coarse_x
            result.y = coarse_y
            result.succeeded = False
            result.confidence *= 0.5
        else:
            result.succeeded = True

        return result

    def _intensity_weighted(
        self, roi: np.ndarray, offset_x: int, offset_y: int
    ) -> RefinedCentroid:
        """Intensity-weighted centroid (center of mass)."""
        h, w = roi.shape
        yy, xx = np.mgrid[:h, :w]
        total = float(np.sum(roi))
        if total < 1.0:
            return RefinedCentroid(x=float(offset_x + w / 2), y=float(offset_y + h / 2))
        cx = float(np.sum(xx * roi) / total) + offset_x
        cy = float(np.sum(yy * roi) / total) + offset_y
        max_val = float(np.max(roi))
        return RefinedCentroid(
            x=cx, y=cy, confidence=min(1.0, max_val / 255.0),
        )

    def _gaussian_fit(
        self, roi: np.ndarray, offset_x: int, offset_y: int
    ) -> RefinedCentroid:
        """2D Gaussian peak fitting for subpixel localization."""
        h, w = roi.shape
        if h < 5 or w < 5:
            return self._intensity_weighted(roi, offset_x, offset_y)

        yy, xx = np.mgrid[:h, :w]
        peak_val = float(np.max(roi))
        if peak_val < 1.0:
            return RefinedCentroid(x=float(offset_x + w / 2), y=float(offset_y + h / 2))

        roi_norm = roi / peak_val

        cxGuess = float(np.argmax(np.max(roi, axis=0)))
        cyGuess = float(np.argmax(np.max(roi, axis=1)))
        sigma_x = max(1.0, w / 6.0)
        sigma_y = max(1.0, h / 6.0)

        best_cx, best_cy = cxGuess, cyGuess
        float("inf")

        for _ in range(self._config.gaussian_fit_max_iterations):
            mask = ((xx - best_cx) ** 2 / (2 * sigma_x ** 2) + (yy - best_cy) ** 2 / (2 * sigma_y ** 2)) < 4.0
            if not np.any(mask):
                break
            gx = xx[mask]
            gy = yy[mask]
            gv = roi_norm[mask]
            total_w = float(np.sum(gv))
            if total_w < 0.01:
                break
            new_cx = float(np.sum(gx * gv) / total_w)
            new_cy = float(np.sum(gy * gv) / total_w)
            if abs(new_cx - best_cx) < 0.01 and abs(new_cy - best_cy) < 0.01:
                best_cx, best_cy = new_cx, new_cy
                break
            best_cx, best_cy = new_cx, new_cy

        predicted = peak_val * np.exp(-(
            (xx - best_cx) ** 2 / (2 * sigma_x ** 2)
            + (yy - best_cy) ** 2 / (2 * sigma_y ** 2)
        ))
        residual = float(np.sqrt(np.mean((roi_norm - predicted / peak_val) ** 2)))

        return RefinedCentroid(
            x=best_cx + offset_x,
            y=best_cy + offset_y,
            confidence=min(1.0, peak_val / 255.0),
            fit_residual=residual,
        )

    def _moment_based(
        self, roi: np.ndarray, offset_x: int, offset_y: int
    ) -> RefinedCentroid:
        """Second-order moment-based centroid."""
        h, w = roi.shape
        yy, xx = np.mgrid[:h, :w]
        total = float(np.sum(roi))
        if total < 1.0:
            return RefinedCentroid(x=float(offset_x + w / 2), y=float(offset_y + h / 2))

        cx = float(np.sum(xx * roi) / total) + offset_x
        cy = float(np.sum(yy * roi) / total) + offset_y

        mu_xx = float(np.sum((xx - cx + offset_x) ** 2 * roi) / total)
        mu_yy = float(np.sum((yy - cy + offset_y) ** 2 * roi) / total)
        spread = math.sqrt(mu_xx + mu_yy)
        confidence = max(0.0, 1.0 - spread / (w + h))

        return RefinedCentroid(
            x=cx, y=cy, confidence=confidence,
        )
