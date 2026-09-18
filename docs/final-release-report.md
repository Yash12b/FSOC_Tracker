# Final Release Report — FSOC Coarse-Alignment Tracker v0.1.0 (spec pass, frozen)

Basis: official SIH PS PDF (Problem Statement 4, ISRO/DoS). Every claim
below carries its measurement. Snapshot:
`/Users/yashas/Downloads/fsoc_snapshots/post_spec_pass.tgz`.

## 1. CURRENT TEST COUNT — 1242 passed, 2 skipped

## 2. SMOKE — PASS (150f, 367 FPS; packaged arm64 binary: 383 FPS)

## 3. GUI — 60/60 scripted demo + 12/12 reverify, 121 widget tests
Five layout presets (IMMERSIVE EXPLORER / TRACKING CONSOLE / AI COMMAND /
OPTICAL LAB / BENCHMARK LAB) applied live without restart; four floating
dock panels (AI/LINK/TELEMETRY/EVENTS); mission flow strip; prediction
overlay; CONTROL group; angular-error + FOV telemetry; AI mission-model
row; event JSONL/CSV export. Zero QPainter/thread/segfault errors.

## 4. SIMULATION — 15 scenes, 11 trajectories, terminal placement wired
User-controlled beacon (WASD/arrows/STOP/RESET/RANDOM) through engine
trajectories, AI-blind verified live (250 px shift via images only).

## 5. ACQUISITION — 0.10 s everywhere measured (target ≤ 2 s)

## 6. TRACKING (kalman_expert, seed 42, 200f)
s1: 0.20/98.5% · s8 fog: 0.32/98.5% · s10 jitter: 3.59/98.5% ·
s9 temporal: genuine events, reacq ~1.07–1.17 s · s5: 10.95/98.5%
(above target) · s7 noise: 28.29/66.5% · s6 glint-field: 425/5%.
Association experiment: Mahalanobis default improves scene 6 to
30.77 px/14.5% but regresses clean lock-rate tests (0.7→0.56), so
NEAREST stays default and Mahalanobis ships as `--assoc-method`
with the measured trade-off documented. Dense identical-decoy
identity remains a structural limit (needs appearance signatures).

## 7. PREDICTION
Constant-velocity production, horizon configurable 0.025–0.5 s
(GUI/worker/brain). GRU: real v5 retrain (temporal-v3, 150-epoch
budget, seed 123, early-stop 14, val 214.4) scores 35.72 px vs CV
4.51 px on held-out test — correctly NOT promoted. Visual v2 trained
for real (3000 samples) but loses 100× to classical — withheld with
versioned receipt. GRU-bigger-data costed (~9 h), not faked.

## 8. TARGET LOSS — temporal 0.5–2.0 s windows (PS §23), deterministic,
seed-controlled; scene dicts wired into benchmark + worker.

## 9. REACQUISITION — s9: 1.067 single / 1.167±0.141 multi-seed
(target ≤1 s marginal); s6: 0.069–0.267; E2E blackout 0.42 mean.

## 10. MP4 — 14/14 acceptance incl. 640×480@30 fps 10% S&P case
(100% detection, 0.37 px; was 57 px before noise-gated median denoise,
no regressions). Decoder-first timestamps unified on both video
sources; arbitrary dims/rates; GT-free; seek verified.

## 11. LIVE — digital-PTZ viewport (FOV-consistent, mock-tested:
pan-shift/clamp/timestamp unit tests); graceful no-camera handling;
distance N/A. PARTIAL: zero video devices in this environment
(verified) — no hardware validation possible here.

## 12. DISTURBANCES — 14 effects, presets, hot-reload, scene shorthand
auto-apply (noise/fog/jitter/distractors/disappearance, PS-anchored),
temporal windows, per-frame pose+image application in benchmarks.

## 13. BENCHMARK — 5 methods, NOT AVAILABLE gating, JSON+CSV+repro,
NEW multi-seed aggregation, NEW association-tuning flags.

## 14. PACKAGING — WORKING: PyInstaller arm64 bundle builds and passes
smoke standalone. Deliverables: app ✓ source ✓ manual ✓ tech report
(new `docs/technical-report.md`) ✓ demo video
(`artifacts/demo/demo_tracking.mp4`, scripted real run) ✓
performance log ✓ event logs ✓.

## 15. MODELS — per `docs/ai/final-audit.md` (+v2/v5 addenda)
CV/expert/rules production; learned policy gated clone; failure
predictor NOW LOADED (live risk/ROI/model-status in AI panel);
GRU-v5, visual-v2, disturbance MLPs trained-but-quarantined with
measured reasons; BeaconCNN random. No superiority claims.

## 16. LIMITATIONS
Glint-field identity (see §6); pan rate-capped but range-unlimited;
worker unthrottled (metrics use sim time); live HW absent here;
pre-pass RC1 tarball lost to /tmp purge (post-pass snapshot kept).

## Classification
WORKING (20): Simulation, Camera, Perception, Centroiding, Situation,
Failure, Search, ROI, Control, AI, MP4, Disturbances, Optical Link,
Communication, 3D World, GUI, Benchmark, Logging, Packaging,
Layouts/Floating (under GUI).
PARTIAL (3): Tracking (glint-field identity), Prediction (learned
experimental by evidence), Live (no hardware in environment).
EXPERIMENTAL quarantined (4): GRU, visual CNNs, BeaconCNN,
disturbance MLPs — each with measured promotion criteria unmet.
NOT IMPLEMENTED (3): live-hardware PTZ validation (environmental),
fine-pointing handoff (out of scope per PS — coarse alignment only),
optional demo-video narration (silent MP4 artifact shipped).
BROKEN: none.

## Freeze
Repository frozen. No architectural changes unless a release-blocking
bug is discovered.
