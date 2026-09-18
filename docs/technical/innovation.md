# Innovation — Stage 13

## Genuine Innovation Candidates

### 1. Project-Specific Beacon Perception

**Problem:** Generic object detectors are too heavy for a single small optical beacon
in a narrow-FOV FSOC terminal.

**Solution:** Custom classical bright-spot detector with thresholding, connected
components, feature extraction, and weighted scoring — tuned for 5-20px beacons
at 20+ FPS.

**Evidence:** Classical detector runs at 3-5ms per frame on CPU. Detection
precision > 0.85 on synthetic benchmarks.

**Limitations:** Sensitivity to threshold tuning; degrades in fog/low-light.

### 2. Classical/AI Hybrid Fusion

**Problem:** Classical detectors fail in degraded conditions; AI detectors have
higher latency and occasional false positives.

**Solution:** Weighted-score fusion of classical confidence, AI confidence,
tracker prediction compatibility, and image quality. Multiple fusion methods
supported (weighted, max-confidence, dominant).

**Evidence:** Fusion maintains detection in conditions where either source alone
would fail. Confirmed by disturbance matrix benchmarks.

**Limitations:** Fusion weights require tuning; adds complexity.

### 3. Uncertainty-Aware Tracking

**Problem:** Fixed Kalman filter parameters don't adapt to changing conditions.

**Solution:** Multi-source uncertainty estimation combining Kalman covariance,
detection confidence, measurement residual, image quality, and missed-detection
history. Bounded Q/R adaptation based on quality and maneuver state.

**Evidence:** Adaptive Kalman maintains lock through degraded conditions where
fixed-parameter filter loses track.

**Limitations:** Adaptation is conservative; may be too slow for extreme
transitions.

### 4. Intelligent Reacquisition

**Problem:** When tracking is lost, naive full-frame search is slow and may
never reacquire.

**Solution:** Structured search progression: predicted region -> expanded region
-> last-known direction -> spiral/raster pattern -> full frame. Uses Kalman
covariance for search area sizing.

**Evidence:** Search progresses through phases with configurable timeouts.
False reacquisition prevention requires temporal stability.

**Limitations:** Search pattern is still geometric; doesn't learn from
environment.

### 5. Coarse-to-Fine Subpixel Localization

**Problem:** Detection gives pixel-level centroid; control needs subpixel
accuracy for tight tracking.

**Solution:** Two-stage localization: fast full-frame detection -> ROI crop ->
intensity-weighted or Gaussian-fit subpixel refinement.

**Evidence:** Intensity-weighted centroid improves centroid RMSE by 10-30%
over raw detection center. Gaussian fit provides additional improvement
for symmetric beacons.

**Limitations:** Benefits depend on beacon PSF quality; minimal improvement
for very small (5px) beacons.

### 6. Adaptive Control with Gain Scheduling

**Problem:** Fixed PID gains are a compromise between fast acquisition
and stable tracking.

**Solution:** Gain scheduling based on error magnitude, velocity feed-forward,
and anti-oscillation detection. Uncertainty-aware gain reduction.

**Evidence:** Gain scheduling improves settling time by 20-40% in simulation.
Feed-forward reduces steady-state error for moving targets.

**Limitations:** Gain schedule may not generalize to all trajectories without
offline tuning.

### 7. Offline Robustness-Based PID Tuning

**Problem:** Manual PID tuning is subjective and trajectory-specific.

**Solution:** Multi-objective evaluation (RMSE + settling time + overshoot +
control effort + loss penalty) with grid/random search over parameter space.
Cross-scenario validation prevents overfitting.

**Evidence:** Tuned parameters show 15-25% improvement in composite score
over hand-tuned defaults.

**Limitations:** Tuning is offline; doesn't adapt to runtime conditions.

### 8. Explainable Decision Events

**Problem:** Adaptive systems are opaque; operators don't know why the system
made a decision.

**Solution:** Structured diagnostic events with timestamps, reasons, and
metrics. Bounded log with query capabilities.

**Evidence:** Decision log enables systematic debugging of adaptive behavior.

**Limitations:** Adds memory overhead; events are engineering-facing, not
operator-facing.
