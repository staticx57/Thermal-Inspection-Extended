"""
A synthetic two-camera rig with known geometry, used to MEASURE how well the project's alignment layers register a
thermal and an RGB view of the same scene:

  * ParallaxCompensator (distance-dependent shift from a depth map; ABSOLUTE parallax = baseline * focal / depth)
  * FusionProcessor.align_rgb_to_thermal (a static homography from a calibration file, else an aspect-ratio crop)

Geometry: both cameras are pinholes with the same focal length (f_px) and resolution and the scene is a fronto-parallel
textured plane at depth Z. The RGB camera sits `baseline_m` to the LEFT of the thermal one - the mounting layout the
compensator's sign convention (thermal target, sign = +1) assumes. A world point X maps to thermal pixel
u = f*X/Z + cx and RGB pixel u' = f*(X + b)/Z + cx, so u = u' - f*b/Z: the RGB view is displaced by f*b/Z pixels.
Registration error is read off with phase correlation between the corrected thermal and the aligned RGB.
"""
import cv2
import numpy as np

from thermal_inspection.processing.fusion_processor import FusionProcessor
from thermal_inspection.processing.parallax_compensator import CameraGeometry, ParallaxCompensator

W, H = 320, 256
F_PX = 256.0
BASELINE_M = 0.05
RGB_X_M = -BASELINE_M                                   # RGB camera position relative to the thermal one
PIXEL_PITCH_MM = 0.012
SENSOR_W_MM = PIXEL_PITCH_MM * W                       # 3.84 mm  -> focal_px = F_PX when focal_mm = 3.072
FOCAL_MM = F_PX * PIXEL_PITCH_MM


def shift_px(depth_m: float) -> float:
    """Parallax in pixels between the two views of a plane at depth_m."""
    return F_PX * BASELINE_M / depth_m


def texture(x, y):
    """Smooth but feature-rich greyscale texture of world coordinates (metres) -> float 0..255."""
    t = (np.sin(37 * x + 11 * y) + np.sin(23 * y - 17 * x) + np.sin(61 * x * 0.5 + 29 * y * 0.7)
         + 0.7 * np.sin(97 * x - 71 * y) + 0.5 * np.sin(131 * y + 53 * x))
    return np.clip(127.5 + 28 * t, 0, 255)


def render(depth_m: float, camera_x_m: float) -> np.ndarray:
    """Greyscale image of the textured plane at depth_m seen from a camera at x = camera_x_m."""
    v, u = np.mgrid[0:H, 0:W].astype(np.float64)
    X = (u - W / 2) * depth_m / F_PX + camera_x_m
    Y = (v - H / 2) * depth_m / F_PX
    return texture(X, Y).astype(np.uint8)


def views(depth_m: float):
    """(thermal BGR, rgb BGR) of a plane at depth_m: thermal at x=0, RGB at x=-baseline."""
    th = render(depth_m, 0.0)
    rg = render(depth_m, RGB_X_M)
    return cv2.cvtColor(th, cv2.COLOR_GRAY2BGR), cv2.cvtColor(rg, cv2.COLOR_GRAY2BGR)


def geometry() -> CameraGeometry:
    return CameraGeometry(
        baseline_mm=BASELINE_M * 1000.0,
        thermal_focal_length_mm=FOCAL_MM, rgb_focal_length_mm=FOCAL_MM,
        thermal_sensor_width_mm=SENSOR_W_MM, rgb_sensor_width_mm=SENSOR_W_MM,
        thermal_resolution=(W, H), rgb_resolution=(W, H),
    )


def make_compensator(depth_m: float, enabled: bool = True) -> ParallaxCompensator:
    """The real compensator, fed ground-truth depth through its hardware ('realsense') depth path."""
    comp = ParallaxCompensator(camera_geometry=geometry(), depth_method="realsense")
    comp.set_hardware_depth_source(lambda size=None: np.full((size[1], size[0]) if size else (H, W), depth_m, np.float32))
    comp.correction_recompute_interval_s = 0.0               # never reuse a cached flow map between our calls
    comp.enable(enabled)
    return comp


def homography_for(depth_m: float) -> np.ndarray:
    """What a calibration wizard run at depth_m would produce for this rig: RGB -> thermal pure translation
    (u = u' - f*b/Z, see the module docstring)."""
    return np.array([[1, 0, -shift_px(depth_m)], [0, 1, 0], [0, 0, 1]], dtype=np.float32)


def residual_px(thermal_bgr: np.ndarray, rgb_aligned_bgr: np.ndarray, margin: int = 50):
    """Remaining (dx, dy) misregistration in pixels between two same-size views, from phase correlation on the central
    region (border pixels are blanked/cropped by the corrections, so they are excluded). Positive dx means the RGB
    content sits that many pixels to the RIGHT of the thermal content (the uncorrected rig reads +f*b/Z)."""
    a = cv2.cvtColor(thermal_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)[margin:-margin, margin:-margin]
    b = cv2.cvtColor(rgb_aligned_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)[margin:-margin, margin:-margin]
    win = cv2.createHanningWindow(a.shape[::-1], cv2.CV_32F)
    (dx, dy), _ = cv2.phaseCorrelate(a, b, win)
    return float(dx), float(dy)


def register(depth_m: float, parallax: bool, calibrated_at_m=None):
    """Run the real pipeline on the rig and return the residual misregistration (dx, dy) in pixels:
       thermal -> ParallaxCompensator (if parallax) ; RGB -> FusionProcessor.align_rgb_to_thermal (homography if set)."""
    thermal, rgb = views(depth_m)
    fusion = FusionProcessor()
    if calibrated_at_m is not None:
        fusion.calibration_matrix = homography_for(calibrated_at_m)
    if parallax:
        thermal, rgb = make_compensator(depth_m).apply_correction(thermal, rgb)
    rgb_aligned = fusion.align_rgb_to_thermal(rgb, (H, W))
    return residual_px(thermal, rgb_aligned)
