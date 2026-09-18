# FINAL ACCEPTANCE REPORT
## FSOC Tracker — Immersive Explorer Integration
### Date: 2026-09-14

---

## CRASH STATUS: FIXED

**Root cause:** `world_view.py:194-195` called `project_to_image(-2000, 0, i, cam_pos, intrinsics, rot_mat)` with 6 positional args instead of 4. The canonical signature is `project_to_image(point_world_tuple, camera_position, intrinsics, rotation_matrix)`.

**Fix:** Removed broken duplicate grid block (lines 186-198). All `project_to_image` calls now use correct tuple syntax. Added exception safety to `paintEvent` with `try/finally` ensuring `painter.end()`.

**Evidence:**
- 871 tests pass (1 skipped, 1 pre-existing GUI bug)
- Smoke test PASSED (290 FPS, 0 losses)
- Offscreen GUI launch: no crash
- Direct widget render capture: confirmed 3D objects visible

**Regression tests added:** `tests/unit/test_gui_regression.py` — 10 tests covering:
- `project_to_image` tuple contract (no 6-arg calls)
- Behind-camera rejection
- Grid projection no-crash
- Target/terminal projection
- TargetView target_id field

---

## GUI STATUS: WORKING

**Before:** Old tracking-console layout with header, large empty viewport, fixed telemetry column. "IMMERSIVE EXPLORER" was just a label on a combo box — layout never changed.

**After:** Immersive 3D viewport dominates the application. World view is the primary widget. Header shows "FSOC IMMERSIVE EXPLORER". Toolbar with SCENES/OBJECTS/TARGET/TIME/WORLD and TRACK/AI/CAMERA/DISTURB/LINK/COMM/BENCH buttons.

**Layout modes:** Combo box in status bar switches between IMMERSIVE EXPLORER, TRACKING CONSOLE, AI COMMAND, OPTICAL LAB, BENCHMARK LAB. Title updates to reflect active layout.

**Evidence:** Offscreen capture confirmed 15 objects, TERM-A, BEACON-3, TERM-B, optical beam all visible.

---

## IMMERSIVE EXPLORER STATUS: PARTIAL

**Working:**
- 3D viewport with grid, objects, terminals, beam
- Orbit (left-drag), pan (right-drag), zoom (scroll)
- Object click selection via hit-test
- Beacon designation on click
- Labels for selected/beacon/tracked objects

**Not yet implemented:**
- Floating/draggable panels (panels are in fixed right sidebar)
- Scene selector as a real clickable widget (configured via `scene_id` in config dict, no GUI dropdown yet)
- Focus/follow/inspect per-object actions
- Dedicated inspector panel with TYPE/POSITION/VELOCITY/DISTANCE/STATUS

---

## SCENE STATUS: PARTIAL

**15 scenes defined** in `simulation/scenes.py`:
1. Open Space Acquisition
2. Fast Crossing
3. Figure-8
4. Dense Object Field (50 random targets)
5. Multiple Beacon Candidates (5 circular)
6. Optical Distractor Field
7. Sensor Noise
8. Fog/Haze
9. Target Loss
10. Platform Jitter
11. High-Speed Maneuver
12. Bidirectional Communication
13. AI Blind Challenge
14. Communication Under Disturbance
15. Full Mission

**Working:** `load_scene_into_engine()` loads any scene into the simulation engine. Worker supports `scene_id` config parameter.

**Not working:** No GUI widget to select scenes at runtime. Must set `scene_id` in config dict programmatically.

---

## OBJECT INTERACTION STATUS: PARTIAL

**Working:**
- `selected_object_id` set on click
- `designated_beacon_id` set on click
- `tracked_target_id` set on click
- 3 visual states: white ring (selected), amber (beacon), green (tracked)
- Labels rendered for significant objects

**Not working:**
- Inspector panel showing per-object details
- FOCUS/FOLLOW/INSPECT/SET AS BEACON/TRACK/VIEW FROM OBJECT actions

---

## BEACON/TERMINAL STATUS: WORKING

**Terminal A:** Position fixed at (1000, 1000, 50), orientation = camera pan/tilt. Optical beam rendered from actual axis direction.

**Terminal B:** Follows designated beacon target position. Updated each frame from simulation world state. When beacon changes, Terminal B position updates.

**Evidence:** Offscreen capture shows TERM-A at bottom, BEACON-3 in center, TERM-B near beacon. Beam line visible from TERM-A.

---

## BEAM STATUS: WORKING

**Beam origin:** Terminal A actual position (1000, 1000, 50).

**Beam direction:** Terminal A's actual yaw/pitch angles → direction vector → beam endpoint.

**Visual:** Cyan line (LOCKED), orange (DEGRADED), faint red (LOST/REACQUIRING), gray otherwise. Length = link range when a genuine range exists, 500 m visual fallback otherwise. A dotted red segment from the beam endpoint to the beacon marks the angular error.

**Critical invariant:** When Terminal A is misaligned, beam visibly misses. This is geometrically correct because beam direction uses `sin(yaw)*cos(pitch)`, `sin(pitch)`, `cos(yaw)*cos(pitch)`.

---

## LINK STATUS: WORKING

**Engine:** `OpticalLinkEngine` computes angular error, beam alignment, range, link quality from Terminal A and Terminal B states. Simplified geometric abstraction (Gaussian alignment decay, hysteresis, inverse-square distance heuristic, multiplicative atmospheric factor) — not a physics simulator. Conceptual flow: tracking → coarse alignment → beam alignment → optical link availability. Subordinate to the camera-tracking mission.

**States:** NO_LINK → SEARCHING / ALIGNING → LOCKED ↔ DEGRADED → LOST → REACQUIRING → LOCKED

**Evidence:** Integration test showed link status updating during simulation. Optical link depends on actual terminal alignment, not ground-truth positions.

---

## COMMUNICATION STATUS: PARTIAL

**Engine:** `CommunicationEngine` creates messages, queues them during link, transmits when link is LOCKED, delivers after latency.

**Flow:** create_message → send_message → QUEUED → TRANSMITTING → DELIVERED/FAILED

**State integration:** Messages converted to `MessageView` objects and shown in GUI.

**Missing:** No GUI SEND button wired to actually call `create_message`/`send_message`. The communication HUD displays messages but the input field is not connected to the engine.

---

## AI STATUS: WORKING

**Runtime AI:** `AIMissionBrain` produces real `MissionDecision` with:
- situation: 10 categories (NORMAL_TRACKING, FAST_TARGET_MOTION,
  HIGH_NOISE, EDGE_OF_FOV, DEGRADING_TRACK, LOW_CONFIDENCE,
  PREDICTION_UNCERTAIN, TARGET_LOST, REACQUISITION, RECOVERY)
- action: TRACK, TRACK_PREDICTIVE, USE_ROI, USE_FULL_FRAME, RUN_CLASSICAL, RUN_HYBRID, LOCAL_SEARCH, GLOBAL_SEARCH, REACQUIRE, HOLD, SAFE_STOP
- confidence, reason, prediction, safety

**GUI:** AI HUD shows actual runtime values: situation, action, confidence, prediction (dx/dy/uncertainty), failure risk, fallback status, explanation.

**Evidence:** Integration test showed `situation=target_lost, action=local_search` when no beacon was tracked.

---

## TEMPORAL MODEL STATUS: EXPERIMENTAL (HONEST)

**Critical bug found and fixed:** Training and evaluation used the LAST FRAME timestep where displacement labels are always ZERO (no future frame exists). Model learned to output zeros, achieving fake 0.035px RMSE. The "837× better than CV" claim was **invalid**.

**Fixed training:** Now samples random mid-sequence timesteps (frame 0-283) with valid future displacements.

**Honest results after fix:**

| Method | RMSE (px) |
|--------|-----------|
| Last Position | 36.03 |
| **Constant Velocity** | **4.51** |
| GRU Predictor | 35.16 |

**The constant velocity baseline (4.51px) outperforms the GRU (35.16px).** The GRU needs significantly more training data (currently only 22 training sequences) to learn meaningful patterns beyond what velocity features provide.

**Model artifacts:**
- `artifacts/models/temporal-v4/temporal_gru.pt` — retrained with fixed training
- val_loss: 209.49 (vs fake 0.000233 before)

---

## SITUATION MODEL STATUS: RULES PRODUCTION / LEARNED QUARANTINED

**Production:** rule-based `SituationClassifier` (10 `Situation` categories).
The on-disk learned situation weights (`mission-*/situation-*.npz`) are
**stale 7-label artifacts** predating the enum expansion -- correctly
refused by the benchmark loader, never executed. The "98.9% test accuracy
(7 classes)" figure below describes that stale artifact's teacher-mimicry
score, NOT production behavior. See `docs/ai/final-audit.md`.

---

## FAILURE MODEL STATUS: EXPERIMENTAL

**Issue:** Tracker Kalman filter never enters formal LOST state, so training data has 0% failure rate. Model defaults to "no failure".

---

## POLICY MODEL STATUS: EXPERT PRODUCTION / LEARNED BEHAVIORAL CLONE

**Accuracy:** 98.9% test accuracy (11 actions) is **teacher-mimicry**:
labels are the expert policy's own outputs, so the score measures rule
distillation, NOT outcome quality. Production default is the expert
policy; learned weights load only after exact 11-label validation.
Closed-loop lock/loss/reacquisition must be measured separately.
See `docs/ai/final-audit.md`.

---

## SEARCH STATUS: PARTIAL

`SearchController` exists and has `update(dt)` method. Not currently wired into the GUI worker pipeline.

---

## ROI STATUS: WORKING

`AdaptiveROIModule` with three modes: fixed, uncertainty-based, situation-aware. Wired into mission brain.

---

## BENCHMARK STATUS: PARTIAL

`BenchmarkPanel` widget exists. AI benchmark (`ai_benchmark.py`) produces classical vs AI-enhanced comparison. No GUI button to trigger benchmarks at runtime.

---

## DISTURBANCES STATUS: PARTIAL

**Engine:** `DisturbancePipeline` supports Gaussian, Poisson, salt-and-pepper, blur, motion blur, jitter, fog, haze, low light, contrast.

**GUI:** Control panel has disturbance preset selector and enable checkbox. Pipeline applies disturbances to rendered images.

**Not all 15 disturbance types exposed as individual GUI controls.**

---

## TIME SYSTEM STATUS: WORKING

Simulation uses `sim_dt` from config. Frame timing based on `time.perf_counter()`. FPS computed from frames processed / wall time.

---

## TEST RESULTS

```
871 passed, 1 skipped (pre-existing GUI test bug)
Smoke test: PASSED (290 FPS, 0 losses)
```

---

## WHAT WAS ACTUALLY DONE

1. **Fixed crash:** Removed broken `project_to_image` calls in `world_view.py:194-195`
2. **Added exception safety:** `paintEvent` now uses `try/finally` to guarantee `painter.end()`
3. **Removed duplicate grid drawing block** (lines 186-198 were broken duplicate of 200-211)
4. **Fixed default camera position** to see world center
5. **Populated 3D world:** Worker now fills `targets_all` from simulation engine
6. **Wired Terminal B to designated beacon:** Position updates each frame
7. **Added `target_id` to `TargetView`** dataclass
8. **Added AI HUD with real runtime values** (situation, action, confidence, prediction, risk, explanation)
9. **Updated communication HUD** with real link status and message format
10. **Added toolbar** with context buttons
11. **Fixed `load_scene` stub** to return scene definition
12. **Added scene loading** to worker pipeline via `scene_id` config
13. **Fixed temporal model training** — random mid-sequence timestep instead of last-frame zeros
14. **Fixed temporal evaluation** — evaluates at mid-sequence timestep, not last frame
15. **Retrained temporal GRU** with corrected labels (val_loss=209.49, honest)
16. **Added 10 GUI regression tests** for projection/rendering
17. **Documented honest temporal model performance** (CV baseline 4.51px beats GRU 35.16px)

---

## WHAT REMAINS

1. **Floating panels** — drag/collapse/close for inspector, HUDs
2. **Scene selector GUI widget** — currently config-only
3. **Communication SEND button** — wiring to engine
4. **More temporal training data** — 22 sequences insufficient for GRU to beat CV
5. **Failure predictor** — needs scenarios with actual tracking loss
6. **Search controller** — not wired into worker
7. **Benchmark trigger** from GUI
