# Technical Upgrade Pass

## Baseline method

The internal benchmark matrix uses 180 synthetic 160x120 grayscale frames at
30 Hz, a Gaussian beacon, and an independent synthetic ground-truth provider.
The reported processing rate is measured wall-clock throughput, not source
rate. Errors are computed only from benchmark ground truth and are not passed
to perception, tracking, or control.

The initial matrix exposed a real small-target failure: the production
percentile threshold rejected a 5 px beacon. The detector now performs a
single conservative fallback threshold pass when the strict pass produces no
candidates. This keeps the normal high-threshold path unchanged while making
the documented 5 px operating point observable.

Representative post-fix clean results:

| Target size | RMSE | P95 error | Loss rate | Processing |
| --- | ---: | ---: | ---: | ---: |
| 5 px | 0.6 px | 1.0 px | 70.6% | 3459 FPS |
| 10 px | 0.2 px | 0.3 px | 1.7% | 2717 FPS |
| 20 px | 0.2 px | 0.3 px | 1.7% | 2662 FPS |

The high 5 px loss rate under this deliberately small synthetic PSF remains a
known robustness limitation rather than a hidden benchmark failure. Combined
disturbances are also intentionally retained as a stress case.

## Performance implementation

Candidate extraction uses one OpenCV
`connectedComponentsWithStats` pass instead of computing connected components
twice per frame. The fallback implementation is used only when OpenCV is not
available.

## Failure analysis

Benchmark results now include bounded per-run counts for:

- `false_negative`
- `bad_centroid`
- `association_error`
- `track_loss`
- `frame_drop`
- `latency_spike`

These categories are diagnostic outputs only. They do not alter the runtime
tracking or control decisions.

## Timing and reproducibility

Benchmark lock, loss, and reacquisition durations use source-frame `dt`.
Processing throughput and stage latency remain wall-clock measurements.
Every benchmark run resets the collector and tracker, and synthetic matrices
use a fixed random seed.
