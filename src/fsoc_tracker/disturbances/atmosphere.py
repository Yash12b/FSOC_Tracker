"""Atmospheric disturbances — Haze, Fog, Rain, LowLight, Turbulence.

All atmospheric models are lightweight image-space approximations.
They do NOT claim to be physically accurate radiative-transfer models.
"""

from __future__ import annotations

import numpy as np

from fsoc_tracker.disturbances.config import AtmosphereConfig, AtmosphereMode
from fsoc_tracker.disturbances.context import DisturbanceContext


def apply_haze(
    image: np.ndarray,
    strength: float,
    atmospheric_intensity: float,
) -> np.ndarray:
    """Apply lightweight haze model using atmospheric scattering approximation.

    I_out = T * I_in + (1 - T) * A

    where T = transmission (1 - strength), A = atmospheric light.

    Args:
        image: Input image (float64).
        strength: Haze strength (0=clear, 1=fully opaque).
        atmospheric_intensity: Atmospheric light intensity.

    Returns:
        Hazed image.
    """
    if strength <= 0:
        return image

    transmission = max(0.0, 1.0 - strength)
    result = transmission * image + (1.0 - transmission) * atmospheric_intensity
    max_val = image.max() if image.size > 0 else 255.0
    return np.clip(result, 0.0, max_val)


def apply_fog(
    image: np.ndarray,
    strength: float,
    atmospheric_intensity: float,
) -> np.ndarray:
    """Apply fog model (stronger version of haze).

    Same scattering model as haze but designed for stronger degradation.
    Uses the same formula: I_out = T * I_in + (1 - T) * A

    Args:
        image: Input image (float64).
        strength: Fog strength (0=clear, 1=fully opaque).
        atmospheric_intensity: Atmospheric light intensity.

    Returns:
        Fogged image.
    """
    if strength <= 0:
        return image

    transmission = max(0.0, 1.0 - strength)
    result = transmission * image + (1.0 - transmission) * atmospheric_intensity
    max_val = image.max() if image.size > 0 else 255.0
    return np.clip(result, 0.0, max_val)


def apply_rain(
    image: np.ndarray,
    config: AtmosphereConfig,
    rng: np.random.Generator,
) -> np.ndarray:
    """Apply lightweight rain degradation.

    Creates sparse semitransparent streaks with configurable angle and length.

    Args:
        image: Input image (float64).
        config: Atmosphere config with rain parameters.
        rng: NumPy random generator.

    Returns:
        Image with rain streaks.
    """
    if config.rain_density <= 0:
        return image

    h, w = image.shape[:2]
    result = image.copy()

    # Number of rain streaks proportional to density and image area
    num_streaks = int(config.rain_density * w * h / 1000)
    num_streaks = max(1, num_streaks)

    angle_rad = np.radians(config.rain_streak_angle_deg)
    dx = np.cos(angle_rad)
    dy = np.sin(angle_rad)

    for _ in range(num_streaks):
        # Random starting position
        x0 = rng.integers(0, w)
        y0 = rng.integers(-config.rain_streak_length, h)

        length = config.rain_streak_length
        streak_opacity = config.rain_opacity

        # Draw streak pixels
        for t in range(length):
            x = int(x0 + dx * t)
            y = int(y0 + dy * t)
            if 0 <= x < w and 0 <= y < h:
                # Blend streak with existing pixel
                alpha = streak_opacity * (1.0 - t / length)
                result[y, x] = (
                    (1.0 - alpha) * result[y, x]
                    + alpha * config.rain_brightness
                )

    return np.clip(result, 0.0, 255.0)


def apply_low_light(
    image: np.ndarray,
    brightness_factor: float,
    contrast_factor: float,
    gamma: float,
) -> np.ndarray:
    """Apply low-light degradation.

    I_out = contrast * (brightness * I)^gamma

    Args:
        image: Input image (float64).
        brightness_factor: Brightness multiplier (1.0=normal).
        contrast_factor: Contrast multiplier (1.0=normal).
        gamma: Gamma correction (1.0=linear).

    Returns:
        Low-light degraded image.
    """
    if brightness_factor >= 1.0 and contrast_factor >= 1.0 and gamma <= 1.0:
        return image

    max_val = image.max() if image.size > 0 else 255.0
    if max_val <= 0:
        return image

    # Normalize to [0, 1]
    normalized = image / max_val

    # Apply brightness and gamma
    adjusted = brightness_factor * normalized
    adjusted = np.power(np.maximum(adjusted, 0.0), gamma)

    # Apply contrast (around midpoint)
    adjusted = contrast_factor * (adjusted - 0.5) + 0.5

    return np.clip(adjusted * max_val, 0.0, max_val)


def apply_atmosphere(
    image: np.ndarray,
    config: AtmosphereConfig,
    context: DisturbanceContext,
) -> np.ndarray:
    """Apply all configured atmospheric disturbances.

    Order: haze → fog → rain → low_light.

    Args:
        image: Input image (float64).
        config: Atmosphere configuration.
        context: Disturbance context.

    Returns:
        Atmospherically degraded image.
    """
    if not config.enabled:
        return image

    rng = np.random.default_rng(config.seed + context.frame_index * 2000)

    result = image.copy()

    # Haze
    if config.mode in (AtmosphereMode.HAZE, AtmosphereMode.CLEAR) and config.haze_strength > 0:
        result = apply_haze(result, config.haze_strength, config.haze_atmospheric_intensity)

    # Fog
    if config.fog_strength > 0:
        result = apply_fog(result, config.fog_strength, config.fog_atmospheric_intensity)

    # Rain
    if config.rain_density > 0:
        result = apply_rain(result, config, rng)

    # Low light
    if config.low_light_factor < 1.0 or config.low_light_gamma > 1.0:
        result = apply_low_light(
            result,
            config.low_light_factor,
            config.low_light_contrast,
            config.low_light_gamma,
        )

    return result
