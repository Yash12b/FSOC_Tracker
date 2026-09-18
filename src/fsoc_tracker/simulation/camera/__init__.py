"""Camera subpackage for the simulation environment.

Provides VirtualCamera, state models, geometry, and projection.
"""

from fsoc_tracker.simulation.camera.camera import VirtualCamera
from fsoc_tracker.simulation.camera.geometry import (
    camera_rotation_matrix,
    world_to_camera,
)
from fsoc_tracker.simulation.camera.projection import (
    angle_to_pixel,
    compute_angular_error,
    pixel_to_angle,
    project_to_image,
)
from fsoc_tracker.simulation.camera.renderer import render_camera_view
from fsoc_tracker.simulation.camera.state import (
    AngularError,
    CameraIntrinsics,
    CameraLimits,
    CameraState,
    CameraViewMode,
    ProjectionResult,
)

__all__ = [
    "AngularError",
    "CameraIntrinsics",
    "CameraLimits",
    "CameraState",
    "CameraViewMode",
    "ProjectionResult",
    "VirtualCamera",
    "angle_to_pixel",
    "camera_rotation_matrix",
    "compute_angular_error",
    "pixel_to_angle",
    "project_to_image",
    "render_camera_view",
    "world_to_camera",
]
