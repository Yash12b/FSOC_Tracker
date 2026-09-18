# Benchmark Metrics

## Centroid Error

When ground truth is available, the centroid error measures how far the tracker's estimated position is from the true beacon position.

```
error_x = x_estimated - x_true
error_y = y_estimated - y_true
euclidean_error = sqrt(error_x² + error_y²)
squared_error = error_x² + error_y²
```

**Important**: The metric distinguishes between:
- **Raw detector centroid** — output of the perception engine
- **Filtered tracker centroid** — output of the Kalman filter

Both are recorded. The tracking error typically uses the filtered centroid.

## RMSE

Root Mean Square Error of Euclidean centroid error:

```
RMSE = sqrt(mean(error_x² + error_y²))
```

Also reported as directional components:
```
RMSE_x = sqrt(mean(error_x²))
RMSE_y = sqrt(mean(error_y²))
```

## MAE

Mean Absolute Error:
```
MAE_x = mean(|error_x|)
MAE_y = mean(|error_y|)
```

## Distribution Metrics

Euclidean centroid error percentiles:

| Metric | Meaning |
|--------|---------|
| P50 | Median error — typical performance |
| P90 | 90th percentile — worse-case for 90% of frames |
| P95 | 95th percentile — near worst-case |
| P99 | 99th percentile — extreme outliers |
| Max | Maximum error observed |

These complement mean/RMSE, which can hide occasional major tracking failures.

## Acquisition Time

Definition:
- **acquisition_start**: beginning of a new search/session
- **acquisition_success**: first moment at which stable-lock criteria are satisfied
- **acquisition_time** = success_timestamp - start_timestamp

This is NOT merely "first non-null detection" — it requires stable lock.

Reported values:
- `first_detection_s` — time to first detection
- `stable_acquisition_s` — time to stable lock
- `acquisition_duration_s` — duration of acquisition phase

## Target Loss

A loss event begins when the tracking state enters LOST.

Metrics:
- `loss_event_count` — number of loss events
- `loss_rate_percent` — percentage of tracking time not successfully locked
- Frame-based: `frames_without_lock / evaluable_frames * 100`

## Lock Retention

```
lock_retention_percent = locked_time / evaluable_time * 100
```

Also reported as frame-based:
```
lock_retention_frames = locked_frames / evaluable_frames * 100
```

## Re-acquisition Time

For every loss followed by recovery:
```
reacquisition_time = reacquired_timestamp - loss_timestamp
```

Reported: mean, median, max, P95. Failed reacquisitions are counted separately.

## Processing FPS

```
processing_fps = 1000 / mean(processing_time_ms)
throughput_fps = frame_count / wall_time
```

These are distinct: processing FPS measures per-frame cost, throughput measures overall pipeline speed.

## Pipeline Latency

Measured per-stage:
- **Perception latency** — time in detector
- **Tracking latency** — time in Kalman filter
- **Control latency** — time in PID controller
- **Total latency** — sum of all stages

## Threshold Evaluation (SIH26169)

| Criterion | Threshold | Pass Condition |
|-----------|-----------|----------------|
| Acquisition time | ≤ 2.0s | stable_acquisition_s ≤ 2.0 |
| Tracking error | ≤ 10.0px | rmse_px ≤ 10.0 |
| Target loss | < 5.0% | loss_rate_percent < 5.0 |
| Re-acquisition | ≤ 1.0s | mean_reacquisition_s ≤ 1.0 |
| Processing FPS | ≥ 20.0 | processing_fps ≥ 20.0 |

Verdicts: **PASS**, **FAIL**, **NOT_EVALUABLE** (when ground truth is unavailable).
