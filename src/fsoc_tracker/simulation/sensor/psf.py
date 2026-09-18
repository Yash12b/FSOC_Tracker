"""Point-spread function (PSF) for optical blur.

Implements a lightweight 2D Gaussian PSF model.
The PSF is not a complete optical propagation model; it provides
a controlled blur that can later be combined with disturbances.
"""

from __future__ import annotations

import numpy as np


def gaussian_psf_2d(
    sigma: float,
    truncate: float = 4.0,
) -> np.ndarray:
    """Generate a normalized 2D Gaussian PSF kernel.

    Args:
        sigma: Standard deviation in pixels.
        truncate: Truncate at this many sigma from center.

    Returns:
        2D numpy array (normalized, sums to 1.0).
    """
    radius = int(np.ceil(truncate * sigma))
    2 * radius + 1
    ax = np.arange(-radius, radius + 1, dtype=np.float64)
    xx, yy = np.meshgrid(ax, ax)
    kernel = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))
    kernel /= kernel.sum()
    return kernel


def apply_psf(
    image: np.ndarray,
    sigma: float,
    truncate: float = 4.0,
) -> np.ndarray:
    """Apply Gaussian PSF to an entire image via convolution.

    For efficiency, this uses numpy-style direct convolution.
    For localized beacons, prefer depositing the PSF directly
    at the beacon location instead of convolving the full frame.

    Args:
        image: Input image (2D float64 array).
        sigma: PSF sigma in pixels.
        truncate: Truncation radius in sigma units.

    Returns:
        Blurred image (same shape as input).
    """
    if sigma <= 0:
        return image.copy()

    kernel = gaussian_psf_2d(sigma, truncate)
    kh, kw = kernel.shape
    pad_h, pad_w = kh // 2, kw // 2

    padded = np.pad(image, ((pad_h, pad_h), (pad_w, pad_w)), mode="edge")
    output = np.zeros_like(image, dtype=np.float64)

    for i in range(image.shape[0]):
        for j in range(image.shape[1]):
            patch = padded[i:i + kh, j:j + kw]
            output[i, j] = np.sum(patch * kernel)

    return output
