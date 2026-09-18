# Release-Candidate Acceptance Report — FSOC Coarse Alignment Tracker v0.1.0

Date: 2026-09-16. Scope: acceptance only — no features added in this pass.
Method: full pytest, offscreen smoke, scripted 60-stage GUI demonstration
(real `MainWindow` + worker thread, offscreen), benchmark CLI matrix,
MP4 acceptance suite, CSV log analysis. Seed 42 unless noted.

## 1. Test execution

- `pytest --collect-only -q`: **1204 collected**
- `pytest -q`: **1202 passed, 2 skipped** (7m45s)
- `QT_QPA_PLATFORM=offscreen python -m fsoc_tracker --smoke`: **PASS**
  (150 frames, 371 FPS, acquisition 0.10 s, 0 loss events)
- Scripted human demonstration (`/tmp/rc_demo.py`, real GUI + thread):
  **60/60 stages PASS**, exit 0, window open at every checkpoint and at end
- Real GUI launched offscreen (`MainWindow.show()`); pages, buttons,
  worker thread start/stop, video/live modes all exercised without crash

## 2. Demonstration log (abridged)

SETUP → pages OK (5/5) → widgets OK (11/11) → config widgets OK (7/7) →
START → SEARCH → DETECT (centroid 245.7,256.0) → TRACK →
telemetry fresh (315→649 frames, 312.7 FPS, 0.8 ms) →
PREDICT (dx=0.40, dy=1.24) → CONTROL (pan=-5.00, tilt=-5.00) →
FOV hold (121px center offset) → GT flag off →
SELECT PRIMARY → LINK ALIVE (**LOCKED, err 0.14°**) →
DISTURBANCE moderate hot-load → TRACKING held, link LOCKED →
scene 9: TRACK → **LOST → SEARCH → REACQUIRE → LINK RESTORE** →
STOP → WORLD VIEW renders → MP4 TRACK (TRACKING, GT-free metadata) →
LIVE handled gracefully (no hardware, no crash) → window open at end.

Defect checks: no projection errors, no QPainter errors, no segfaults,
no thread errors, no freeze, telemetry advances every tick, no fake
values (all readouts traced to `ApplicationViewState`), no fake AI
(`expert_only`, learned gated), no GT leakage (sim flag off, video
metadata scanned), no broken buttons (START/STOP/nav/scene all driven).

## 3. PS reference metrics — measured by scenario (kalman_expert, seed 42)

| Scenario | Acq (≤2 s) | Err (≤10 px) | Loss (<5%) | Reacq (≤1 s) | FPS (≥20) |
|---|---|---|---|---|---|
| scene 1 nominal, 200f | 0.10 ✓ | 0.20 ✓ | 1.5% ✓ (0 ev) | N/A (no event) | 309 ✓ |
| scene 5 multi-beacon, 200f | 0.10 ✓ | **10.95 ✗** | 1.5% ✓ | N/A | 163 ✓ |
| scene 6 distractors, 200f | 0.10 ✓ | **33.15 ✗** | **15.0% ✗** (13 ev) | **0.069 ✓** | 95 ✓ |
| scene 9 loss, 200f | 0.10 ✓ | 0.88 ✓ | 1.5% ✓ | N/A | 300 ✓ |
| scene 9 loss, 2000f | 0.10 ✓ | 0.30 ✓ | 0.1% ✓ | N/A (see §5) | 292 ✓ |
| classical_pid s1, 200f | 0.00* | 0.18 ✓ | **53% ✗** (1 ev) | N/A | 461 ✓ |
| full_ai_mission s1, 200f | 0.10 ✓ | 0.24 ✓ | 1.0% ✓ | N/A | 320 ✓ |
| app smoke | 0.10 ✓ | sub-px | 0 ev | — | 371 ✓ |
| E2E stress (outage+noise) | 0.10 ✓ | 108 overall† | 11–14 ev† | **0.42 mean ✓** | harness‡ |
| GUI demo live s1 | TRACKING | LOCKED 0.14° | 0 | — | 312 ✓ |
| GUI demo live s9 | TRACKING | restored | LOST→reacq observed | observed | — |
| MP4 acceptance 25fps | det 100% | 0.19 centroid | 97% tracking | — | 361 ✓ |

\* classical_pid "0.000 s" is a first-frame-detection artifact of the raw
(no-Kalman) method, not a real acquisition measurement.
† E2E RMSE/loss dominated by the scripted 60-frame blackout +
distractor crossings; nominal pre-outage phase is LOCKED/sub-px.
‡ E2E harness runs as-fast-as-possible; FPS target applies to the
real-time worker/benchmark paths, all ≥95 FPS.

**Verdict: targets are met on nominal scenes, NOT universally.**
Above-target cases (multi-beacon RMSE, distractor-field loss/RMSE,
raw-method lock retention) are reported as measured. No universal
satisfaction is claimed.

## 4. Component status

- Simulation: WORKING
- Camera: WORKING
- Perception: WORKING
- Centroiding: WORKING
- Tracking: WORKING
- Prediction: PARTIAL (CV production; GRU experimental/quarantined)
- Situation: WORKING (rules production; learned stale/quarantined)
- Failure: PARTIAL (artifact trained, not loaded; runtime heuristic)
- Search: WORKING
- ROI: WORKING
- Control: WORKING
- AI: PARTIAL (expert production; learned clone gated; advisory-only)
- MP4: WORKING
- Live: PARTIAL (graceful offline handling verified; no hardware validation)
- Disturbances: PARTIAL (14 effects + hot-reload verified; disappearance
  duration fields unhonored — single-frame Bernoulli; see §5)
- Optical Link: WORKING
- Communication: WORKING
- 3D World: WORKING
- GUI: WORKING
- Benchmark: WORKING
- Logging: WORKING
- Packaging: PARTIAL (v0.1.0, `--gui`/`--smoke` verified, dist/ builds;
  no installer/platform-matrix validation)

## 5. Known limitations (carried, not release-blocking)

1. Equal-brightness multi-beacon association can hijack (scene 5 RMSE
   10.95 px; GUI run once locked a distractor at −11.5°). Mitigated in
   E2E via brightness separation; production scenes should separate
   beacon brightness or spacing.
2. `target_disappearance` ignores `min/max_duration_s` (single-frame
   Bernoulli, `disturbances/pipeline.py:299`): scene-9 benchmark yields
   no sustained loss; reacquisition timing comes from scene 6 (0.069 s)
   and E2E (0.42 s mean) instead.
3. GRU temporal model, visual CNN, disturbance MLPs, failure predictor:
   trained but quarantined/unwired (see `docs/ai/final-audit.md`).
4. Learned policy/situation accuracies are teacher-mimicry, not outcome
   metrics (see `docs/ai/final-audit.md`).
5. Live mode validated only for graceful degradation (no camera
   hardware in this pass); monocular range correctly reports N/A.

## 6. Freeze

Repository frozen at this report. No architectural changes after this
point unless a release-blocking bug is discovered. Allowed: release
paperwork, packaging, and fixes for release-blockers only.
