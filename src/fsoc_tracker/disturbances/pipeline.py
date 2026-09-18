"""Disturbance pipeline — composable pre-render and post-render disturbances.

Architecture:

    nominal camera pose
        |
        v
    pre_render: camera jitter offset
        |
        v
    pre_render: platform motion offset
        |
        v
    effective camera pose  (used by sensor renderer)
        |
        v
    clean rendered image
        |
        v
    post_render: turbulence warp
        |
        v
    post_render: atmospheric effects (haze, fog, rain, low-light)
        |
        v
    post_render: sensor noise (Gaussian, Poisson, salt-and-pepper)
        |
        v
    disturbed image
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from fsoc_tracker.disturbances.atmosphere import apply_atmosphere
from fsoc_tracker.disturbances.config import DisturbanceConfig
from fsoc_tracker.disturbances.context import (
    CameraPoseContext,
    DisturbanceContext,
)
from fsoc_tracker.disturbances.motion import (
    compute_jitter_offset,
    compute_platform_offset,
    pixel_offset_to_angle,
)
from fsoc_tracker.disturbances.noise import apply_noise
from fsoc_tracker.disturbances.telemetry import DisturbancePerformance, DisturbanceTelemetry
from fsoc_tracker.disturbances.turbulence import apply_turbulence


@dataclass
class EffectiveCameraPose:
    """Result of pre-render disturbance computation."""

    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    pan_deg: float = 0.0
    tilt_deg: float = 0.0
    roll_deg: float = 0.0

    jitter_offset_x_px: float = 0.0
    jitter_offset_y_px: float = 0.0
    platform_offset_x_px: float = 0.0
    platform_offset_y_px: float = 0.0


class DisturbancePipeline:
    """Composable disturbance pipeline with pre/post-render separation.

    Usage::

        pipeline = DisturbancePipeline(config)

        # Pre-render: compute effective camera pose
        effective_pose = pipeline.compute_effective_pose(camera_pose, context)

        # ... render with effective_pose ...

        # Post-render: degrade image
        disturbed_image = pipeline.apply_to_image(clean_image, context)

        # Telemetry
        telemetry = pipeline.last_telemetry
    """

    def __init__(self, config: DisturbanceConfig | None = None) -> None:
        self._config = config or DisturbanceConfig()
        self._telemetry = DisturbanceTelemetry()
        self._performance = DisturbancePerformance()
        # Active disappearance window end (simulation seconds). While set,
        # the target stays suppressed for a real interval (PS: disappearance
        # is temporal, e.g. begins t=5s for 0.75s) instead of flickering.
        self._disappearance_until_s: float | None = None

    @property
    def config(self) -> DisturbanceConfig:
        return self._config

    @property
    def last_telemetry(self) -> DisturbanceTelemetry:
        return self._telemetry

    @property
    def last_performance(self) -> DisturbancePerformance:
        return self._performance

    def set_config(self, config: DisturbanceConfig) -> None:
        """Update pipeline configuration at runtime."""
        self._config = config
        self._disappearance_until_s = None

    def compute_effective_pose(
        self,
        camera_pose: CameraPoseContext,
        context: DisturbanceContext,
    ) -> EffectiveCameraPose:
        """Compute effective camera pose with pre-render disturbances.

        This applies camera jitter and platform motion to produce
        the effective pose used by the sensor renderer.

        Args:
            camera_pose: Nominal camera pose.
            context: Disturbance context.

        Returns:
            EffectiveCameraPose with jitter/platform offsets applied.
        """
        t0 = time.perf_counter()

        effective = EffectiveCameraPose(
            position_x=camera_pose.position_x,
            position_y=camera_pose.position_y,
            position_z=camera_pose.position_z,
            pan_deg=camera_pose.pan_deg,
            tilt_deg=camera_pose.tilt_deg,
            roll_deg=camera_pose.roll_deg,
        )

        if not self._config.enabled:
            self._performance.geometry_ms = 0.0
            return effective

        # Compute jitter offset
        jitter_x, jitter_y = 0.0, 0.0
        if self._config.jitter.enabled:
            jitter_x, jitter_y = compute_jitter_offset(
                self._config.jitter, context,
            )
            effective.jitter_offset_x_px = jitter_x
            effective.jitter_offset_y_px = jitter_y

        # Compute platform motion offset
        plat_x, plat_y = 0.0, 0.0
        if self._config.platform_motion.enabled:
            plat_x, plat_y = compute_platform_offset(
                self._config.platform_motion, context,
            )
            effective.platform_offset_x_px = plat_x
            effective.platform_offset_y_px = plat_y

        # Convert pixel offsets to angular offsets and apply to camera pose
        # Use image dimensions and intrinsics to compute angular displacement
        total_offset_x = jitter_x + plat_x
        total_offset_y = jitter_y + plat_y

        if abs(total_offset_x) > 0 or abs(total_offset_y) > 0:
            # Approximate angular offset from pixel displacement
            # fx ≈ width / (2 * tan(HFOV/2)), but we don't have intrinsics here
            # Use a simple approximation: 1 pixel ≈ HFOV/width degrees
            # This is approximate; the caller should use proper intrinsics for precision
            hfov_rad = np.radians(4.0)  # default 4-degree HFOV
            vfov_rad = np.radians(3.0)  # default 3-degree VFOV
            approx_fx = context.image_width / (2.0 * np.tan(hfov_rad / 2.0))
            approx_fy = context.image_height / (2.0 * np.tan(vfov_rad / 2.0))

            angle_h, angle_v = pixel_offset_to_angle(
                total_offset_x, total_offset_y, approx_fx, approx_fy,
            )
            effective.pan_deg += angle_h
            effective.tilt_deg += angle_v

        self._performance.geometry_ms = (time.perf_counter() - t0) * 1000.0

        return effective

    def apply_to_image(
        self,
        image: np.ndarray,
        context: DisturbanceContext,
    ) -> np.ndarray:
        """Apply post-render disturbances to a clean image.

        Order: turbulence → blur → motion blur → brightness/contrast
               → atmosphere → distractors → noise.

        Args:
            image: Clean rendered image (uint8).
            context: Disturbance context.

        Returns:
            Disturbed image.
        """
        t_total = time.perf_counter()

        if not self._config.enabled:
            self._telemetry = DisturbanceTelemetry(
                timestamp_s=context.timestamp_s,
                frame_index=context.frame_index,
            )
            self._performance.total_ms = 0.0
            return image

        # Initialize telemetry
        self._telemetry = DisturbanceTelemetry(
            timestamp_s=context.timestamp_s,
            frame_index=context.frame_index,
        )

        result = image.copy()

        # 1. Turbulence (geometric warp, applied to image)
        t0 = time.perf_counter()
        if self._config.turbulence.enabled:
            result = apply_turbulence(result, self._config.turbulence, context)
            self._telemetry.turbulence_strength = self._config.turbulence.strength
            self._telemetry.active_disturbances.append("turbulence")
        self._performance.turbulence_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Gaussian blur
        t0 = time.perf_counter()
        if self._config.blur.enabled:
            from fsoc_tracker.disturbances.optical import apply_gaussian_blur
            result = apply_gaussian_blur(result, self._config.blur.kernel_size, self._config.blur.sigma)
            self._telemetry.active_disturbances.append("blur")
        (time.perf_counter() - t0) * 1000.0

        # 3. Motion blur
        t0 = time.perf_counter()
        if self._config.motion_blur.enabled:
            from fsoc_tracker.disturbances.optical import apply_motion_blur
            result = apply_motion_blur(result, self._config.motion_blur.kernel_size, self._config.motion_blur.angle_deg)
            self._telemetry.active_disturbances.append("motion_blur")
        (time.perf_counter() - t0) * 1000.0

        # 4. Brightness/contrast/gamma
        t0 = time.perf_counter()
        if self._config.brightness_contrast.enabled:
            from fsoc_tracker.disturbances.optical import apply_brightness_contrast
            bc = self._config.brightness_contrast
            result = apply_brightness_contrast(result, bc.brightness, bc.contrast, bc.gamma)
            self._telemetry.active_disturbances.append("brightness_contrast")
        (time.perf_counter() - t0) * 1000.0

        # 5. Atmospheric effects
        t0 = time.perf_counter()
        if self._config.atmosphere.enabled:
            result = apply_atmosphere(result, self._config.atmosphere, context)
            atm = self._config.atmosphere
            self._telemetry.atmosphere_mode = atm.mode.value
            self._telemetry.atmosphere_haze_strength = atm.haze_strength
            self._telemetry.atmosphere_fog_strength = atm.fog_strength
            self._telemetry.atmosphere_rain_density = atm.rain_density
            self._telemetry.atmosphere_low_light_factor = atm.low_light_factor
            self._telemetry.active_disturbances.append("atmosphere")
        self._performance.atmosphere_ms = (time.perf_counter() - t0) * 1000.0

        # 6. Distractors
        t0 = time.perf_counter()
        if self._config.distractors.enabled:
            from fsoc_tracker.disturbances.optical import apply_distractors
            d = self._config.distractors
            rng = np.random.RandomState(
                self._config.master_seed + context.frame_index
            )
            result = apply_distractors(
                result, d.count, d.min_size_px, d.max_size_px,
                d.min_brightness, d.max_brightness,
                context.timestamp_s, d.move_speed_px_s, rng,
            )
            self._telemetry.active_disturbances.append("distractors")
        (time.perf_counter() - t0) * 1000.0

        # 7. Sensor noise
        t0 = time.perf_counter()
        if self._config.noise.enabled:
            result = apply_noise(result, self._config.noise, context)
            n = self._config.noise
            self._telemetry.noise_gaussian_sigma = n.gaussian_sigma
            self._telemetry.noise_salt_pepper_density = n.salt_pepper_density
            self._telemetry.noise_poisson_enabled = n.poisson_enabled
            self._telemetry.active_disturbances.append("noise")
        self._performance.noise_ms = (time.perf_counter() - t0) * 1000.0

        self._performance.total_ms = (time.perf_counter() - t_total) * 1000.0

        return result

    def should_suppress_target(self, timestamp_s: float) -> bool:
        """Check if target should be suppressed this frame (source-layer).

        Called by VirtualSimulationSource before rendering targets.
        Disappearance is TEMPORAL: once triggered, the target stays
        suppressed for a duration drawn from
        [min_duration_s, max_duration_s]. Uses deterministic RNG based on
        config seed + trigger timestamp, so runs are reproducible.
        """
        cfg = self._config.target_disappearance
        if not cfg.enabled or cfg.probability_per_frame <= 0:
            return False

        if (self._disappearance_until_s is not None
                and timestamp_s < self._disappearance_until_s):
            return True
        self._disappearance_until_s = None

        rng = np.random.RandomState(cfg.seed + int(timestamp_s * 1000))
        if rng.random() < cfg.probability_per_frame:
            duration = float(rng.uniform(cfg.min_duration_s,
                                         cfg.max_duration_s))
            self._disappearance_until_s = timestamp_s + duration
            return True
        return False
