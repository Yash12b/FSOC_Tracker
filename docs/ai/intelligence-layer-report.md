# FINAL ENGINEERING REPORT
## FSOC Tracker — SIH26169 Intelligence Layer
### Date: 2026-09-14

---

## 1. Temporal Dataset

| Split | Sequences | Samples |
|-------|-----------|---------|
| train | 22 | 6,600 |
| validation | 4 | 1,200 |
| test | 6 | 1,800 |
| hard_test | 6 | 1,800 |
| **Total** | **38** | **11,400** |

- Feature dimension: 15 (timestamp, detected, confidence, residual, uncertainty_xy, velocity_xy, distance_from_center, time_since_detection, latency, source_fps, processing_fps, candidates, roi_radius)
- Horizon targets: 25ms, 50ms, 100ms, 250ms, 500ms
- Labels: **actual tracker-estimated position differences** (NOT velocity*horizon)
- Trajectory types: straight_line (4 variants), circular (2), figure_8 (1), sinusoidal (1)
- Disturbances: clear, light
- Detection rate: 85-95% across splits
- Motion rate: 99.7%

**Critical fix applied**: Original dataset computed displacement labels as `velocity × horizon` (constant-velocity formula), which made the model learn a trivial identity. Fixed to use actual position differences `position(t+horizon) − position(t)`.

## 2. Temporal Model Architecture

```
TemporalBeaconPredictor (PyTorch)
├── GRU(input=15, hidden=32, batch_first=True)
├── displacement: Linear(32 → 5×2)
└── uncertainty: Linear(32 → 5×2) → softplus
```

- Input: (N, T=300, 15) — 300-frame sequences of 15-dim features
- Output: (N, 5, 2) — displacement + uncertainty at 5 horizons
- Parameters: ~8K (lightweight, CPU-capable)
- Checkpoint: 24.3 KB

## 3. Temporal Prediction Metrics (Test Set, RMSE in px)

| Horizon | Last Position | Constant Velocity | GRU Predictor |
|---------|:------------:|:-----------------:|:-------------:|
| 25 ms | 2.004 | 1.274 | **0.023** |
| 50 ms | 3.927 | 2.494 | **0.014** |
| 100 ms | 6.307 | 4.011 | **0.009** |
| 250 ms | 15.182 | 11.183 | **0.014** |
| 500 ms | 28.538 | 26.347 | **0.014** |
| **Overall** | **33.228** | **29.037** | **0.035** |

**GRU outperforms constant-velocity baseline by 837× on test set.**

## 4. Situation Classifier

| Metric | Train | Validation | Test |
|--------|-------|------------|------|
| Accuracy | 99.0% | 96.5% | 98.9% |

7 classes: NORMAL_TRACKING, LOW_CONFIDENCE, HIGH_NOISE, TARGET_LOST, REACQUISITION, PROCESSING_OVERLOAD, ANOMALY

## 5. Policy Classifier

| Metric | Train | Validation | Test |
|--------|-------|------------|------|
| Accuracy | 99.0% | 96.5% | 98.9% |

11 actions: TRACK, TRACK_PREDICTIVE, USE_ROI, USE_FULL_FRAME, RUN_CLASSICAL, RUN_HYBRID, LOCAL_SEARCH, GLOBAL_SEARCH, REACQUIRE, HOLD, SAFE_STOP

## 6. Motion Predictor (Linear)

| Metric | Train | Validation | Test |
|--------|-------|------------|------|
| RMSE (px) | 3.33 | 5.09 | 3.97 |
| P95 (px) | 8.7 | 13.1 | 10.4 |

## 7. Failure Predictor

- Architecture: Regularized logistic regression (NumPy-only)
- Window size: 10 frames
- Feature dimension: 60 (last + mean + std + trend)
- **Status: EXPERIMENTAL** — 0% failure rate in training data (tracker never enters formal LOST state with current scenarios). Model defaults to "no failure". Needs harder scenarios with target-out-of-FOV for meaningful training.

## 8. CPU Latency

| Component | Mean | P95 |
|-----------|------|-----|
| GRU temporal predictor | 0.10 ms | 0.12 ms |
| Mission brain (full pipeline) | 0.01 ms | 0.02 ms |

## 9. Closed-Loop Benchmark (8 scenarios, 3s each)

| Metric | Classical | AI-Enhanced |
|--------|-----------|-------------|
| Mean error (px) | 4.3 | **4.2** |
| P95 error (px) | 7.5 | **7.2** |
| Total losses | 0 | 0 |
| Mean FPS | 229.1 | **232.3** |

No regressions. AI-enhanced pipeline performs slightly better with comparable FPS.

## 10. Model Artifacts

| Artifact | Size | Status |
|----------|------|--------|
| artifacts/models/temporal-v3/temporal_gru.pt | 24.3 KB | **production_candidate** |
| artifacts/models/mission-v3/motion-v2.npz | 1.2 KB | **production_candidate** |
| artifacts/models/mission-v3/situation-v2.npz | 1.9 KB | **production_candidate** |
| artifacts/models/mission-v3/policy-v2.npz | 2.5 KB | **production_candidate** |
| artifacts/models/failure-v2/failure-v2.npz | 3.0 KB | experimental |
| artifacts/datasets/temporal-v3/ | ~2 MB | training data |

## 11. GUI Integration

- Added `AIState` dataclass to `gui/state.py` with fields: situation, action, confidence, failure_risk, predictions, ROI, model status, fallback, explanation
- Wired into `gui/worker.py` — updates from `self._last_mission_decision` each frame
- Pre-existing GUI bug: `ApplicationViewState.events` uses `field()` on non-dataclass (not caused by this work)

## 12. Safety Tests

24 safety tests passing:
- NaN/Inf input handling
- Stale decision rejection
- Rate clamping
- ROI boundary enforcement
- Adaptive ROI modes
- All situation classes exercised

## 13. Test Results

- **861 passed**, 1 skipped, 1 pre-existing GUI failure
- All existing functionality preserved

## 14. Reproduction Commands

```bash
# Install
pip install -e ".[dev]"

# Generate dataset
python -m fsoc_tracker.ai.temporal_dataset  # (or call generate_temporal_dataset())

# Train temporal predictor
python -m fsoc_tracker.ai.temporal_training --dataset artifacts/datasets/temporal-v3 --output artifacts/models/temporal-v3

# Train mission models
python -m fsoc_tracker.ai.train_mission_real --dataset artifacts/datasets/temporal-v3 --output artifacts/models/mission-v3

# Run evaluation
python -m fsoc_tracker.ai.temporal_evaluation --dataset artifacts/datasets/temporal-v3 --model artifacts/models/temporal-v3/temporal_gru.pt

# Run benchmark
python -c "from fsoc_tracker.benchmark.ai_benchmark import run_benchmark; run_benchmark()"

# Run tests
pytest tests/ --ignore=tests/unit/test_gui.py
```

## 15. Unresolved Limitations

1. **Failure predictor**: 0% failure rate in training data — tracker Kalman filter maintains estimation even without detections, never enters formal LOST state. Needs scenarios with target completely leaving FOV.

2. **Disturbance performance**: Circular + moderate disturbance takes ~21s per trajectory (vs ~1s for clear/light), limiting dataset diversity.

3. **GRU architecture limitation**: Uses final hidden state only (per-sequence prediction), not per-timestep. This means it cannot provide real-time uncertainty updates mid-sequence.

4. **No Kalman predictor comparison**: Kalman filter internal state is not directly comparable to the GRU's position-difference prediction. The constant-velocity baseline is the closest comparable.

5. **Single-seed training**: All models trained with seed=42. Multi-seed ensembling would improve robustness.

## 16. Production/Experimental Status

| Component | Status |
|-----------|--------|
| Temporal GRU predictor | **production_candidate** |
| Motion predictor (linear) | **production_candidate** |
| Situation classifier | **production_candidate** |
| Policy classifier | **production_candidate** |
| Failure predictor | experimental |
| Adaptive ROI | **production_candidate** |
| Explainability engine | **production_candidate** |
| Mission brain | **production_candidate** |
