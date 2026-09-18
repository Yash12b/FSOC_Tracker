# Virtual Environment Architecture

## Coordinate System

The simulation world uses a **right-handed 3D coordinate system**:

```
    Y (up)
    ^
    |
    |
    +------> X (right)
   /
  /
 Z (forward/depth)
```

- **Origin**: (0, 0, 0) at the bottom-left-front corner of the world volume
- **X axis**: Horizontal, increasing rightward
- **Y axis**: Vertical, increasing upward
- **Z axis**: Depth, increasing forward (away from viewer)
- **Units**: World units (meters by default, configurable)
- **Orientation**: Right-handed (X cross Y = Z)

## World Representation

```
┌──────────────────────────────────┐
│ WorldConfig                      │
│  width: 2000.0                   │
│  height: 2000.0                  │
│  depth: 100.0                    │
│  boundary_mode: REFLECT          │
│  random_seed: 42                 │
├──────────────────────────────────┤
│ WorldState                       │
│  config: WorldConfig             │
│  targets: [WorldTargetState, …] │
│  platform: PlatformState         │
│  simulation_time_s: float        │
│  step_count: int                 │
└──────────────────────────────────┘
```

The world is a mathematical abstraction. It does NOT allocate pixel buffers.
The 2000×2000 specification defines the logical coordinate range, not an image.

## Target Model

Each target is represented by `WorldTargetState`:

```
WorldTargetState
  ├── target_id: int
  ├── active: bool
  ├── position: (x, y, z)         ← world coordinates
  ├── velocity: (vx, vy, vz)      ← world units/second
  ├── acceleration: (ax, ay, az)
  ├── shape, width, height        ← physical dimensions
  ├── brightness
  ├── trajectory_type: str
  ├── trajectory_params: dict
  ├── spawn_time_s, current_time_s
  └── metadata
```

**Critical**: The target's physical size (width/height in meters) is separate from its apparent pixel size. Pixel size is computed by the camera projection (Stage 3).

## Platform Model

`PlatformState` represents the FSOC terminal mounting platform:

```
PlatformState
  ├── position: (x, y, z)
  ├── orientation: (roll, pitch, yaw) in degrees
  ├── linear velocity
  ├── angular velocity
  └── timestamp
```

Initially stationary. The disturbance engine (Stage 9) will modify this.

## Trajectory Abstraction

All trajectories implement the `Trajectory` interface:

```
Trajectory (ABC)
  ├── position(t) → (x, y, z)
  ├── velocity(t) → (vx, vy, vz)
  ├── acceleration(t) → (ax, ay, az)
  ├── reset()
  ├── duration → float | None
  ├── is_finished(t) → bool
  ├── to_dict() → dict
  └── from_dict(d) → Trajectory
```

**FPS Independence**: Position is evaluated as an analytical function of simulation time `t`. There are no per-frame increments. The same trajectory at 15 FPS and 120 FPS produces the same position at the same simulation time.

## Trajectory Equations

### Straight Line
```
p(t) = p₀ + v·t
v(t) = v    (constant)
a(t) = 0
```

### Circular
```
x(t) = cx + r·cos(ωt + φ)
y(t) = cy + r·sin(ωt + φ)
z(t) = cz

vx(t) = -rω·sin(ωt + φ)
vy(t) =  rω·cos(ωt + φ)

ax(t) = -rω²·cos(ωt + φ)
ay(t) = -rω²·sin(ωt + φ)
```

### Figure-8 (Lissajous)
```
x(t) = cx + Ax·sin(ωt + φx)
y(t) = cy + Ay·sin(2ωt + φy)

2:1 frequency ratio produces the figure-8 shape.
```

### Random
- Seeded RNG generates waypoints
- Cosine interpolation between waypoints ensures smoothness
- Same seed → same trajectory (deterministic)

## Boundary Handling

Three modes for when targets reach world boundaries:

| Mode | Behavior |
|------|----------|
| `REFLECT` | Bounce: position reflected, velocity reversed |
| `CLAMP` | Stop: position clamped, velocity zeroed |
| `WRAP` | Teleport: position wraps to opposite side |

Applied independently per axis (X, Y, Z).

## Simulation Clock

Uses `SimulationClock` from Stage 1. Key properties:

- `sim_time_s`: Current simulation time (seconds)
- `time_scale`: Acceleration factor (1.0 = real-time)
- `pause()` / `resume()`: Freeze/unfreeze time
- `step(dt)`: Deterministic time advance
- `reset()`: Return to t=0

## Determinism

Given:
- Same `WorldConfig`
- Same random seed
- Same initial target state
- Same sequence of `step(dt)` calls

The resulting `WorldState` is bit-identical (for analytical trajectories) or statistically identical (for random trajectories with same seed).

## World-Space vs Image-Space

```
World Space                    Image Space
(meters, right-handed)         (pixels, top-left origin)
                               
  Target at (1200, 800, 50)    Camera sees beacon at (320, 240)
       │                            │
       ▼                            ▼
  Camera projection ────────► Pixel coordinates
  (Stage 3)                    (Stage 3)
```

The world simulator produces **world coordinates**. The camera subsystem (Stage 3) will project these to **pixel coordinates**. This separation is intentional.
