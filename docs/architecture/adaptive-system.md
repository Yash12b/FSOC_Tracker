# Adaptive System Architecture — Stage 13

## Overview

Stage 13 transforms the baseline perception-tracking-control pipeline into an
intelligent, adaptive system that responds to changing visual conditions,
uncertainty, target behavior, and camera pointing state.

## Architecture Diagram

```
                       FRAME
                         |
                         v
                 QUALITY ANALYZER
                   (quality.py)
                         |
                         v
             +-----------+-----------+
             |                       |
             v                       v
        FULL FRAME                ROI MODE
             |                       |
             +-----------+-----------+
                         |
                         v
                  PERCEPTION FUSION
                  /       |        \
                 /        |         \
          Classical      AI       Temporal
             CV                    priors
                 \        |         /
                  \       |         /
                   v      v      v
                    Detection
                         |
                         v
                UNCERTAINTY ESTIMATION
                  (uncertainty.py)
                         |
                         v
                  TEMPORAL TRACKER
                    + ADAPTIVE KALMAN
                    + MANEUVER DETECTION
                         |
                         v
                 LOCK QUALITY SCORE
                         |
             +-----------+-----------+
             |                       |
             v                       v
          TRACKING            SEARCH/REACQUIRE
             |                  (search.py)
             +-----------+-----------+
                         |
                         v
               ADAPTIVE CONTROLLER
                 + GAIN SCHEDULING
                 + FEED-FORWARD
                 + ANTI-OSCILLATION
                         |
                         v
                   VIRTUAL CAMERA
                         |
                         v
                      FRAME
```

## Module Map

| Module | File | Purpose |
|--------|------|---------|
| Quality Analyzer | `perception/quality.py` | Image quality metrics + classification |
| Uncertainty Estimator | `perception/uncertainty.py` | Multi-source uncertainty estimation |
| Perception Policy | `perception/policy.py` | Strategy selection (ROI/full-frame/search) |
| Fusion Engine | `perception/fusion.py` | Classical+AI+tracker evidence fusion |
| Centroid Refiner | `perception/refinement.py` | Coarse-to-fine subpixel refinement |
| Adaptive Kalman | `tracking/adaptive_kalman.py` | Q/R scaling based on conditions |
| Maneuver Detector | `tracking/maneuver.py` | Motion classification (smooth/maneuvering/unpredictable) |
| Search Controller | `tracking/search.py` | Intelligent search + reacquisition |
| Lock Quality | `tracking/lock_quality.py` | Multi-factor lock quality score |
| Adaptive Controller | `control/adaptive.py` | Gain scheduling + feed-forward + anti-oscillation |
| PID Tuning | `control/tuning.py` | Offline parameter sweep + multi-objective |
| Advanced Config | `advanced/__init__.py` | Master configuration for all features |
| Diagnostics | `advanced/diagnostics.py` | Explainable decision events |

## Feature Flags

Every feature is independently switchable for ablation:

```yaml
advanced:
  quality_analysis:
    enabled: true
  adaptive_perception:
    enabled: true
  confidence_fusion:
    enabled: true
  uncertainty:
    enabled: true
  adaptive_kalman:
    enabled: true
  maneuver_detection:
    enabled: true
  coarse_to_fine:
    enabled: true
  search:
    enabled: true
  adaptive_controller:
    enabled: true
  gain_scheduling:
    enabled: true
  feed_forward:
    enabled: true
```

## Quality Levels

| Level | Meaning | Perception Response |
|-------|---------|-------------------|
| EXCELLENT | High contrast, low noise, good brightness | Standard pipeline |
| GOOD | Minor degradation | Standard pipeline |
| DEGRADED | Noticeable issues | Adaptive threshold + denoising |
| POOR | Significant degradation | Enhanced denoising + caution |
| CRITICAL | Severe degradation | Minimal processing + fallback |

## Uncertainty Levels

| Level | Position Uncertainty | Response |
|-------|---------------------|----------|
| VERY_LOW | < 5 px | Tight ROI, high trust |
| LOW | 5-15 px | Standard ROI |
| MODERATE | 15-30 px | Wider ROI |
| HIGH | 30-50 px | Wide ROI, reduce control |
| VERY_HIGH | > 50 px | Maximum ROI, enter search |

## Search Progression

```
PREDICTED_REGION (50px radius, projected position)
    -> timeout ->
EXPANDED_REGION (150px, last known position)
    -> timeout ->
LAST_KNOWN_DIRECTION (projected along velocity)
    -> timeout ->
STRUCTURED_SEARCH (spiral/raster pattern)
    -> timeout ->
FULL_FRAME (complete image scan)
```

## Controller Adaptation

| Error Range | KP Scale | KD Scale | Behavior |
|-------------|----------|----------|----------|
| < 5 px | 0.7x | 0.5x | Reduced gains near center |
| 5-20 px | 1.0x | 1.0x | Normal operation |
| > 20 px | 1.5x | 1.5x | Faster response |

Feed-forward: `ff = velocity * gain / (image_size / 2)`

Anti-oscillation: Detects sign changes in error, reduces gains by 0.6x when oscillation detected.
