# Temporal prediction

The current learned motion artifact is an observable-feature regression
baseline. Its target is exactly `velocity * 0.1`, so its near-zero error is
expected and is not evidence of learned temporal intelligence.

`fsoc_tracker.ai.neural.build_temporal_predictor` provides an optional GRU
interface for histories of observable features and predicts displacement and
uncertainty at 25, 50, 100, 250, and 500 ms. It must be compared with
constant-velocity and Kalman baselines on unseen trajectory parameters before
use.
