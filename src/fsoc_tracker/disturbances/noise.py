"""Sensor noise disturbances — Gaussian, Poisson, Salt-and-Pepper.

All noise models operate on image arrays (float64, range [0, max_intensity]).
Each function is deterministic given the same seed.
"""

from __future__ import annotations

import numpy as np

from fsoc_tracker.disturbances.config import NoiseConfig
from fsoc_tracker.disturbances.context import DisturbanceContext


def apply_gaussian_noise(
    image: np.ndarray,
    sigma: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply additive Gaussian noise: I_noisy = I + N(0, sigma^2).

    Args:
        image: Input image (float64).
        sigma: Standard deviation of noise.
        rng: NumPy random generator for determinism.

    Returns:
        Noisy image clipped to [0, max_intensity].
    """
    if sigma <= 0:
        return image

    noise = rng.normal(0.0, sigma, image.shape)
    noisy = image + noise
    max_val = image.max() if image.size > 0 else 255.0
    return np.clip(noisy, 0.0, max_val)


def apply_salt_pepper_noise(
    image: np.ndarray,
    density: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply salt-and-pepper noise.

    Randomly replaces a fraction of pixels with min or max intensity.

    Args:
        image: Input image (float64).
        density: Fraction of pixels to replace (0 to 1).
        rng: NumPy random generator.

    Returns:
        Corrupted image.
    """
    if density <= 0:
        return image

    max_val = image.max() if image.size > 0 else 255.0
    min_val = 0.0
    total_pixels = image.size
    num_corrupt = int(total_pixels * density)

    if num_corrupt <= 0:
        return image

    result = image.copy()

    # Random pixel positions
    flat_indices = rng.choice(total_pixels, size=num_corrupt, replace=False)
    coords = np.unravel_index(flat_indices, image.shape)

    # Randomly assign salt or pepper
    salt_mask = rng.random(num_corrupt) < 0.5
    result[coords] = np.where(salt_mask, max_val, min_val)

    return result


def apply_poisson_noise(
    image: np.ndarray,
    scale: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply simplified Poisson/shot noise model.

    Scales image to approximate photon counts, applies Poisson sampling,
    then rescales back.

    Args:
        image: Input image (float64, range [0, max_intensity]).
        scale: Scaling factor (higher = more noise).
        rng: NumPy random generator.

    Returns:
        Noisy image clipped to valid range.
    """
    if scale <= 0:
        return image

    max_val = image.max() if image.size > 0 else 255.0
    if max_val <= 0:
        return image

    # Scale to approximate photon counts (lambda)
    # Higher scale = fewer photons = more noise
    lambda_img = np.maximum(image / max_val * scale * 100.0, 1e-6)

    # Poisson sampling
    sampled = rng.poisson(lambda_img).astype(np.float64)

    # Rescale back to original range
    result = sampled / (scale * 100.0) * max_val

    return np.clip(result, 0.0, max_val)


def apply_noise(
    image: np.ndarray,
    config: NoiseConfig,
    context: DisturbanceContext,
) -> np.ndarray:
    """Apply all configured noise disturbances in sequence.

    Order: Gaussian → Poisson → Salt-and-Pepper.

    Args:
        image: Input image (float64).
        config: Noise configuration.
        context: Disturbance context.

    Returns:
        Noisy image.
    """
    if not config.enabled:
        return image

    rng = np.random.default_rng(config.seed + context.frame_index * 1000)

    result = image.copy()

    # Gaussian noise
    result = apply_gaussian_noise(result, config.gaussian_sigma, rng)

    # Poisson noise
    if config.poisson_enabled:
        result = apply_poisson_noise(result, config.poisson_scale, rng)

    # Salt-and-pepper noise
    result = apply_salt_pepper_noise(result, config.salt_pepper_density, rng)

    return result
