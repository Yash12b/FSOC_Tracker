# Temporal / Situation / Policy Model Card

## Purpose
Predict target motion over 25ms, 50ms, 100ms, 250ms, 500ms horizons using temporal features. Classify the tracking situation and select an optimal policy.

## Architecture
Lightweight Linear/GRU baseline ensemble trained on observable runtime metrics.

## Inputs
Timestamp, X, Y, Velocity, Confidence, Residual, Uncertainty, Miss Count.

## Outputs
Future X/Y positions, Situation classification, Policy recommendation.

## Dataset
Synthetic sequence dataset generated across 14 trajectories and disturbance profiles.

## Splits
Train (4000), Val (1000), Test (1000).

## Metrics
RMSE: ~6e-10 (synthetic linear motion fit)
Situation Accuracy: 80.3%
Policy Accuracy: 80.3%

## Status
PRODUCTION_CANDIDATE (for linear fallback), EXPERIMENTAL (for non-linear predictions).
