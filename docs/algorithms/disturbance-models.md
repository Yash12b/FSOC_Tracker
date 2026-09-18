# Disturbance Models

## Overview

The disturbance engine provides controlled environmental and sensor degradation for the FSOC tracker. All models are **lightweight image-space approximations** — they are not physically accurate atmospheric or sensor physics models.

## Categories

### A. Sensor/Image Noise
Affects pixel intensity values (post-render).

| Model | Formula | Parameters |
|-------|---------|------------|
| Gaussian | `I_noisy = I + N(0, σ²)` | `gaussian_sigma` |
| Salt-and-Pepper | Random replacement with min/max | `salt_pepper_density` |
| Poisson | Poisson sampling of scaled intensities | `poisson_scale` |

Order: Gaussian → Poisson → Salt-and-Pepper

### B. Atmospheric Effects
Affects image quality, contrast, visibility (post-render).

| Model | Formula | Parameters |
|-------|---------|------------|
| Haze | `I_out = T·I + (1-T)·A` | `haze_strength`, `haze_atmospheric_intensity` |
| Fog | `I_out = T·I + (1-T)·A` | `fog_strength`, `fog_atmospheric_intensity` |
| Rain | Streak overlay | `rain_density`, `rain_streak_length`, `rain_brightness` |
| Low Light | `I_out = contrast·(brightness·I)^γ` | `low_light_factor`, `low_light_contrast`, `low_light_gamma` |

Order: Haze → Fog → Rain → Low Light

### C. Motion/Geometric Disturbances
Affects camera/platform pose (pre-render).

| Model | Description | Parameters |
|-------|-------------|------------|
| Camera Jitter | High-frequency pointing disturbance | `amplitude_px`, `frequency_hz`, `model` |
| Platform Motion | Lower-frequency platform drift | `amplitude_x_px`, `amplitude_y_px`, `speed`, `type` |

### D. Optical Turbulence
Spatially varying displacement field (post-render warp).

| Model | Description | Parameters |
|-------|-------------|------------|
| Turbulence | Sinusoidal displacement field | `strength`, `spatial_scale`, `temporal_frequency` |

## Mathematical Models

### Haze/Fog (Atmospheric Scattering)

```
I_out = T(d) · I_in + (1 - T(d)) · A
```

Where:
- `T(d) = 1 - strength` is the transmission factor
- `A` is the atmospheric/background light intensity
- `strength` ∈ [0, 1]: 0 = clear, 1 = fully opaque

This is a simplified single-scattering model. It does NOT account for:
- Depth-dependent transmission
- Multiple scattering
- Wavelength-dependent attenuation
- Sky light polarization

### Poisson Noise (Simplified)

```
λ = I / max_val · scale · 100
I_out = Poisson(λ) / (scale · 100) · max_val
```

This is a simplified shot-noise approximation. It does NOT model:
- Quantum efficiency
- Dark current
- Read noise
- Full photon-counting statistics

### Camera Jitter Models

| Model | Formula |
|-------|---------|
| Bounded | `offset ∈ [-A, +A]` uniform random |
| Gaussian | `offset ~ N(0, (A/3)²)`, clipped to `±A` |
| Sinusoidal | `offset = A · sin(2πft)` |
| Damped Vibration | `offset = A · e^(-αt) · sin(2πft)` |

### Platform Motion Models

| Type | Formula |
|------|---------|
| Linear | `x = A · sin(2πst)`, `y = A · sin(2πst)` |
| Circular | `x = Aₓ · sin(ωt)`, `y = A_y · cos(ωt)` |
| Figure-8 | `x = Aₓ · sin(ωt)`, `y = A_y · sin(2ωt)` |
| Spiral | `x = A · phase · cos(ωt)`, `y = A · phase · sin(ωt)` |
| Random | Sum of 3 sine waves with random phases |

### Turbulence

```
x' = x + Σᵢ Aᵢ · sin(fᵢ · x + ω·t + φᵢ)
y' = y + Σᵢ Aᵢ · sin(fᵢ · y + ω·t + φᵢ)
```

Where:
- `Aᵢ = strength / N` (amplitude per basis function)
- `fᵢ = 2π/spatial_scale · random_multiplier`
- `ω = 2π·temporal_frequency`
- `φᵢ` random phase offsets

This produces smooth, spatially correlated displacement fields.

## Deterministic Randomness

Every stochastic disturbance uses a dedicated `np.random.Generator` seeded with:
```
seed = config_seed + frame_index * DOMAIN_CONSTANT
```

Domain constants:
- Noise: 1000
- Atmosphere: 2000
- Jitter: 3000
- Platform: 4000
- Turbulence: 5000

This ensures:
1. Same seed + same timestamps = identical output
2. Different domains don't affect each other's random streams
3. Changing frame index produces different but reproducible noise

## Pre-Render vs Post-Render

### Pre-Render (Modifies Camera Pose)
- Camera jitter → angular offset
- Platform motion → angular offset

These produce an `EffectiveCameraPose` used by the sensor renderer.

### Post-Render (Modifies Image)
- Turbulence warp
- Atmospheric effects (haze, fog, rain, low light)
- Sensor noise (Gaussian, Poisson, salt-and-pepper)

## Limitations

1. **No depth-dependent fog**: Fog strength is global, not distance-based
2. **No physical rain rendering**: Rain is overlay streaks, not 3D particles
3. **No wavelength effects**: All models are grayscale/intensity-only
4. **Approximate turbulence**: Sinusoidal basis, not Kolmogorov statistics
5. **No detector physics**: Poisson model is simplified, not full CCD/CMOS model

These simplifications are documented for scientific honesty. The purpose is algorithm development and benchmarking, not physical simulation.
