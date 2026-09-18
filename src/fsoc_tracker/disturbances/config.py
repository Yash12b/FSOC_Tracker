"""Disturbance configuration.

Strongly typed Pydantic models for all disturbance parameters.
All values are validated and have sensible defaults.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AtmosphereMode(str, Enum):
    CLEAR = "clear"
    HAZE = "haze"
    FOG = "fog"
    RAIN = "rain"
    LOW_LIGHT = "low_light"


class PlatformMotionType(str, Enum):
    NONE = "none"
    LINEAR = "linear"
    CIRCULAR = "circular"
    FIGURE_EIGHT = "figure_eight"
    SPIRAL = "spiral"
    RANDOM = "random"


class JitterModel(str, Enum):
    BOUNDED = "bounded"
    GAUSSIAN = "gaussian"
    SINUSOIDAL = "sinusoidal"
    DAMPED_VIBRATION = "damped_vibration"


class DisturbanceMode(str, Enum):
    OFF = "off"
    CLEAR = "clear"
    LIGHT = "light"
    MODERATE = "moderate"
    SEVERE = "severe"
    EXTREME = "extreme"


class NoiseConfig(BaseModel):
    """Configuration for sensor/image noise disturbances."""

    enabled: bool = False
    gaussian_sigma: float = Field(default=0.0, ge=0.0, le=100.0,
        description="Standard deviation of additive Gaussian noise (intensity units)")
    salt_pepper_density: float = Field(default=0.0, ge=0.0, le=1.0,
        description="Fraction of pixels replaced by min/max intensity")
    poisson_scale: float = Field(default=1.0, ge=0.0, le=10.0,
        description="Scaling factor for Poisson noise (higher = more noise)")
    poisson_enabled: bool = False
    seed: int = 42


class AtmosphereConfig(BaseModel):
    """Configuration for atmospheric degradation effects."""

    enabled: bool = False
    mode: AtmosphereMode = AtmosphereMode.CLEAR

    haze_strength: float = Field(default=0.0, ge=0.0, le=1.0,
        description="Haze transmission reduction (0=clear, 1=fully opaque)")
    haze_atmospheric_intensity: float = Field(default=200.0, ge=0.0, le=255.0,
        description="Atmospheric light intensity for haze model")

    fog_strength: float = Field(default=0.0, ge=0.0, le=1.0,
        description="Fog transmission reduction (0=clear, 1=fully opaque)")
    fog_atmospheric_intensity: float = Field(default=220.0, ge=0.0, le=255.0,
        description="Atmospheric light intensity for fog model")

    rain_density: float = Field(default=0.0, ge=0.0, le=1.0,
        description="Rain streak density (0=none, 1=dense)")
    rain_streak_length: int = Field(default=15, ge=3, le=50,
        description="Length of rain streaks in pixels")
    rain_streak_angle_deg: float = Field(default=80.0,
        description="Angle of rain streaks from horizontal")
    rain_brightness: float = Field(default=200.0, ge=0.0, le=255.0,
        description="Brightness of rain streaks")
    rain_opacity: float = Field(default=0.4, ge=0.0, le=1.0,
        description="Opacity of rain streaks")

    low_light_factor: float = Field(default=1.0, ge=0.0, le=2.0,
        description="Brightness multiplier (1.0=normal, <1 darker)")
    low_light_contrast: float = Field(default=1.0, ge=0.0, le=2.0,
        description="Contrast multiplier")
    low_light_gamma: float = Field(default=1.0, ge=0.1, le=5.0,
        description="Gamma correction (<1 brighten shadows, >1 darken)")

    seed: int = 42


class JitterConfig(BaseModel):
    """Configuration for camera jitter (geometric, pre-render)."""

    enabled: bool = False
    model: JitterModel = JitterModel.BOUNDED

    amplitude_px: float = Field(default=5.0, ge=0.0, le=100.0,
        description="Maximum pixel displacement amplitude")
    frequency_hz: float = Field(default=10.0, ge=0.1, le=200.0,
        description="Oscillation frequency for sinusoidal/damped models")
    damping: float = Field(default=0.1, ge=0.0, le=10.0,
        description="Damping factor for damped_vibration model")

    seed: int = 42


class PlatformMotionConfig(BaseModel):
    """Configuration for platform motion (geometric, pre-render)."""

    enabled: bool = False
    type: PlatformMotionType = PlatformMotionType.LINEAR

    amplitude_x_px: float = Field(default=10.0, ge=0.0, le=200.0,
        description="Platform motion amplitude in X (pixels)")
    amplitude_y_px: float = Field(default=10.0, ge=0.0, le=200.0,
        description="Platform motion amplitude in Y (pixels)")
    speed: float = Field(default=1.0, ge=0.0, le=100.0,
        description="Platform motion speed (cycles/sec for periodic, px/s for linear)")

    seed: int = 42


class TurbulenceConfig(BaseModel):
    """Configuration for optical turbulence approximation."""

    enabled: bool = False

    strength: float = Field(default=0.0, ge=0.0, le=10.0,
        description="Turbulence displacement amplitude (pixels)")
    spatial_scale: float = Field(default=50.0, ge=1.0, le=500.0,
        description="Spatial correlation scale (pixels)")
    temporal_frequency: float = Field(default=2.0, ge=0.1, le=50.0,
        description="Temporal oscillation frequency (Hz)")

    seed: int = 42


class BlurConfig(BaseModel):
    """Configuration for Gaussian blur (image-layer)."""

    enabled: bool = False
    kernel_size: int = Field(default=5, ge=1, le=51,
        description="Gaussian kernel size (must be odd)")
    sigma: float = Field(default=1.0, ge=0.1, le=20.0,
        description="Gaussian standard deviation")


class MotionBlurConfig(BaseModel):
    """Configuration for directional motion blur (image-layer)."""

    enabled: bool = False
    kernel_size: int = Field(default=15, ge=3, le=51,
        description="Motion blur kernel length (must be odd)")
    angle_deg: float = Field(default=0.0, ge=0.0, le=360.0,
        description="Motion blur direction angle (degrees from horizontal)")


class BrightnessContrastConfig(BaseModel):
    """Configuration for brightness/contrast/gamma adjustment (image-layer)."""

    enabled: bool = False
    brightness: float = Field(default=1.0, ge=0.0, le=3.0,
        description="Brightness multiplier (1.0=normal, <1 darker, >1 brighter)")
    contrast: float = Field(default=1.0, ge=0.0, le=3.0,
        description="Contrast multiplier (1.0=normal)")
    gamma: float = Field(default=1.0, ge=0.1, le=5.0,
        description="Gamma correction (<1 brighten shadows, >1 darken)")


class TargetDisappearanceConfig(BaseModel):
    """Configuration for target disappearance (source-layer).

    Target is not rendered when disappearance is active.
    """

    enabled: bool = False
    probability_per_frame: float = Field(default=0.0, ge=0.0, le=1.0,
        description="Probability of disappearance each frame")
    min_duration_s: float = Field(default=0.5, ge=0.0, le=10.0,
        description="Minimum disappearance duration (seconds)")
    max_duration_s: float = Field(default=3.0, ge=0.1, le=30.0,
        description="Maximum disappearance duration (seconds)")
    seed: int = 42


class DistractorConfig(BaseModel):
    """Configuration for false target distractors (image-layer)."""

    enabled: bool = False
    count: int = Field(default=3, ge=0, le=20,
        description="Number of distractor spots")
    min_size_px: float = Field(default=3.0, ge=1.0, le=30.0,
        description="Minimum distractor radius (pixels)")
    max_size_px: float = Field(default=12.0, ge=2.0, le=50.0,
        description="Maximum distractor radius (pixels)")
    min_brightness: float = Field(default=150.0, ge=0.0, le=255.0,
        description="Minimum distractor intensity")
    max_brightness: float = Field(default=255.0, ge=0.0, le=255.0,
        description="Maximum distractor intensity")
    move_speed_px_s: float = Field(default=20.0, ge=0.0, le=200.0,
        description="Distractor movement speed (pixels/sec)")
    seed: int = 42


class DisturbanceConfig(BaseModel):
    """Master disturbance configuration.

    Contains all configurable disturbance parameters organized by domain.
    """

    enabled: bool = False
    profile: str = "clear"

    noise: NoiseConfig = Field(default_factory=NoiseConfig)
    atmosphere: AtmosphereConfig = Field(default_factory=AtmosphereConfig)
    jitter: JitterConfig = Field(default_factory=JitterConfig)
    platform_motion: PlatformMotionConfig = Field(default_factory=PlatformMotionConfig)
    turbulence: TurbulenceConfig = Field(default_factory=TurbulenceConfig)
    blur: BlurConfig = Field(default_factory=BlurConfig)
    motion_blur: MotionBlurConfig = Field(default_factory=MotionBlurConfig)
    brightness_contrast: BrightnessContrastConfig = Field(default_factory=BrightnessContrastConfig)
    target_disappearance: TargetDisappearanceConfig = Field(default_factory=TargetDisappearanceConfig)
    distractors: DistractorConfig = Field(default_factory=DistractorConfig)

    master_seed: int = 42


def apply_world_disturbances(
    cfg: DisturbanceConfig,
    world_disturbances: dict | None,
    seed: int | None = None,
) -> DisturbanceConfig:
    """Merge world-attached disturbance shorthand into a pipeline config.

    World dicts use PS-anchored values: ``noise``/``fog`` are fractions of
    their PS maxima (20 px noise std, opaque atmosphere), ``jitter_px``
    and platform values are absolute pixels, flags enable defaults::

        {"distractors": True}   -> transient optical glints on
        {"noise": 0.5}          -> Gaussian sigma 10 px + S&P 5%
        {"fog": 0.8}            -> fog transmission cut 80%
        {"jitter_px": 5.0}      -> +/-5 px camera jitter
        {"target_disappearance": True} -> temporal outages
            (moderate-preset rate/durations when the world gives none)

    Unknown keys are ignored. Mutates and returns ``cfg``; sets the
    top-level ``enabled`` flag whenever anything is enabled (the
    pipeline early-exits while it is False).
    """
    d = world_disturbances or {}
    touched = False

    if d.get("distractors"):
        cfg.distractors.enabled = True
        touched = True
    if "noise" in d:
        v = max(0.0, min(1.0, float(d["noise"])))
        cfg.noise.enabled = True
        cfg.noise.gaussian_sigma = 20.0 * v
        cfg.noise.salt_pepper_density = 0.10 * v
        touched = True
    if "fog" in d:
        v = max(0.0, min(1.0, float(d["fog"])))
        cfg.atmosphere.enabled = True
        cfg.atmosphere.mode = AtmosphereMode.FOG
        cfg.atmosphere.fog_strength = v
        touched = True
    if "jitter_px" in d:
        cfg.jitter.enabled = True
        cfg.jitter.amplitude_px = max(0.0, float(d["jitter_px"]))
        touched = True
    if d.get("target_disappearance"):
        cfg.target_disappearance.enabled = True
        if cfg.target_disappearance.probability_per_frame <= 0:
            cfg.target_disappearance.probability_per_frame = 0.01
            cfg.target_disappearance.min_duration_s = 0.5
            cfg.target_disappearance.max_duration_s = 2.0
        if seed is not None:
            cfg.target_disappearance.seed = int(seed)
        touched = True

    if touched:
        cfg.enabled = True
    return cfg


def get_preset_config(mode: DisturbanceMode) -> DisturbanceConfig:
    """Get a disturbance configuration for a severity preset.

    Args:
        mode: Severity level preset.

    Returns:
        DisturbanceConfig with appropriate parameter values.
    """
    profile_name = mode.value if isinstance(mode, DisturbanceMode) else str(mode or "clear")

    if mode == DisturbanceMode.OFF:
        return DisturbanceConfig(enabled=False, profile=profile_name)

    if mode == DisturbanceMode.CLEAR:
        return DisturbanceConfig(
            enabled=True,
            profile=profile_name,
            atmosphere=AtmosphereConfig(enabled=True, mode=AtmosphereMode.CLEAR),
        )

    if mode == DisturbanceMode.LIGHT:
        return DisturbanceConfig(
            enabled=True,
            profile=profile_name,
            noise=NoiseConfig(enabled=True, gaussian_sigma=2.0, salt_pepper_density=0.02),
            atmosphere=AtmosphereConfig(
                enabled=True, mode=AtmosphereMode.HAZE,
                haze_strength=0.15,
            ),
            jitter=JitterConfig(enabled=True, amplitude_px=2.0),
            blur=BlurConfig(enabled=True, kernel_size=3, sigma=0.5),
            brightness_contrast=BrightnessContrastConfig(enabled=True, brightness=0.9),
        )

    if mode == DisturbanceMode.MODERATE:
        return DisturbanceConfig(
            enabled=True,
            profile=profile_name,
            noise=NoiseConfig(enabled=True, gaussian_sigma=5.0, salt_pepper_density=0.05),
            atmosphere=AtmosphereConfig(
                enabled=True, mode=AtmosphereMode.FOG,
                fog_strength=0.3,
                haze_strength=0.2,
                low_light_factor=0.8,
            ),
            jitter=JitterConfig(enabled=True, amplitude_px=5.0, frequency_hz=15.0),
            platform_motion=PlatformMotionConfig(
                enabled=True, type=PlatformMotionType.LINEAR,
                amplitude_x_px=5.0, amplitude_y_px=3.0,
            ),
            blur=BlurConfig(enabled=True, kernel_size=5, sigma=1.0),
            motion_blur=MotionBlurConfig(enabled=True, kernel_size=7, angle_deg=45.0),
            brightness_contrast=BrightnessContrastConfig(enabled=True, brightness=0.7, contrast=0.9),
            distractors=DistractorConfig(enabled=True, count=2, min_size_px=4, max_size_px=8),
        )

    if mode == DisturbanceMode.SEVERE:
        return DisturbanceConfig(
            enabled=True,
            profile=profile_name,
            noise=NoiseConfig(enabled=True, gaussian_sigma=10.0, salt_pepper_density=0.10,
                              poisson_enabled=True, poisson_scale=2.0),
            atmosphere=AtmosphereConfig(
                enabled=True, mode=AtmosphereMode.FOG,
                fog_strength=0.5,
                haze_strength=0.3,
                rain_density=0.3,
                low_light_factor=0.7,
            ),
            jitter=JitterConfig(enabled=True, amplitude_px=10.0, frequency_hz=20.0),
            platform_motion=PlatformMotionConfig(
                enabled=True, type=PlatformMotionType.CIRCULAR,
                amplitude_x_px=10.0, amplitude_y_px=8.0, speed=0.5,
            ),
            turbulence=TurbulenceConfig(enabled=True, strength=2.0, spatial_scale=80.0),
            blur=BlurConfig(enabled=True, kernel_size=7, sigma=2.0),
            motion_blur=MotionBlurConfig(enabled=True, kernel_size=11, angle_deg=30.0),
            brightness_contrast=BrightnessContrastConfig(enabled=True, brightness=0.5, contrast=0.7, gamma=1.3),
            target_disappearance=TargetDisappearanceConfig(
                enabled=True, probability_per_frame=0.01, min_duration_s=0.5, max_duration_s=2.0,
            ),
            distractors=DistractorConfig(enabled=True, count=4, min_size_px=5, max_size_px=15),
        )

    # EXTREME
    return DisturbanceConfig(
        enabled=True,
        profile=profile_name,
        noise=NoiseConfig(enabled=True, gaussian_sigma=20.0, salt_pepper_density=0.15,
                          poisson_enabled=True, poisson_scale=4.0),
        atmosphere=AtmosphereConfig(
            enabled=True, mode=AtmosphereMode.FOG,
            fog_strength=0.7,
            haze_strength=0.5,
            rain_density=0.6,
            low_light_factor=0.4,
            low_light_gamma=1.5,
        ),
        jitter=JitterConfig(enabled=True, amplitude_px=20.0, frequency_hz=30.0),
        platform_motion=PlatformMotionConfig(
            enabled=True, type=PlatformMotionType.RANDOM,
            amplitude_x_px=20.0, amplitude_y_px=20.0, speed=2.0,
        ),
        turbulence=TurbulenceConfig(enabled=True, strength=5.0, spatial_scale=40.0),
        blur=BlurConfig(enabled=True, kernel_size=11, sigma=4.0),
        motion_blur=MotionBlurConfig(enabled=True, kernel_size=21, angle_deg=60.0),
        brightness_contrast=BrightnessContrastConfig(enabled=True, brightness=0.3, contrast=0.5, gamma=2.0),
        target_disappearance=TargetDisappearanceConfig(
            enabled=True, probability_per_frame=0.03, min_duration_s=0.3, max_duration_s=5.0,
        ),
        distractors=DistractorConfig(enabled=True, count=8, min_size_px=6, max_size_px=25, move_speed_px_s=50.0),
    )
