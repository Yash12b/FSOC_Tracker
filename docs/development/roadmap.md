# Development Roadmap

## Stage 1 - Foundation ✅ COMPLETE
- Project structure and packaging
- Configuration system (YAML + Pydantic)
- Core typed models and interfaces
- Frame and FrameSource abstraction
- Time/dt architecture
- Exception hierarchy
- Structured logging
- Synthetic test frame source
- Unit and integration tests
- Smoke-test entry point

## Stage 2 - Virtual 3D Environment ✅ COMPLETE
- World coordinate system (right-handed 3D)
- VirtualWorld + WorldState models
- WorldTargetState (world-space target representation)
- PlatformState foundation
- Trajectory interface (ABC)
- StraightLineTrajectory (p = p₀ + v·t)
- CircularTrajectory (analytical circular motion)
- FigureEightTrajectory (Lissajous 2:1 ratio)
- RandomTrajectory (seeded, deterministic, smooth interpolation)
- SpiralTrajectory (optional, expanding/contracting)
- SinusoidalTrajectory (optional, independent axis oscillation)
- TrajectoryFactory/Registry (extensible, no if/elif chains)
- SimulationEngine (step/reset/update_to/get_state)
- Boundary handling (REFLECT, CLAMP, WRAP)
- Configuration integration (WorldConfig, EngineConfig)
- Serialization (to_dict/from_dict for all models)
- Minimal debug visualization (OpenCV top-down view)
- Simulation demo smoke test (python -m fsoc_tracker.simulation_demo)
- Comprehensive unit tests (50+ tests)
- FPS independence tests (analytical proof)
- Determinism/replay tests
- Architecture documentation

## Stage 3 - Virtual Camera + Projection ✅ COMPLETE
- Camera state model (position, pan/tilt/roll, FOV, resolution)
- Camera intrinsics (focal lengths from FOV, principal point)
- Camera limits (pan/tilt angular bounds, clamping)
- Rotation matrices (pan/yaw, tilt/pitch, roll)
- Camera-to-world and world-to-camera transforms
- Pinhole perspective projection (3D world → 2D pixels)
- Visibility test (behind camera, outside FOV)
- ProjectionResult model (pixel coords, depth, angles, visibility)
- Angular error computation (horizontal + vertical)
- Pixel ↔ angle conversion (roundtrip accurate)
- Rate-limited pan/tilt update (configurable max speed)
- VirtualCamera class (main API: project, error, update, reset)
- Minimal software renderer (beacon projection visualization)
- Camera demo (python -m fsoc_tracker.camera_demo)
- Camera model documentation (docs/algorithms/camera-model.md)
- Comprehensive unit tests (35+ mathematical tests)
- Determinism verification

## Stage 4 - Virtual Optical Sensor + Beacon Image Formation ✅ COMPLETE
- SensorConfig (Pydantic) with SIH26169 defaults (640x480 mono, 10px beacon, 5-20px range)
- ColorMode enum (MONO, BGR, RGB)
- BeaconShape enum (SQUARE, CIRCULAR)
- SizeMode enum (FIXED, DISTANCE_BASED) with interface for future physical model
- TargetVisibility enum (VISIBLE, PARTIAL, OUTSIDE, BEHIND_CAMERA)
- GroundTruth dataclass (target_visible, pixel coords, bbox, angles, depth, brightness)
- RenderedFrame API (image ndarray + ground_truths + timestamp + metadata)
- Beacon image formation (hard square, hard circular, soft Gaussian)
- Sub-pixel beacon location with anti-aliased deposition
- Apparent size policy (fixed pixel mode + distance-based interface)
- Clipping states (VISIBLE/PARTIAL/OUTSIDE/BEHIND_CAMERA)
- Point-spread function (2D Gaussian kernel, configurable sigma)
- Intensity model (background + peak, dynamic range clipping)
- VirtualSensorRenderer (clean API: render → RenderedFrame)
- PSF applied efficiently only to beacon region
- Monochrome uint8 default output
- Debug visualization (separate copy, never contaminates raw image)
- Synthetic dataset generation utility (scripts/generate_synthetic_dataset.py)
- Sensor demo (python -m fsoc_tracker.sensor_demo)
- Sensor model documentation (docs/algorithms/sensor-model.md)
- Comprehensive unit tests (34 tests: A-Q categories)
- Determinism, FPS independence, ground truth separation verified
- All 229 tests passing (Stages 1-4)

## Stage 5 - Baseline Classical Detection ✅ COMPLETE
- PerceptionEngine ABC (extensible for future AI/classical/hybrid backends)
- ClassicalBeaconDetector wrapper implementing the ABC
- Brightness threshold detector (percentile, global, adaptive modes)
- Centroid-based localization (intensity-weighted + geometric, configurable)
- Multi-feature candidate scoring (intensity, size, shape, contrast)
- Sub-pixel centroid estimation
- Ground truth comparison utilities (RMSE, centroid error)
- Debug visualization (non-contaminating, separate copy)
- Perception demo (python -m fsoc_tracker.perception_demo)
- Beacon detection algorithm documentation (docs/algorithms/beacon-detection.md)
- Comprehensive unit tests (47 tests: A-T categories)
- Determinism, FPS independence, noise robustness verified
- All 276 tests passing (Stages 1-5)

## Stage 6 - Temporal Target Tracking + State Estimation ✅ COMPLETE
- TrackerConfig (Pydantic) with SIH26169 defaults
- KalmanFilter2D (NumPy, constant-velocity model, adaptive dt)
- TrackStateMachine (explicit FSM: NO_TRACK → SEARCHING → ACQUIRING → TRACKING → LOST → REACQUIRING)
- Detection-to-track association (nearest-neighbor + gating)
- Euclidean and Mahalanobis gating
- Acquisition logic (configurable consecutive hits, timeout)
- Target loss detection (time-based, FPS-independent)
- Reacquisition logic (timeout-based)
- Track quality estimation
- Lock status
- KalmanTracker (main tracker class, perception-agnostic)
- Performance logging hooks (TrackingMetricsCollector)
- Debug visualization overlay
- Perception-to-tracking pipeline documentation
- Temporal tracking algorithm documentation
- Comprehensive unit tests (59 tests: A-Z categories)
- SIH-style synthetic evaluation test
- Variable FPS tested (10/15/24/30/60/120)
- Irregular timestamps, timestamp rollback, zero/negative dt handled
- All 335 tests passing (Stages 1-6)

## Stage 7 - Closed-Loop Coarse Pointing Control ✅ COMPLETE
- ControllerConfig (Pydantic) with SIH26169 defaults
- PIDController (reusable, anti-windup, derivative filter, deadband, output saturation)
- Pixel-to-angle conversion using Stage-3 camera geometry
- CoarsePointingController (main class: TrackingState → ControlCommand)
- ControlMode state machine (DISABLED, TRACK, PREDICT, SAFE_STOP)
- CameraActuator adapter (ControlCommand → VirtualCamera.update)
- ControlCommand and ControlTelemetry models
- Prediction control with configurable timeout
- NaN safety and ground-truth isolation
- Closed-loop simulation demo (python -m fsoc_tracker.control_demo)
- Coarse pointing control algorithm documentation
- Closed-loop system architecture documentation
- Comprehensive unit tests (92 tests: AA-BB categories)
- Variable FPS tested (10/15/24/30/60/120)
- Tracker integration verified
- All 427 tests passing (Stages 1-7)

## Stage 8 - Disturbance / Noise / Atmospheric Degradation Engine ✅ COMPLETE
- DisturbanceConfig (Pydantic) with noise, atmosphere, jitter, platform motion, turbulence sections
- DisturbanceContext typed data model
- Noise disturbances: Gaussian, Poisson, Salt-and-Pepper
- Atmospheric disturbances: Haze, Fog, Rain, LowLight
- Camera jitter (geometric, pre-render): Bounded, Gaussian, Sinusoidal, DampedVibration
- Platform motion (geometric, pre-render): Linear, Circular, Figure-8, Spiral, Random
- Optical turbulence approximation (sinusoidal displacement field)
- DisturbancePipeline with pre-render/post-render separation
- EffectiveCameraPose computation
- Deterministic RNG (separate streams per domain)
- Severity presets (OFF, CLEAR, LIGHT, MODERATE, SEVERE, EXTREME)
- DisturbanceTelemetry and DisturbancePerformance
- Runtime enable/disable and reconfiguration
- Ground-truth invariance guarantee
- Disturbance demo (python -m fsoc_tracker.disturbance_demo)
- Disturbance models documentation
- Disturbance pipeline architecture documentation
- Comprehensive unit tests (94 tests: A-Z + AA-BB categories)
- FPS independence tested (10/30/60/120 Hz)
- Closed-loop tracking under disturbances verified
- All 521 tests passing (Stages 1-8)

## Stage 9 - AI Perception Subsystem ✅ COMPLETE
- BeaconCNN tiny heatmap CNN (~15K params, pure NumPy inference)
- Synthetic dataset generation from Stage 2-4 simulator + Stage 8 disturbances
- AI config (AIModelConfig, TrainingConfig, DatasetConfig)
- AIBeaconDetector implementing PerceptionEngine ABC
- HybridBeaconDetector with 6 fusion policies
- Model save/load (NumPy .npz) and ONNX export
- AI benchmark framework (precision, recall, centroid error, latency)
- Comprehensive unit tests (49 tests: A-T categories)
- AI perception documentation (model-selection.md, ai-beacon-perception.md)
- All 570 tests passing (Stages 1-9)

## Stage 10 - Performance Metrics + Benchmark + Video Replay Engine ✅ COMPLETE
- BenchmarkSession, BenchmarkScenario, BenchmarkResult models
- BenchmarkThresholds (SIH26169: acquisition ≤2s, error ≤10px, loss <5%, reacq ≤1s, FPS ≥20)
- MetricsCollector (streaming, frame-by-frame, no unlimited image storage)
- FrameMetrics (perception, tracking, control, ground truth, disturbance data)
- PerformanceProfiler / StageTimer (per-stage timing: preprocessing through metrics)
- GroundTruthProvider abstraction (Null, Synthetic, Sidecar JSON/JSONL/CSV)
- VideoBenchmarkSource (OpenCV: MP4, AVI, MKV, MOV)
- LiveCameraSource (webcam via OpenCV)
- BenchmarkEngine (synthetic closed-loop + external video + live modes)
- CSV/JSON export with frame_metrics.csv, event_log.csv, benchmark_result.json
- HTML report generator (dark theme, SIH scorecard)
- Matplotlib plots (error vs time, histogram, centroid path, latency, lock state)
- Experiment runner and sweep utilities
- CI regression benchmark (deterministic, quick, no model required)
- Performance budget framework (max_ms per stage)
- Benchmark documentation (metrics, architecture, user guide)
- Comprehensive unit tests (83 tests: A-W categories)
- All 653 tests passing (Stages 1-10)

## Stage 11 - Professional Aerospace GUI / Tactical HUD ✅ COMPLETE
- PySide6 desktop application (LGPL, maintained, modern Qt bindings)
- Professional aerospace dark theme (centralized Colors, Fonts, Spacing)
- ApplicationViewState read-only snapshot model (thread-safe)
- ProcessingWorker QThread (background pipeline: acquire → detect → track → control)
- ApplicationController thin facade (config management, mode switching)
- Camera view widget with raw/debug overlay, crosshair, bounding box, centroid
- Global world/radar view (2000x2000, trajectory trail, camera FOV cone)
- Telemetry panel (System/Input/Perception/Tracking/Control/Performance sections)
- Tabbed control panel (SIM/CAM/PERC/DIST/VIDEO modes)
- SIH scorecard (5 metrics, pass/fail/not-evaluated, overall verdict)
- Live error plots (QPainter, X/Y/Euclidean/FPS, 300-sample history)
- Event log panel (scrollable, color-coded by level)
- AI perception panel (model status, inference metrics)
- Benchmark panel (progress bar, results display)
- About dialog
- Main window with horizontal splitter, status bar, keyboard shortcuts
- Config save/load (JSON)
- GUI launch via `python -m fsoc_tracker --gui`
- QT_QPA_PLATFORM=offscreen support for CI/headless
- Documentation (architecture/gui.md)
- Comprehensive unit tests (89 tests: state, controller, theme, worker, widgets, main window, integration)
- All 742 tests passing (Stages 1-11)

## Stage 12 - Full-System Integration + Robustness + Validation ✅ COMPLETE
- TrackingPipeline authoritative orchestrator (FrameSource -> Perception -> Tracking -> Control -> Metrics)
- FrameSource ABC + SimulationSource, VideoSource, LiveSource, DatasetSource adapters
- SessionController lifecycle manager (start/stop/pause/resume/reset)
- CLI headless simulation runner (cli/run_simulation.py)
- CLI video benchmark runner (cli/run_benchmark.py)
- Validation suite with 17 automated SIH scenarios
- Integration tests (closed-loop, disturbance matrix, trajectory matrix, FPS matrix, target size)
- Deterministic replay verification
- Camera geometry fixes (target within FOV)
- All 774 tests passing (Stages 1-12)

## Stage 13 - Advanced Intelligence + Adaptive Tracking + Innovation ✅ COMPLETE
- Image quality analyzer (brightness, contrast, noise, blur, edge density, SBR)
- Quality state classification (EXCELLENT/GOOD/DEGRADED/POOR/CRITICAL)
- Uncertainty estimation (multi-source: Kalman covariance, confidence, residual, quality)
- Uncertainty level classification (VERY_LOW/LOW/MODERATE/HIGH/VERY_HIGH)
- Perception policy (adaptive strategy selection: ROI/full-frame/search)
- Confidence-aware perception fusion (classical + AI + tracker + quality)
- Coarse-to-fine subpixel centroid refinement (intensity-weighted, Gaussian fit, moments)
- Adaptive Kalman filter (Q/R scaling based on quality and maneuver state)
- Maneuver detection (SMOOTH/MANEUVERING/UNPREDICTABLE classification)
- Intelligent search and reacquisition (5-phase progressive search)
- Search patterns (spiral, raster, expanding box)
- Lock quality score (multi-factor engineering score)
- Adaptive controller (gain scheduling, feed-forward, anti-oscillation)
- Uncertainty-aware control authority reduction
- PID tuning tools (grid search, random search, multi-objective score)
- Offline robustness-based parameter sweep
- Advanced config (AdvancedConfig with independent feature flags)
- Explainable diagnostic events (25 event types with reasons)
- Advanced demo (python -m fsoc_tracker.advanced_demo)
- Production/baseline/debug config files
- Innovation documentation
- Adaptive system architecture documentation
- 87 unit + integration tests for advanced features
- All 861 tests passing (Stages 1-13)

## Stage 14 - Final SIH Preparation / Polish
- Evaluator-facing benchmark workflow
- Polished demo scenarios
- Technical-report evidence generation
- User manual
- Installation/packaging
- Reproducible one-command demos
- Automated result collection
- Final requirements traceability
- Benchmark readiness for unknown external videos
- Presentation/Q&A preparation
- Final system hardening
