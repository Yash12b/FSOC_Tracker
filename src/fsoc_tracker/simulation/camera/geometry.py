"""Camera geometry: rotation matrices, coordinate transforms.

All rotations use rotation matrices for clarity and correctness.
Euler angles (pan/tilt/roll) are converted to matrices as needed.

Convention:
    World: +X right, +Y up, +Z forward
    Camera: +X right, +Y up, +Z forward (optical axis)

Pan (yaw) rotates around world Y axis.
Tilt (pitch) rotates around camera X axis (after pan).
Roll rotates around camera Z axis (after pan and tilt).
"""

from __future__ import annotations

import math


def rotation_y(angle_deg: float) -> list[list[float]]:
    """Rotation matrix around the Y axis (pan/yaw).

    Positive angle rotates from +Z toward +X (rightward).
    """
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [
        [c, 0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c],
    ]


def rotation_x(angle_deg: float) -> list[list[float]]:
    """Rotation matrix around the X axis (tilt/pitch).

    Positive angle rotates from +Y toward +Z (looking down).
    """
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [
        [1.0, 0.0, 0.0],
        [0.0, c, -s],
        [0.0, s, c],
    ]


def rotation_z(angle_deg: float) -> list[list[float]]:
    """Rotation matrix around the Z axis (roll).

    Positive angle rotates from +X toward +Y.
    """
    a = math.radians(angle_deg)
    c, s = math.cos(a), math.sin(a)
    return [
        [c, -s, 0.0],
        [s, c, 0.0],
        [0.0, 0.0, 1.0],
    ]


def mat_mul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """Multiply two 3x3 matrices."""
    result = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            for k in range(3):
                result[i][j] += a[i][k] * b[k][j]
    return result


def mat_vec_mul(m: list[list[float]], v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Multiply a 3x3 matrix by a 3-vector."""
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def transpose(m: list[list[float]]) -> list[list[float]]:
    """Transpose a 3x3 matrix."""
    return [[m[j][i] for j in range(3)] for i in range(3)]


def camera_rotation_matrix(
    pan_deg: float,
    tilt_deg: float,
    roll_deg: float = 0.0,
) -> list[list[float]]:
    """Compute the camera-to-world rotation matrix.

    The camera starts looking along +Z (world).
    Pan rotates around world Y (positive = look right).
    Tilt rotates around camera X (positive = look up).
    Roll rotates around camera Z (positive = clockwise when looking along Z).

    The resulting matrix R maps camera coordinates to world coordinates:
        P_world = R * P_camera + C

    To go from world to camera:
        P_camera = R^T * (P_world - C)
    """
    r_pan = rotation_y(pan_deg)
    r_tilt = rotation_x(-tilt_deg)
    r_roll = rotation_z(roll_deg)
    return mat_mul(r_pan, mat_mul(r_tilt, r_roll))


def world_to_camera(
    point_world: tuple[float, float, float],
    camera_position: tuple[float, float, float],
    rotation_matrix: list[list[float]],
) -> tuple[float, float, float]:
    """Transform a world-space point to camera-space coordinates.

    P_camera = R^T * (P_world - C)

    Args:
        point_world: Point in world coordinates.
        camera_position: Camera position in world coordinates.
        rotation_matrix: Camera-to-world rotation (from ``camera_rotation_matrix``).

    Returns:
        Point in camera coordinates (X=right, Y=up, Z=forward).
    """
    dx = point_world[0] - camera_position[0]
    dy = point_world[1] - camera_position[1]
    dz = point_world[2] - camera_position[2]
    r_inv = transpose(rotation_matrix)
    return mat_vec_mul(r_inv, (dx, dy, dz))
