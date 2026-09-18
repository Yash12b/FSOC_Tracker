# Final Release Report — FSOC Coarse-Alignment Tracker v0.1.0 (post-spec pass)

Basis: official SIH PS PDF (Problem Statement 4, ISRO/DoS). RC1 preserved
(`/Users/yashas/Downloads/fsoc_snapshots/` holds the post-pass snapshot;
pre-pass RC1 tarball was lost to a /tmp purge — recorded here honestly).
No features claimed without measured evidence below.

## 1. CURRENT TEST COUNT
1215 passed, 2 skipped (`pytest -q`, 4m50s). Was 1202/2 at RC1; +13 new
(temporal disappearance, user-beacon/terminal wiring, telemetry/event/AI
panel, PS Benchmark-2 video).

## 2. SMOKE RESULT
`python -m fsoc_tracker --smoke`: PASS — 150 frames, 367 FPS,
acquisition 0.10 s, 0 loss events.

## 3. GUI RESULT
Real `MainWindow` + worker thread, offscreen: RC demo 60/60 stages PASS
(pre-pass tree); post-pass reverify 11/12 (scene 9 link-restore needed a
longer window than the script's 40 s — a follow-up probe showed full
recovery to LOCKED at 0.07°). Flow strip, CONTROL group, prediction
overlay, telemetry/event/AI additions all unit-tested (109 GUI tests).
Zero QPainter/thread/segfault errors in every run.

## 4. SIMULATION RESULT
15/15 scenes load; 11 trajectory types (all 4 PS-mandatory + spiral,
sinusoidal, random_walk, stop_go, sudden_reversal, accel_decel,
user_controlled); per-beacon independent params; Terminal A placeable
end-to-end (world view → worker camera); GT flag off at runtime.

## 5. ACQUISITION RESULT
0.10 s consistently (benchmarks, smoke, E2E first-frame detect, GUI
scene 1). Target ≤ 2 s: met on all measured scenarios.

## 6. TRACKING RESULT
kalman_expert RMSE: scene 1 0.20 px, scene 9 0.84–0.88 px,
scene 5 10.95 px, scene 6 33.15 px; full_ai_mission s1 0.24 px;
MP4 noisy-30fps centroid RMSE 0.42 px. Target ≤ 10 px: met except
multi-beacon (10.95) and distractor-field (33.15) scenes — reported,
not hidden.

## 7. PREDICTION RESULT
Constant-velocity production (audited 4.51 px RMSE, thin protocol);
GRU trained/experimental (35.16 px) quarantined. Live dx/dy verified
in GUI demo. Required horizons 25–500 ms implemented in predictor.

## 8. TARGET LOSS RESULT
Temporal disappearance implemented per PS §23 (0.5–2.0 s windows, was
single-frame Bernoulli). Scene 9 benchmark: 3 genuine loss events/200f;
E2E 60-frame blackout → LOST + search + ROI; GUI scene 9 LOST observed.

## 9. REACQUISITION RESULT
Scene 9 mean 1.067 s (target ≤ 1 s: marginal, n=3); scene 6 0.069 s;
E2E blackout mean 0.42 s. Reported per-scenario; no universal claim.

## 10. MP4 RESULT
Acceptance 14/14 incl. new PS case (640×480 @30 fps, 10% S&P + Gaussian):
100% detection, 0.37 px mean centroid error (was 57 px before enabling
the noise-gated median denoise). Decoder timestamps, arbitrary dims,
GT-free metadata, seek verified. Same perception/tracker as sim.

## 11. LIVE RESULT
Graceful no-camera handling verified (no crash, window stays open);
monocular distance N/A enforced. PARTIAL: no physical hardware or PTZ
validation in this pass; virtual viewport fallback stands.

## 12. DISTURBANCE RESULT
14 effect types; presets + hot-reload verified live; temporal windows
fixed; benchmark scene-dict disappearance now wired. Limitation:
scene-attached image-layer dicts (noise/fog/jitter values on scenes
7/8/10) are not auto-applied — presets cover the same effects.

## 13. BENCHMARK RESULT
5 methods with honest NOT AVAILABLE gating; per-scenario JSON+CSV auto
logs with repro commands; PS table in §3 of rc1 report, extended here.
Single-seed runs (multi-seed aggregation not implemented).

## 14. PACKAGING RESULT
v0.1.0; `--gui`/`--smoke` verified; PyInstaller spec present, dist/
builds; docs: user manual present, tech-report deliverable still a
stub. PARTIAL.

## 15. MODEL STATUS
Per `docs/ai/final-audit.md` (12 models): CV + expert policy + rules
production; learned policy gated clone; GRU/visual/disturbance/failure
trained-but-quarantined/unwired; BeaconCNN random. No superiority
claims; two code-provenance defects fixed in earlier pass.

## 16. KNOWN LIMITATIONS
1. Equal-brightness multi-beacon association can hijack (see §6).
2. Camera pan has no range stops (observed −56° windup; rates are
   safety-capped, range is not).
3. Worker runs unthrottled: sim time races wall time (metrics use
   sim timestamps correctly; wall-clock "search duration" reads long).
4. Scene image-layer disturbance dicts not auto-applied (§12).
5. Five GUI layouts: pages genuine, layout presets not implemented;
   floating panels unintegrated.
6. Tech-report deliverable is a stub; user manual exists.
7. Live hardware unvalidated; single-seed benchmarks.
8. `/tmp` purge destroyed the pre-pass RC1 tarball; post-pass snapshot
   retained at `/Users/yashas/Downloads/fsoc_snapshots/`.

## Component classification
WORKING: Simulation, Camera, Perception, Centroiding, Tracking,
Situation, Search, ROI, Control, MP4, Optical Link, Communication,
3D World, GUI, Benchmark, Logging.
PARTIAL: Prediction, Failure, AI, Live, Disturbances, Packaging.
EXPERIMENTAL: GRU predictor, visual CNN, BeaconCNN (random),
disturbance MLPs (all quarantined/unwired, documented).
NOT IMPLEMENTED: five layout presets, floating-panel integration,
tech-report deliverable, multi-seed aggregation, scene image-layer
auto-apply.
BROKEN: none known.
