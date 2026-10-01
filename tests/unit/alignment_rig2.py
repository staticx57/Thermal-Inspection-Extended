"""
A second synthetic rig, closer to the real hardware than alignment_rig.py: the RGB camera has a DIFFERENT focal length and
resolution than the thermal one (the real pairs differ a lot), can be rolled a little about its optical axis, and the
scene texture is corner-rich noise (so ORB feature calibration works on it, which the smooth sinusoid texture of the first
rig does not allow). Geometry is exact: both cameras are pinholes looking at a fronto-parallel plane at depth Z, RGB
sitting `BASELINE_M` to the left of the thermal one.

  thermal pixel  u_t = F_T * X / Z + cx_t
  rgb pixel      u_r = F_R * (X + b) / Z + cx_r      (then rolled by `roll_deg` about the RGB centre)
"""
import cv2
import numpy as np

from thermal_inspection.processing.parallax_compensator import CameraGeometry, ParallaxCompensator

TW, TH = 320, 256
RW, RH = 480, 384
F_T = 256.0
F_R = 1.5 * F_T                       # RGB sees a narrower field than thermal here (longer focal length)
BASELINE_M = 0.05
PITCH_MM = 0.012
WORLD_PX_PER_M = 150.0                # texture resolution of the plane
OVERSAMPLE = 3                        # sub-pixel samples per axis, area-averaged (a real pixel integrates its footprint)


def _plane_texture():
    """Multi-scale blotchy texture with plenty of corners at the scale a pixel sees (a few cm)."""
    rng = np.random.default_rng(11)
    acc = np.zeros((1600, 1600), np.float32)
    for sigma, weight in ((3, 0.5), (6, 1.0), (12, 1.0), (24, 0.7)):
        n = cv2.GaussianBlur(rng.standard_normal((1600, 1600)).astype(np.float32), (0, 0), sigma)
        acc += weight * n / n.std()
    return cv2.normalize(acc, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


_TEX = _plane_texture()
_TEX_C = _TEX.shape[0] / 2.0


def render(width, height, focal_px, depth_m, camera_x_m, roll_deg=0.0):
    """Image of the textured plane at depth_m from a pinhole camera at x = camera_x_m."""
    k = OVERSAMPLE
    v, u = np.mgrid[0:height * k, 0:width * k].astype(np.float32)
    u, v = (u + 0.5) / k - 0.5, (v + 0.5) / k - 0.5
    ur, vr = u - width / 2, v - height / 2
    if roll_deg:
        c, s = np.cos(np.radians(roll_deg)), np.sin(np.radians(roll_deg))
        ur, vr = c * ur - s * vr, s * ur + c * vr
    X = ur * depth_m / focal_px + camera_x_m
    Y = vr * depth_m / focal_px
    map_x = (X * WORLD_PX_PER_M + _TEX_C).astype(np.float32)
    map_y = (Y * WORLD_PX_PER_M + _TEX_C).astype(np.float32)
    big = cv2.remap(_TEX, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return cv2.resize(big, (width, height), interpolation=cv2.INTER_AREA)


def views(depth_m, roll_deg=0.0):
    """(thermal BGR 320x256, rgb BGR 480x384) of the plane at depth_m."""
    th = render(TW, TH, F_T, depth_m, 0.0)
    rg = render(RW, RH, F_R, depth_m, -BASELINE_M, roll_deg)
    return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR), cv2.cvtColor(rg, cv2.COLOR_GRAY2BGR)


def geometry():
    return CameraGeometry(
        baseline_mm=BASELINE_M * 1000.0,
        thermal_focal_length_mm=F_T * PITCH_MM, rgb_focal_length_mm=F_R * PITCH_MM,
        thermal_sensor_width_mm=PITCH_MM * TW, rgb_sensor_width_mm=PITCH_MM * RW,
        thermal_resolution=(TW, TH), rgb_resolution=(RW, RH),
    )


def make_compensator(depth_m, target="thermal"):
    comp = ParallaxCompensator(camera_geometry=geometry(), depth_method="realsense")
    comp.set_hardware_depth_source(lambda size=None: np.full((size[1], size[0]) if size else (RH, RW), depth_m, np.float32))
    comp.correction_recompute_interval_s = 0.0
    comp.set_correction_target(target)
    comp.enable(True)
    return comp
