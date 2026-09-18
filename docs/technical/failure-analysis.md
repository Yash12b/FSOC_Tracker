# Failure Analysis

## Initial target behind the camera

- **Scenario:** GUI simulation with an empty straight-line trajectory
  configuration.
- **Symptom:** The global view showed a target while the camera feed remained
  empty and the tracker stayed in `SEARCHING`.
- **Root cause:** The trajectory constructor defaults were `(0, 0, 0)`,
  while the camera was at the world center looking along positive Z.
- **Fix:** The GUI supplies a centered, forward-facing default trajectory
  (`x=world_width/2`, `y=world_height/2`, `z=100`) only when no explicit
  parameters are provided.
- **Verification:** GUI regression coverage and headless runtime reproduction.
- **Residual risk:** User-provided trajectory parameters remain authoritative
  and can intentionally place a target outside the camera view.

## No autonomous initial search

- **Scenario:** Target begins outside the camera FOV.
- **Symptom:** `SEARCHING` produced zero pan/tilt commands.
- **Root cause:** `CoarsePointingController` mapped `SEARCHING` directly to
  `DISABLED`; the GUI worker did not invoke the separate search module.
- **Fix:** Added an explicit configurable open-loop search command for
  `SEARCHING`, while retaining `LOST` prediction behavior.
- **Verification:** Controller tests and outside-FOV worker reproduction confirm
  non-zero camera movement.
- **Residual risk:** Open-loop search requires an adequate pan/tilt envelope;
  no claim of universal reacquisition performance is made.

## False SIH-suite acceptance

- **Scenario:** Clean suite with no target-loss event.
- **Symptom:** Reacquisition was absent but the scenario was reported `PASS`.
- **Root cause:** `NOT_EVAL` was included in the suite's pass condition, and
  loss was calculated from event count rather than source-time lock duration.
- **Fix:** Suite now reports `NOT_EVAL` for unmeasured gates and uses the
  pipeline's source-time lock/evaluable durations.
- **Verification:** New verdict-integrity regression test and corrected quick
  suite output.
- **Residual risk:** A dedicated controlled-loss fixture is still needed to
  measure reacquisition time.
