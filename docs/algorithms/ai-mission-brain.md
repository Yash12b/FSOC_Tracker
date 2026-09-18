# AI Mission Brain

The project now has a modular, bounded mission-brain interface around the
deterministic beacon perception, Kalman tracking, search, and PID control
layers.

## Runtime contract

`ObservationFeatures` contains only runtime-observable values:

- detector confidence and candidate count;
- residual and Kalman uncertainty;
- velocity;
- distance from image center;
- time since detection;
- source/processing rates and latency.

Ground-truth positions, simulator target state, and disturbance labels are
not accepted by the mission-brain API.

`SituationClassifier` produces an explainable situation class. `ExpertPolicy`
maps that class to a high-level recommendation such as `USE_ROI`,
`RUN_HYBRID`, `LOCAL_SEARCH`, or `REACQUIRE`. `SafetyEnvelope` validates the
recommendation and provides deterministic actuator-rate clamps.

This expert policy is the baseline for future supervised policy learning. It
is intentionally not described as a trained model. The existing heatmap CNN
remains an optional perception backend and must be benchmarked against the
classical detector before being selected.

## Trainable models

The NumPy-only models in `fsoc_tracker.ai.learned` provide an actual
project-specific supervised baseline without making PyTorch a runtime
dependency:

```bash
PYTHONHOME= .venv/bin/python -m fsoc_tracker.ai.train_models \
  --output artifacts/models/mission-v1 --samples 4000 --seed 42
```

This produces versioned motion, situation, and policy artifacts plus an
experiment manifest. The generated data contains observable features only;
expert labels are used as training targets, not runtime inputs. The trained
models are optional and must be compared with the deterministic expert policy
on a held-out scenario split before enabling them as a production default. The
manifest records independent validation and test seeds and their measured
accuracy/RMSE; the current artifacts are evidence of a lightweight baseline,
not proof of superiority or generalization to physical video.

## Explainability and resource bounds

`DecisionLogger` writes compact JSONL records and enforces a maximum record
count. Full tensors and images are never logged. Stale observations fall back
to `HOLD`, invalid confidence values are rejected, and pan/tilt rates are
clamped to configured limits.

## Training boundary

The simulator may generate labels for offline training and evaluation, but
those labels must not enter `ObservationFeatures` or runtime policy
decisions. Any learned predictor must be compared with the constant-velocity
Kalman baseline for centroid error, reacquisition, latency, CPU, and memory
before it can become a production default.
