# Deep Robustness Validation

This document records the evidence collected during the technical upgrade
pass. Results are internal measurements on macOS (Python 3.14.7, NumPy,
OpenCV, PySide6) and are not official SIH results.

## Baseline

The baseline was run with `configs/baseline.yaml` equivalent behavior:
640x480, 4x3 degree FOV, classical bright-spot perception, Kalman CV
tracking, PID control, 30 Hz simulation time, and the deterministic seed 42.

The 17-scenario internal suite completed before the verdict-integrity fix with
17/17 reported PASS. That report was not accepted as a trustworthy acceptance
result because scenarios without a loss event were incorrectly treated as
passing the reacquisition requirement.

Representative measured baseline values from the deterministic benchmark:

| Metric | Measured |
| --- | ---: |
| Frames | 150 |
| Processing FPS | 1577.5 |
| P95 processing latency | 0.88 ms |
| Tracking RMSE | N/A (no ground-truth provider) |
| Loss rate | 2.0% |
| Lock retention | 98.0% |

The high processing FPS is offline throughput, not a camera or GUI refresh
rate.

## Correction made during validation

The internal SIH-style suite previously computed loss as
`loss_events / frame_count` and considered `NOT_EVAL` reacquisition metrics a
passing result. Both behaviors could produce a false acceptance result.

The suite now:

- uses source-time locked/evaluable duration for loss and retention;
- reports P50/P90/P95/P99 tracking error;
- reports lock retention and reacquisition P95/max when evaluable;
- returns `NOT_EVAL` when a required metric cannot be measured;
- exits unsuccessfully only when an actual evaluated gate fails.

The corrected quick suite currently reports `NOT_EVAL` for clean scenarios
with no loss/reacquisition event. This is intentional and prevents an
unsupported reacquisition claim.

## Timing audit

Runtime tracking and benchmark timing use frame timestamps and measured
processing time. The remaining `1/30` values are explicit simulation/demo
defaults or test fixtures; they are not used as hidden frame-based loss,
velocity, or reacquisition timing.

## Current limitations

- The existing internal scenario suite does not inject controlled target loss,
  so reacquisition is not evaluable in those clean scenarios.
- The deterministic benchmark without a ground-truth provider cannot produce
  centroid RMSE or percentile error metrics.
- CPU and memory measurements have not been collected as part of the
  benchmark result model.
- AI, external-video, live-camera, and 30-minute stress matrices require
  dedicated fixtures and are not represented as completed evidence here.

Commands:

```bash
PYTHONHOME= .venv/bin/python -m fsoc_tracker.validation.sih_suite \
  --output runs/technical_upgrade/baseline
PYTHONHOME= .venv/bin/python -m fsoc_tracker.validation.sih_suite \
  --quick --output runs/technical_upgrade/after_suite
PYTHONHOME= .venv/bin/pytest -q
PYTHONHOME= .venv/bin/python -m fsoc_tracker --smoke
```
