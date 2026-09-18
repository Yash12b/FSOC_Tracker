"""Perspective projection: 3D world → camera pixels.

Uses the pinhole camera model with focal lengths derived from FOV.
Projection follows standard conventions:
    pixel_x = fx * (cx / cz) + cx
    pixel_y = fy * (cy / cz) + cy

where (cx, cy, cz) are camera-space coordinates.
"""

from __future__ import annotations

import math

from fsoc_tracker.simulation.camera.geometry import (
    world_to_camera,
)
from fsoc_tracker.simulation.camera.state import CameraIntrinsics, ProjectionResult


def project_to_image(
    point_world: tuple[float, float, float],
    camera_position: tuple[float, float, float],
    intrinsics: CameraIntrinsics,
    rotation_matrix: list[list[float]],
) -> ProjectionResult:
    """Project a world-space point into camera pixel coordinates.

    Args:
        point_world: (x, y, z) in world coordinates.
        camera_position: (x, y, z) of camera in world coordinates.
        intrinsics: Camera intrinsic parameters (focal lengths, principal point).
        rotation_matrix: Camera-to-world rotation matrix.

    Returns:
        ProjectionResult with pixel coordinates and visibility info.
    """
    cam_x, cam_y, cam_z = world_to_camera(point_world, camera_position, rotation_matrix)

    result = ProjectionResult(
        camera_x=cam_x,
        camera_y=cam_y,
        camera_z=cam_z,
    )

    if cam_z <= 0:
        result.visible = False
        return result

    pixel_x = intrinsics.fx * (cam_x / cam_z) + intrinsics.cx
    pixel_y = intrinsics.fy * (-cam_y / cam_z) + intrinsics.cy

    result.pixel_x = pixel_x
    result.pixel_y = pixel_y
    result.depth = cam_z

    result.normalized_x = (pixel_x - intrinsics.cx) / intrinsics.cx
    result.normalized_y = -(pixel_y - intrinsics.cy) / intrinsics.cy

    result.horizontal_angle_deg = math.degrees(math.atan2(cam_x, cam_z))
    result.vertical_angle_deg = math.degrees(math.atan2(cam_y, cam_z))

    if (
        0 <= pixel_x < intrinsics.width
        and 0 <= pixel_y < intrinsics.height
    ):
        result.visible = True
    else:
        result.visible = False

    return result


def compute_angular_error(
    target_world: tuple[float, float, float],
    camera_position: tuple[float, float, float],
    rotation_matrix: list[list[float]],
) -> tuple[float, float]:
    """Compute angular error between camera optical axis and target direction.

    Args:
        target_world: Target position in world coordinates.
        camera_position: Camera position in world coordinates.
        rotation_matrix: Camera-to-world rotation matrix.

    Returns:
        (horizontal_angle_deg, vertical_angle_deg) relative to optical axis.
    """
    cam_x, cam_y, cam_z = world_to_camera(target_world, camera_position, rotation_matrix)

    if cam_z <= 0:
        return (0.0, 0.0)

    h_angle = math.degrees(math.atan2(cam_x, cam_z))
    v_angle = math.degrees(math.atan2(cam_y, cam_z))
    return (h_angle, v_angle)


def pixel_to_angle(
    pixel_x: float,
    pixel_y: float,
    intrinsics: CameraIntrinsics,
) -> tuple[float, float]:
    """Convert pixel coordinates to angular offsets from optical axis.

    Args:
        pixel_x: Horizontal pixel coordinate.
        pixel_y: Vertical pixel coordinate.
        intrinsics: Camera intrinsic parameters.

    Returns:
        (horizontal_angle_deg, vertical_angle_deg).
    """
    dx = pixel_x - intrinsics.cx
    dy = -(pixel_y - intrinsics.cy)
    h_angle = math.degrees(math.atan2(dx, intrinsics.fx))
    v_angle = math.degrees(math.atan2(dy, intrinsics.fy))
    return (h_angle, v_angle)


def angle_to_pixel(
    angle_h_deg: float,
    angle_v_deg: float,
    intrinsics: CameraIntrinsics,
) -> tuple[float, float]:
    """Convert angular offsets from optical axis to pixel coordinates.

    Args:
        angle_h_deg: Horizontal angle in degrees.
        angle_v_deg: Vertical angle in degrees.
        intrinsics: Camera intrinsic parameters.

    Returns:
        (pixel_x, pixel_y).
    """
    dx = intrinsics.fx * math.tan(math.radians(angle_h_deg))
    dy = intrinsics.fy * math.tan(math.radians(angle_v_deg))
    pixel_x = dx + intrinsics.cx
    pixel_y = -dy + intrinsics.cy
    return (pixel_x, pixel_y)
