# Camera Model (Stage 3)

## Overview

The camera module implements a virtual PTZ (Pan-Tilt-Zoom) camera with perspective projection for the FSOC tracking simulator. It transforms 3D world-space beacon positions into 2D camera image coordinates.

## Coordinate Systems

### World Coordinates
- **Origin**: Bottom-left of the virtual canvas
- **X**: Right (horizontal)
- **Y**: Up (vertical)
- **Z**: Forward (depth into the scene)
- **Convention**: Right-handed, Y-up

### Camera Coordinates
- **Origin**: Camera lens center
- **X**: Image right
- **Y**: Image up
- **Z**: Optical axis (forward)

## Camera State

```
CameraState
├── position: (x, y, z) world coords
├── pan_deg: yaw rotation (horizontal)
├── tilt_deg: pitch rotation (vertical)
├── roll_deg: roll rotation (typically 0)
├── horizontal_fov_deg: field of view
├── vertical_fov_deg: field of view
├── width: image width in pixels
├── height: image height in pixels
├── max_pan_speed_deg_s: rate limit
└── max_tilt_speed_deg_s: rate limit
```

## Rotation Model

Pan/tilt/roll compose into a rotation matrix R (camera-to-world):

```
R = R_pan * R_tilt * R_roll
```

Where:
- **Pan** (yaw): Rotation around world Y axis. Positive = look right.
- **Tilt** (pitch): Rotation around camera X axis. Positive = look up.
- **Roll**: Rotation around camera Z axis. Positive = clockwise.

World-to-camera transform:
```
P_camera = R^T * (P_world - C)
```

Where C is the camera position in world coordinates.

## Projection Model

Pinhole camera projection:

```
pixel_x = fx * (cam_x / cam_z) + cx
pixel_y = fy * (-cam_y / cam_z) + cy
```

Where:
- `fx = (width / 2) / tan(HFOV / 2)` — horizontal focal length
- `fy = (height / 2) / tan(VFOV / 2)` — vertical focal length
- `(cx, cy)` — principal point (image center)

A point is **visible** if:
1. `cam_z > 0` (in front of camera)
2. `0 <= pixel_x < width`
3. `0 <= pixel_y < height`

## Angular Error

The angular error between the camera optical axis and a target is:

```
h_angle = atan2(cam_x, cam_z)  [degrees]
v_angle = atan2(cam_y, cam_z)  [degrees]
total = sqrt(h_angle² + v_angle²)
```

This is used by the PID controller (Stage 8) to drive pan/tilt toward the target.

## Rate Limiting

Pan/tilt movement is rate-limited to simulate physical servo constraints:

```
max_step = max_speed * dt
actual_step = clamp(desired_step, -max_step, max_step)
```

## Default Parameters (SIH26169)

| Parameter | Value |
|-----------|-------|
| Resolution | 640 x 480 |
| HFOV | 4° |
| VFOV | 3° |
| Max pan speed | 5°/s |
| Max tilt speed | 5°/s |
| Update rate | 30 Hz |

## API Usage

```python
from fsoc_tracker.simulation.camera import VirtualCamera, CameraState

# Create camera
state = CameraState(position_x=1000, position_y=1000, position_z=0)
camera = VirtualCamera(state)

# Project a world point
proj = camera.project_world_point((1100, 1050, 950))
print(f"Visible: {proj.visible}, Pixel: ({proj.pixel_x:.1f}, {proj.pixel_y:.1f})")

# Compute angular error to target
err = camera.compute_error((1100, 1050, 950))
print(f"Error: {err.total_angle_deg:.2f}°")

# Set tracking target and update
camera.set_target_pan_tilt(err.horizontal_angle_deg, err.vertical_angle_deg)
camera.update(dt)

# Convert between pixels and angles
angle_h, angle_v = camera.pixel_to_angle(400, 200)
px, py = camera.angle_to_pixel(1.5, -0.8)
```
