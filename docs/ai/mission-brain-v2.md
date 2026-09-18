# Mission brain V2 boundary

The intended flow is image perception, temporal state, motion prediction,
situation classification, policy recommendation, safety validation, and
deterministic execution. No neural component mutates camera state or bypasses
the tracker/controller.

When an optional backend is unavailable, times out, is stale, or produces an
invalid action, the mission brain falls back to deterministic behavior.
