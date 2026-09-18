# Final Release Report — FSOC Coarse-Alignment Tracker v0.1.0 (renovation pass, frozen)

Follow-up to `docs/final-release-report.md`. This pass executed the
architectural audit's renovation plan: EvalSink migration triage,
single-pipeline cutover, search/camera-drive fixes, AI consolidation.
All claims below carry measurements from this session.

## 1. CURRENT TEST COUNT — 1282 passed, 2 skipped

## 2. SMOKE — PASS (packaged binary verified previously; source smoke
unchanged in behavior)

## 3. GUI — 10/10 scripted demo (real window + worker thread)
TRACKING acquired on a random world, search moves camera across a wide
span (pans −26°…−23° observed), MP4 TRACKING, live no-crash, window
open throughout. Zero QPainter/thread/segfault errors.

## 4. SIMULATION — 15 scenes fully removed (`scenes.py` deleted)
Generic `world_builder` + `ScenarioConfig` + engine IDs/monotonic
counter is the only world API. Benchmarks use generated
`--world` profiles (`nominal|multi|distractor|loss|noise|fog|jitter`).

## 5. ACQUISITION — 0.10 s nominal; random-world acquisition demonstrated
live (<4 s wall on an edge-of-FOV primary).

## 6. TRACKING (kalman_expert, seed 42, 200f)
nominal: 0.19px/98.5% · loss-world: genuine events, reacq
1.167±0.141s · multi: ~11px · distractor-field: association-limited
(nearest-neighbor default kept; Mahalanobis ships as `--assoc-method`
after measuring 425→31px with a clean-lock trade-off documented).

## 7. PREDICTION — CV production, horizon configurable
GRU v5 retrained for real (35.72px vs CV 4.51px) — correctly withheld.

## 8. TARGET LOSS — temporal 0.5–2.0 s windows, deterministic, seeded.

## 9. REACQUISITION — ≤1 s marginal on torture scene (1.167 s),
0.069 s distractor, 0.42 s E2E blackout. Per-scenario only.

## 10. MP4 — 14/14 incl. 640×480@30 fps noisy (0.37 px centroid).

## 11. LIVE — viewport + mock-tested + graceful; no hardware in env.

## 12. DISTURBANCES — 14 effects, presets, hot-reload, scene/world
attach, temporal windows.

## 13. BENCHMARK — 5 gated methods, JSON+CSV+repro, multi-seed stats.

## 14. PACKAGING — WORKING (arm64 bundle + smoke verified).

## 15. MODELS — CV/expert/rules production; learned policy gated clone;
failure predictor loaded with live risk/ROI/model-status; GRU-v5,
visual-v2, disturbance MLPs trained-but-quarantined with measured
reasons; BeaconCNN random; `AIIntegration` deleted (unwirable
contract), `SafetyGate`/types kept; beacon_ai range fabrication
deleted (None/N/A).

## 16. LIMITATIONS
Dense identical-decoy identity (needs appearance signatures);
pan rate-capped, range-unlimited; worker unthrottled (metrics use sim
time); live hardware absent; narrated demo video not produced
(silent MP4 artifact exists).

## Bugs fixed this pass (all with regression tests)
1. Video/live NameError (`fi`/`ts`): every video/live frame died
   mid-update — view state froze at NO_TRACK.
2. Search expiry parked the camera (COMPLETE + zero rates after 5 s):
   sweep now recycles.
3. Search-override commands carried DISABLED mode: actuator dropped
   every search motion — camera static during SEARCHING.
4. Search waypoints were image-anchored (±2° around pan=0): beacons
   outside that band were unfindable; waypoints are now origin-relative
   with a ±30° global raster.
5. Terminal-A HUD overwrote live pose with (1000,1000,50) every frame.

## Component classification
WORKING (19): Simulation, Camera, Perception, Centroiding, Situation,
Failure, Search, ROI, Control, AI, MP4, Disturbances, Optical Link,
Communication, 3D World, GUI, Benchmark, Logging, Packaging.
PARTIAL (3): Tracking (glint-field identity), Prediction (learned
experimental by evidence), Live (no hardware in environment).
EXPERIMENTAL quarantined (4): GRU, visual CNNs, BeaconCNN,
disturbance MLPs.
NOT IMPLEMENTED (3): live-hardware PTZ validation, fine-pointing
(out of scope per PS), narrated demo video.
BROKEN: none.

## Freeze
Repository frozen at snapshot
`/Users/yashas/Downloads/fsoc_snapshots/post_search_fix.tgz`.
No architectural changes unless a release-blocking bug is discovered.
