# Technical Report — AI-Based Virtual Camera Tracking System for Coarse Alignment of Mobile FSOC Terminals

## 1. Problem understanding

Free-space optical communication uses highly directional beams: a small
angular error breaks the link. Before fine pointing can engage, a coarse
alignment stage must observe the environment, acquire the remote beacon,
estimate its motion, steer the pointing direction to keep it visible, and
recover after loss. Real-hardware development is expensive; this project
is a software virtual laboratory for that coarse-alignment (PAT) loop:
world/scene generation is the test harness, the camera image is the
observation, and perception/tracking/control is the product.

Reference operating point: 640×480 monochrome camera, 4°×3° FOV,
30 Hz update, 5°/s pan/tilt limits. Performance targets: acquisition
≤ 2 s, tracking error ≤ 10 px, loss < 5%, reacquisition ≤ 1 s,
processing ≥ 20 FPS. All reported numbers in §8 are measured, with
scenario, method, seed, and frame count attached.

## 2. System architecture

```
SIMULATION / MP4 VIDEO / LIVE CAMERA
        │ (FrameSource → Frame: image, timestamp, dims, metadata)
        ▼
PREPROCESSING (noise-gated median denoise, background estimation)
        ▼
PERCEPTION → BEACON DETECTION → CENTROIDING (intensity-weighted)
        ▼
TRACKER (Kalman, constant-velocity motion, dt from timestamps)
        ▼
PREDICTION (constant-velocity production; GRU experimental)
        ▼
SITUATION / FAILURE RISK → POLICY/BRAIN → SAFETY → PAN/TILT CONTROL
        ▼
CAMERA / VIEWPORT ──→ NEXT FRAME (closed loop)
```

The information boundary is absolute: world truth flows only into
rendering, offline label generation, and benchmark scoring. Runtime
perception/tracking/AI/control receive image pixels, timestamps, and
own-history state only. Frame metadata carries no ground truth in any
production path (verified by unit, integration, and acceptance tests,
including a guarded-annotation MP4 test whose runtime raises on any
ground-truth access).

## 3. Software modules

- **Simulation** (`simulation/`): engine, 15 scenes, 11 trajectory types
  (straight/circular/figure-8/random/spiral/sinusoidal/random-walk/
  stop-go/sudden-reversal/accel-decel/user-controlled), square-beacon
  sensor renderer with PSF deposit, authoritative camera model
  (resolution, FOV, pose, intrinsics, projection), optical-link and
  communication engines.
- **Frame sources** (`pipeline/sources.py`): `VirtualSimulationSource`,
  `VideoSource` (decoder timestamps, arbitrary dims/rates, seek),
  `LiveSource` (availability probing, graceful errors),
  `LiveViewportSource` (digital PTZ when no hardware PTZ exists),
  `EquirectangularFrameSource` (360° viewport extraction).
- **Perception** (`perception/`): classical bright-spot detector
  (preprocess → candidates → features → intensity-weighted centroid
  with NaN/Inf and zero-weight fallbacks), adaptive ROI with
  FULL_FRAME fallback, candidate scoring.
- **Tracking** (`tracking/`): 2D Kalman filter (Joseph-form update,
  residual/Mahalanobis gating), track-state machine
  (NO_TRACK→SEARCHING→ACQUIRING→TRACKING→LOST→REACQUIRING), search
  controller (local/uncertainty/predictive/spiral/sweep), dt strictly
  from timestamps.
- **Control** (`control/`): PID with deadband, integral clamp,
  filtered derivative, output saturation + anti-windup, NaN/Inf guards;
  actuator applies rate-limited camera updates.
- **AI** (`ai/`): rule-based situation classifier (10 categories),
  expert policy (production), ridge-multinomial learned policy
  (behavioral clone, label-gated), motion predictor with configurable
  horizon, ridge failure-risk predictor (trained weights loaded at
  runtime), safety envelope + safety gate.
- **Disturbances** (`disturbances/`): 14 effect types across
  image/camera/source layers, severity presets, temporal target
  disappearance with configured durations, scene-attached shorthand
  mapped from PS-anchored values.
- **GUI** (`gui/`): camera-first workspace with prediction/uncertainty
  overlays, 3D setup world, five layout presets, floating panels,
  AI/link/telemetry/event panels, benchmark panel, mission flow strip.
- **Benchmark** (`benchmark/`, `cli/`): five methods with honest
  NOT AVAILABLE gating, per-scenario JSON+CSV logs, multi-seed
  mean/std aggregation, repro commands.

## 4. Tracking methods

Production estimation is classical: intensity-weighted centroiding
(0.19 px mean error on noisy 30 fps video), Kalman filtering with
constant-velocity motion (audited 4.51 px RMSE vs 35.16 px for the
experimental GRU on the same thin protocol — the baseline wins and
stays). A raw-detection (no-filter) method is benchmarked to prove the
filter's value (53% loss vs ~1% with Kalman on the nominal scene).
LAST_POSITION/CV/KALMAN comparisons are preserved in evaluation code.

## 5. AI methods

Situation classification and policy are deterministic rules on
observable features (production). The learned policy distills the
expert (≈98.9% mimicry accuracy — a distillation score, not an outcome
claim) and loads only after exact 11-label validation. Failure risk
comes from trained ridge weights on sliding observation windows.
The temporal GRU, visual CNN, and disturbance MLPs are trained but
quarantined by measured evidence (see `docs/ai/final-audit.md` for the
per-model audit). Every ML component carries a provenance label
(trained / random / imported / deterministic_baseline).

## 6. Test methodology

1215 unit/integration tests; flagship 29-step end-to-end regression
(multi-beacon setup, misaligned start, outage blackout, search/ROI,
reacquisition, link restore — all image-driven); MP4 acceptance suite
with guarded annotations (14 tests incl. the 30 fps noisy reference);
determinism checks (repeat runs identical); static guards against
simulation imports in runtime paths; live scripted GUI demonstration
(60/60 stages, real window + worker thread).

## 7. Performance analysis

kalman_expert, seed 42, 200 frames: scene 1 — acq 0.10 s, RMSE
0.20 px, loss 1.5%, 309 FPS; scene 9 (temporal outages) — 3 loss
events, reacquisition mean 1.07 s, RMSE 0.84 px; scene 5
multi-beacon — RMSE 10.95 px (above target); scene 6 distractor field —
RMSE 33–425 px with glints applied, loss 15–95% (association limit,
openly reported); full_ai_mission scene 1 — RMSE 0.24 px, loss 1.0%,
320 FPS. MP4 640×480@30 fps noisy: 100% detection, 0.37 px centroid
error, 361 FPS processing. GUI live: 312 FPS, link LOCKED at 0.14°.
Targets are met on nominal scenes; stress scenes exceed error/loss
targets and are reported as such — no universal claim is made.

## 8. Limitations and future improvements

Equal-brightness multi-target association can hijack (needs appearance
signatures or joint probabilistic association); camera pan has rate
but no range stops; benchmark uses single seeds unless `--seeds` is
passed; live hardware unvalidated; GRU/visual models need larger,
more diverse datasets to challenge the classical baseline honestly;
five GUI layouts share page widgets (combinations, not bespoke
compositions); tech evaluation of fine-pointing handoff is out of
scope (coarse alignment only).
