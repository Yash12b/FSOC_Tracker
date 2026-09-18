"""Motion disturbances — camera jitter and platform motion.

These are GEOMETRIC disturbances that modify effective camera pose.
They are applied PRE-RENDER, not as image filters.

Camera jitter:
    High-frequency small disturbances in camera pointing.
    Model: nominal_pose + jitter_offset = effective_pose

Platform motion:
    Lower-frequency intentional motion of the entire platform.
    Model: platform_pose(t) + mounting_transform = camera_pose(t)
"""

from __future__ import annotations

import math

import numpy as np

from fsoc_tracker.disturbances.config import (
    JitterConfig,
    JitterModel,
    PlatformMotionConfig,
    PlatformMotionType,
)
from fsoc_tracker.disturbances.context import (
    DisturbanceContext,
)


def compute_jitter_offset(
    config: JitterConfig,
    context: DisturbanceContext,
) -> tuple[float, float]:
    """Compute camera jitter pixel offset at current time.

    Args:
        config: Jitter configuration.
        context: Disturbance context.

    Returns:
        (offset_x_px, offset_y_px) jitter displacement.
    """
    if not config.enabled or config.amplitude_px <= 0:
        return (0.0, 0.0)

    t = context.timestamp_s
    rng = np.random.default_rng(config.seed + context.frame_index * 3000)

    model = config.model

    if model == JitterModel.BOUNDED:
        # Bounded random displacement within [-amplitude, +amplitude]
        offset_x = float(rng.uniform(-config.amplitude_px, config.amplitude_px))
        offset_y = float(rng.uniform(-config.amplitude_px, config.amplitude_px))
        return (offset_x, offset_y)

    if model == JitterModel.GAUSSIAN:
        # Gaussian random displacement (3-sigma = amplitude)
        sigma = config.amplitude_px / 3.0
        offset_x = float(rng.normal(0.0, sigma))
        offset_y = float(rng.normal(0.0, sigma))
        # Clip to amplitude bounds
        offset_x = max(-config.amplitude_px, min(config.amplitude_px, offset_x))
        offset_y = max(-config.amplitude_px, min(config.amplitude_px, offset_y))
        return (offset_x, offset_y)

    if model == JitterModel.SINUSOIDAL:
        omega = 2.0 * math.pi * config.frequency_hz
        offset_x = config.amplitude_px * math.sin(omega * t)
        offset_y = config.amplitude_px * math.sin(omega * t + math.pi / 3.0)
        return (offset_x, offset_y)

    if model == JitterModel.DAMPED_VIBRATION:
        omega = 2.0 * math.pi * config.frequency_hz
        decay = math.exp(-config.damping * t)
        offset_x = config.amplitude_px * decay * math.sin(omega * t)
        offset_y = config.amplitude_px * decay * math.sin(omega * t + math.pi / 4.0)
        return (offset_x, offset_y)

    return (0.0, 0.0)


def compute_platform_offset(
    config: PlatformMotionConfig,
    context: DisturbanceContext,
) -> tuple[float, float]:
    """Compute platform motion pixel offset at current time.

    Args:
        config: Platform motion configuration.
        context: Disturbance context.

    Returns:
        (offset_x_px, offset_y_px) platform motion displacement.
    """
    if not config.enabled or config.type == PlatformMotionType.NONE:
        return (0.0, 0.0)

    t = context.timestamp_s
    np.random.default_rng(config.seed + context.frame_index * 4000)

    ptype = config.type
    amp_x = config.amplitude_x_px
    amp_y = config.amplitude_y_px
    speed = config.speed

    if ptype == PlatformMotionType.LINEAR:
        # Linear drift: position = speed * t (wraps within amplitude)
        offset_x = amp_x * math.sin(2.0 * math.pi * speed * t)
        offset_y = amp_y * math.sin(2.0 * math.pi * speed * t)
        return (offset_x, offset_y)

    if ptype == PlatformMotionType.CIRCULAR:
        omega = 2.0 * math.pi * speed
        offset_x = amp_x * math.sin(omega * t)
        offset_y = amp_y * math.cos(omega * t)
        return (offset_x, offset_y)

    if ptype == PlatformMotionType.FIGURE_EIGHT:
        omega = 2.0 * math.pi * speed
        offset_x = amp_x * math.sin(omega * t)
        offset_y = amp_y * math.sin(2.0 * omega * t)
        return (offset_x, offset_y)

    if ptype == PlatformMotionType.SPIRAL:
        omega = 2.0 * math.pi * speed
        # Expanding spiral: amplitude grows with time (bounded by configured amplitude)
        phase = (t * speed) % 1.0
        r = amp_x * phase
        offset_x = r * math.cos(omega * t)
        offset_y = r * math.sin(omega * t)
        return (offset_x, offset_y)

    if ptype == PlatformMotionType.RANDOM:
        # Smooth random motion using low-frequency noise
        # Use sine combination for smooth deterministic randomness
        omega = 2.0 * math.pi * speed * 0.1
        offset_x = amp_x * (
            0.5 * math.sin(omega * t + 0.0)
            + 0.3 * math.sin(omega * t * 1.7 + 1.2)
            + 0.2 * math.sin(omega * t * 2.3 + 2.4)
        )
        offset_y = amp_y * (
            0.5 * math.sin(omega * t + 0.8)
            + 0.3 * math.sin(omega * t * 1.3 + 2.1)
            + 0.2 * math.sin(omega * t * 2.7 + 0.5)
        )
        return (offset_x, offset_y)

    return (0.0, 0.0)


def pixel_offset_to_angle(
    offset_x_px: float,
    offset_y_px: float,
    fx: float,
    fy: float,
) -> tuple[float, float]:
    """Convert pixel offset to angular offset.

    Args:
        offset_x_px: Horizontal pixel displacement.
        offset_y_px: Vertical pixel displacement.
        fx: Horizontal focal length in pixels.
        fy: Vertical focal length in pixels.

    Returns:
        (angle_h_deg, angle_v_deg) angular displacement.
    """
    angle_h_deg = math.degrees(math.atan2(offset_x_px, fx)) if fx > 0 else 0.0
    angle_v_deg = math.degrees(math.atan2(-offset_y_px, fy)) if fy > 0 else 0.0
    return (angle_h_deg, angle_v_deg)
