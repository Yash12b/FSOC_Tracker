# Policy model

The learned policy predicts bounded high-level actions such as tracking,
reacquisition, or hold. It cannot issue raw pan/tilt commands. Every learned
recommendation is passed through `SafetyEnvelope`, and deterministic policy
behavior remains the fallback.

Policy accuracy against an expert teacher is not sufficient proof of outcome
quality; closed-loop lock retention, loss, reacquisition, and control effort
must also be measured.
