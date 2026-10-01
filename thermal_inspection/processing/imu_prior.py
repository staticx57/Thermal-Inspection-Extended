"""
IMU helpers for 3D Mapping: a rotation head-start for the tracker and a gravity sanity check.

RealSense L515 and D4xx IMUs (BMI055 / BMI085) give gyro rates and accelerometer readings in the camera's own frame.
  * delta_R: rotation of the camera since the previous sample window, as a 3x3 matrix R with
             orientation_now = orientation_before @ R   (camera-frame increment).
  * gravity_cam: the accelerometer's low-passed reading (m/s^2) in the camera frame. At rest it points UP (an
             accelerometer measures the reaction to gravity), so "up in the world" seen from the camera.
Neither is used as a measurement of position - only as a prior (ICP/odometry still decide) and a veto when a pose's
tilt contradicts gravity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

GRAVITY = 9.81


@dataclass
class ImuSample:
    delta_R: np.ndarray                      # 3x3, rotation since the previous sample (camera frame increment)
    gravity_cam: Optional[np.ndarray] = None  # 3-vector (m/s^2) or None when no accelerometer reading yet

    @staticmethod
    def identity() -> "ImuSample":
        return ImuSample(np.eye(3), None)

    def then(self, later: "ImuSample") -> "ImuSample":
        """Combine two consecutive windows (self first): rotations compose, the newest gravity reading wins."""
        g = later.gravity_cam if later.gravity_cam is not None else self.gravity_cam
        return ImuSample(self.delta_R @ later.delta_R, g)


def rotation_from_rotvec(rv: np.ndarray) -> np.ndarray:
    """Rodrigues: rotation vector (rad) -> 3x3 matrix (no OpenCV dependency)."""
    rv = np.asarray(rv, dtype=float)
    theta = float(np.linalg.norm(rv))
    if theta < 1e-12:
        return np.eye(3)
    k = rv / theta
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * (K @ K)


def integrate_gyro(samples, t_start: float, t_end: float) -> np.ndarray:
    """Integrate gyro samples [(t_seconds, wx, wy, wz) rad/s in the camera frame] over [t_start, t_end] into one
    rotation (3x3). Each sample's rate is held until the next sample (zero-order hold); samples must be time-ordered."""
    R = np.eye(3)
    if len(samples) == 0 or t_end <= t_start:
        return R
    arr = np.asarray(samples, dtype=float)
    t = arr[:, 0]
    # rate in effect at t_start: the latest sample at or before it (else the first one after)
    lo = np.searchsorted(t, t_start, side="right") - 1
    cur = max(lo, 0)
    edges = [t_start] + [x for x in t if t_start < x < t_end] + [t_end]
    idx = cur
    for a, b in zip(edges[:-1], edges[1:]):
        # advance to the last sample at or before `a`
        while idx + 1 < len(t) and t[idx + 1] <= a:
            idx += 1
        R = R @ rotation_from_rotvec(arr[idx, 1:4] * (b - a))
    return R


def rotation_prior_transform(delta_R_since_reference: np.ndarray) -> np.ndarray:
    """Initial guess for Open3D's odometry between a reference frame and the current frame. Odometry's transform maps
    reference-camera coordinates into the current camera's: when the camera rotated by R (reference -> now), a fixed
    point's coordinates change by R^T. Translation is unknown, so zero."""
    T = np.eye(4)
    T[:3, :3] = np.asarray(delta_R_since_reference).T
    return T


def pose_with_rotation_prior(pose: np.ndarray, delta_R: np.ndarray) -> np.ndarray:
    """Camera-to-world pose advanced by a camera-frame rotation increment (translation kept)."""
    out = np.array(pose, dtype=float, copy=True)
    out[:3, :3] = out[:3, :3] @ np.asarray(delta_R)
    return out


def is_quasi_static(gravity_cam: Optional[np.ndarray], tolerance: float = 1.5) -> bool:
    """True when the accelerometer reads ~1 g (camera not being shaken or accelerated), so its direction is a
    trustworthy gravity estimate."""
    if gravity_cam is None:
        return False
    return abs(float(np.linalg.norm(gravity_cam)) - GRAVITY) <= tolerance


def gravity_world_from_pose(pose: np.ndarray, gravity_cam: np.ndarray) -> np.ndarray:
    """Unit 'up' direction in the world frame, given the camera's pose and its accelerometer reading."""
    g = np.asarray(gravity_cam, dtype=float)
    g = g / np.linalg.norm(g)
    return np.asarray(pose)[:3, :3] @ g


def gravity_error_deg(pose: np.ndarray, gravity_cam: Optional[np.ndarray], gravity_world: Optional[np.ndarray]) -> float:
    """Angle (deg) between the world 'up' the pose implies and the stored world 'up'. 0 when either is unknown or the
    camera is being accelerated (reading not trustworthy) - i.e. never vetoes without good evidence."""
    if gravity_world is None or not is_quasi_static(gravity_cam):
        return 0.0
    implied = gravity_world_from_pose(pose, gravity_cam)
    ref = np.asarray(gravity_world, dtype=float)
    ref = ref / np.linalg.norm(ref)
    return float(np.degrees(np.arccos(np.clip(float(implied @ ref), -1.0, 1.0))))
