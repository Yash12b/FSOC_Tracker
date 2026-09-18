"""Optical turbulence approximation — spatially varying displacement field.

Lightweight image-space approximation of atmospheric turbulence.
This is NOT a physically accurate model.

Model:
    x' = x + dx(x, y, t)
    y' = y + dy(x, y, t)

where dx, dy are smooth, spatially correlated displacement fields
generated using superposition of low-frequency sinusoidal components.
"""

from __future__ import annotations

import math

import numpy as np

from fsoc_tracker.disturbances.config import TurbulenceConfig
from fsoc_tracker.disturbances.context import DisturbanceContext


def generate_turbulence_field(
    width: int,
    height: int,
    config: TurbulenceConfig,
    timestamp_s: float,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate smooth turbulence displacement fields.

    Creates spatially correlated dx/dy displacement fields using
    superposition of sinusoidal basis functions.

    Args:
        width: Image width.
        height: Image height.
        config: Turbulence configuration.
        timestamp_s: Current time.
        rng: NumPy random generator.

    Returns:
        (dx_field, dy_field) each of shape (height, width) in pixels.
    """
    if config.strength <= 0:
        return (
            np.zeros((height, width), dtype=np.float64),
            np.zeros((height, width), dtype=np.float64),
        )

    x = np.linspace(0, 1, width, dtype=np.float64)
    y = np.linspace(0, 1, height, dtype=np.float64)
    xx, yy = np.meshgrid(x, y)

    # Generate random phase offsets for basis functions
    num_bases = 4
    phases_x = rng.uniform(0, 2 * math.pi, size=num_bases)
    phases_y = rng.uniform(0, 2 * math.pi, size=num_bases)
    freq_multipliers = rng.uniform(0.5, 2.0, size=num_bases)

    omega = 2.0 * math.pi * config.temporal_frequency
    spatial_freq = 2.0 * math.pi / max(config.spatial_scale, 1.0)

    # Superposition of smooth sinusoidal components
    dx = np.zeros_like(xx)
    dy = np.zeros_like(yy)

    for i in range(num_bases):
        freq = spatial_freq * freq_multipliers[i]
        amp = config.strength / num_bases
        dx += amp * np.sin(freq * xx + omega * timestamp_s + phases_x[i])
        dy += amp * np.sin(freq * yy + omega * timestamp_s + phases_y[i])

    # Normalize to configured strength
    max_disp = max(np.max(np.abs(dx)), np.max(np.abs(dy)), 1e-6)
    dx = dx / max_disp * config.strength
    dy = dy / max_disp * config.strength

    return (dx, dy)


def apply_turbulence_warp(
    image: np.ndarray,
    dx_field: np.ndarray,
    dy_field: np.ndarray,
) -> np.ndarray:
    """Apply turbulence displacement field to image using remapping.

    Args:
        image: Input image.
        dx_field: Horizontal displacement field (pixels).
        dy_field: Vertical displacement field (pixels).

    Returns:
        Warped image.
    """
    h, w = image.shape[:2]

    # Build coordinate grids
    x_coords = np.arange(w, dtype=np.float32)
    y_coords = np.arange(h, dtype=np.float32)
    xx, yy = np.meshgrid(x_coords, y_coords)

    # Remap coordinates: original position + displacement
    map_x = (xx + dx_field.astype(np.float32)).astype(np.float32)
    map_y = (yy + dy_field.astype(np.float32)).astype(np.float32)

    # Use nearest-neighbor interpolation for speed
    # (bilinear would be smoother but slower)
    try:
        import cv2
        result = cv2.remap(
            image.astype(np.float32), map_x, map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )
    except ImportError:
        # Fallback: simple nearest-neighbor without OpenCV
        map_x_int = np.clip(np.round(map_x).astype(int), 0, w - 1)
        map_y_int = np.clip(np.round(map_y).astype(int), 0, h - 1)
        result = image[map_y_int, map_x_int]

    return result.astype(np.float64)


def apply_turbulence(
    image: np.ndarray,
    config: TurbulenceConfig,
    context: DisturbanceContext,
) -> np.ndarray:
    """Apply turbulence disturbance to image.

    Args:
        image: Input image (float64).
        config: Turbulence configuration.
        context: Disturbance context.

    Returns:
        Turbulence-degraded image.
    """
    if not config.enabled or config.strength <= 0:
        return image

    rng = np.random.default_rng(config.seed + context.frame_index * 5000)

    h, w = image.shape[:2]
    dx_field, dy_field = generate_turbulence_field(
        w, h, config, context.timestamp_s, rng,
    )

    return apply_turbulence_warp(image, dx_field, dy_field)
