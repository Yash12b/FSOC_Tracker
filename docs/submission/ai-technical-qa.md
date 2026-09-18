# AI technical Q&A

The production path sees camera pixels through the sensor and perception
interfaces, then uses tracker estimates. Ground truth is restricted to
synthetic label generation and evaluation. The learned motion baseline is
not presented as advanced AI: it learns the deterministic relationship
`velocity * horizon`.

The optional visual model is specialized as a heatmap/keypoint detector
because the beacon is a 5–20 pixel target. A bounded high-level policy may
select modes such as local search or reacquisition, but deterministic safety
code executes the motion. If AI is unavailable, stale, or unsafe, the
deterministic baseline continues operating.

No AI superiority, SIH compliance, physical-video generalization, or
production neural performance is claimed without the corresponding measured
evidence.
