"""
Camera Calibration Utility for Thermal-RGB Alignment

Computes a homography that maps RGB-camera pixels onto thermal-camera pixels, from a pair of still images of the SAME
scene taken at the same moment. The result is a JSON file for `python -m thermal_inspection --calibration-file FILE`
(read by FusionProcessor, which warps the RGB frame with it).

What a homography can and cannot do: it registers the two views exactly for ONE plane - the one the calibration images
show - so it captures the fixed geometry (scale, rotation, perspective, lens FOV difference, mounting offset) but not
parallax, which changes with distance. The file therefore records `working_distance_m` (how far that plane was). When
depth-based parallax correction is also on, the app removes the shift the homography already contains at that distance
(FusionProcessor.set_parallax_composition) so the two are not applied twice. Calibrate on a flat target at the distance
you usually inspect from, and pass --distance.

Command line (no cameras needed, works on saved snapshots):

    python -m thermal_inspection.cameras.camera_calibration --thermal t.png --rgb r.png --distance 2.0 \\
        --method features --out calibration.json --preview check.png

Methods: `checkerboard` (most accurate; the pattern must be visible to BOTH cameras - a printed pattern is invisible to a
thermal camera unless it is heated or has contrasting emissivity), `features` (ORB matches; use --edges for the
cross-modal case, where raw brightness differs between a thermal and a visible image), `manual` (click points).
"""
import argparse
import json
import logging
import sys
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MAX_RMS_PX = 3.0        # a fit worse than this is refused by the command line
MIN_INLIERS = 8
MIN_INLIER_RATIO = 0.3          # of the matches, for the RANSAC methods: random matches yield a few chance inliers


def to_gray8(frame: np.ndarray) -> np.ndarray:
    """Any thermal/RGB frame as an 8-bit single-channel image: BGR(A) -> gray; 16-bit (radiometric Y16) and float
    frames are stretched between their 1st and 99th percentile so ORB/chessboard detection can see them."""
    if frame is None:
        raise ValueError("no image")
    f = frame
    if f.ndim == 3:
        if f.dtype != np.uint8:
            f = to_gray8(f.mean(axis=2))
        else:
            f = cv2.cvtColor(f, cv2.COLOR_BGRA2GRAY if f.shape[2] == 4 else cv2.COLOR_BGR2GRAY)
    if f.dtype == np.uint8:
        return f
    lo, hi = np.percentile(f, (1, 99))
    if hi <= lo:
        hi = lo + 1
    return np.clip((f.astype(np.float32) - lo) * (255.0 / (hi - lo)), 0, 255).astype(np.uint8)


def edge_image(gray8: np.ndarray) -> np.ndarray:
    """Gradient-magnitude image: the structure a thermal and a visible image of the same scene actually share (raw
    brightness differs completely between the two), so feature matching on it works across the two modalities."""
    g = cv2.GaussianBlur(gray8, (3, 3), 0)
    mag = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    return cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


class CameraCalibrator:
    """Calibrates thermal and RGB cameras for fusion: computes the homography RGB -> thermal."""

    def __init__(self) -> None:
        self.homography_matrix = None
        self.thermal_points = []
        self.rgb_points = []
        self.calibration_complete = False
        self.quality: Dict[str, Any] = {}
        self.thermal_shape: Optional[Tuple[int, int]] = None      # (height, width) of the images calibrated on
        self.rgb_shape: Optional[Tuple[int, int]] = None

    # ------------------------------------------------------------------ shared

    def _finish(self, pts_rgb: np.ndarray, pts_thermal: np.ndarray, method: str, thermal_frame, rgb_frame,
                ransac: bool = True, min_inliers: int = MIN_INLIERS) -> bool:
        """Fit the homography, measure how good it is (RMS reprojection error over the inliers, in thermal pixels)
        and store it. Returns False when no usable homography results."""
        if len(pts_rgb) < 4:
            logger.error(f"Need at least 4 point pairs, got {len(pts_rgb)}")
            return False
        H, mask = cv2.findHomography(pts_rgb, pts_thermal, cv2.RANSAC if ransac else 0, 5.0)
        if H is None:
            logger.error("Failed to compute homography")
            return False
        inliers = np.ones(len(pts_rgb), bool) if mask is None else mask.ravel().astype(bool)
        if ransac and inliers.sum() < min_inliers:
            logger.error(f"Only {int(inliers.sum())} inlier matches (need {min_inliers}): not a reliable fit")
            return False
        if ransac and inliers.mean() < MIN_INLIER_RATIO:
            logger.error(f"Only {int(inliers.sum())} of {len(inliers)} matches agree on one homography "
                         f"(< {MIN_INLIER_RATIO:.0%}): the images do not show a common structure")
            return False
        proj = cv2.perspectiveTransform(pts_rgb.reshape(-1, 1, 2).astype(np.float64), H).reshape(-1, 2)
        err = np.linalg.norm(proj - pts_thermal, axis=1)[inliers]
        self.homography_matrix = H
        self.quality = {"method": method, "points": int(len(pts_rgb)), "inliers": int(inliers.sum()),
                        "rms_px": float(np.sqrt(np.mean(err ** 2)))}
        self.thermal_shape = tuple(int(v) for v in thermal_frame.shape[:2])
        self.rgb_shape = tuple(int(v) for v in rgb_frame.shape[:2])
        self.calibration_complete = True
        logger.info(f"Calibration ({method}): {self.quality['inliers']}/{self.quality['points']} inliers, "
                    f"RMS {self.quality['rms_px']:.2f} px")
        return True

    # ------------------------------------------------------------------ methods

    def calibrate_with_checkerboard(self, thermal_frame: np.ndarray, rgb_frame: np.ndarray,
                                    checkerboard_size: Tuple[int, int] = (9, 6)) -> bool:
        """Calibrate from a checkerboard seen by both cameras (internal corners, width x height)."""
        try:
            thermal_gray, rgb_gray = to_gray8(thermal_frame), to_gray8(rgb_frame)
            flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            ret_t, corners_t = cv2.findChessboardCorners(thermal_gray, checkerboard_size, flags)
            ret_r, corners_r = cv2.findChessboardCorners(rgb_gray, checkerboard_size, flags)
            if not ret_t or not ret_r:
                logger.error(f"Checkerboard not found (thermal: {ret_t}, RGB: {ret_r})")
                return False
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_t = cv2.cornerSubPix(thermal_gray, corners_t, (11, 11), (-1, -1), criteria)
            corners_r = cv2.cornerSubPix(rgb_gray, corners_r, (11, 11), (-1, -1), criteria)
            return self._finish(corners_r.reshape(-1, 2), corners_t.reshape(-1, 2), "checkerboard",
                                thermal_frame, rgb_frame, min_inliers=4)
        except Exception as e:
            logger.error(f"Calibration error: {e}")
            return False

    def calibrate_with_features(self, thermal_frame: np.ndarray, rgb_frame: np.ndarray,
                                min_matches: int = MIN_INLIERS, use_edges: bool = False,
                                n_features: int = 1500) -> bool:
        """Calibrate from ORB feature matches between the two images of the same scene. use_edges matches on gradient
        magnitude instead of brightness, which is what makes thermal-vs-visible matching workable."""
        try:
            tg, rg = to_gray8(thermal_frame), to_gray8(rgb_frame)
            if use_edges:
                tg, rg = edge_image(tg), edge_image(rg)
            orb = cv2.ORB_create(nfeatures=n_features)
            kp_t, des_t = orb.detectAndCompute(tg, None)
            kp_r, des_r = orb.detectAndCompute(rg, None)
            if des_t is None or des_r is None:
                logger.error("Failed to detect features")
                return False
            matches = sorted(cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(des_r, des_t),
                             key=lambda m: m.distance)
            if len(matches) < min_matches:
                logger.error(f"Not enough matches: {len(matches)} < {min_matches}")
                return False
            good = matches[:min(150, len(matches))]
            pts_r = np.float32([kp_r[m.queryIdx].pt for m in good]).reshape(-1, 2)
            pts_t = np.float32([kp_t[m.trainIdx].pt for m in good]).reshape(-1, 2)
            return self._finish(pts_r, pts_t, "features-edges" if use_edges else "features", thermal_frame, rgb_frame,
                                min_inliers=min_matches)
        except Exception as e:
            logger.error(f"Feature calibration error: {e}")
            return False

    def calibrate_manual(self, thermal_frame: np.ndarray, rgb_frame: np.ndarray, n_points: int = 4) -> bool:
        """Manual calibration by clicking corresponding points: first n in the thermal window, then the same n in RGB."""
        try:
            self.thermal_points, self.rgb_points = [], []
            tview = cv2.cvtColor(to_gray8(thermal_frame), cv2.COLOR_GRAY2BGR)
            rview = rgb_frame.copy() if rgb_frame.ndim == 3 else cv2.cvtColor(rgb_frame, cv2.COLOR_GRAY2BGR)

            def click_thermal(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN and len(self.thermal_points) < n_points:
                    self.thermal_points.append([x, y])
                    cv2.circle(tview, (x, y), 5, (0, 255, 0), -1)
                    cv2.putText(tview, str(len(self.thermal_points)), (x + 8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 255, 0), 2)

            def click_rgb(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN and len(self.rgb_points) < n_points:
                    self.rgb_points.append([x, y])
                    cv2.circle(rview, (x, y), 5, (0, 255, 0), -1)
                    cv2.putText(rview, str(len(self.rgb_points)), (x + 8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 255, 0), 2)

            for name, view, cb, pts in (("Thermal - click points in order", tview, click_thermal, self.thermal_points),
                                        ("RGB - click the SAME points in the same order", rview, click_rgb, self.rgb_points)):
                cv2.namedWindow(name)
                cv2.setMouseCallback(name, cb)
                while len(pts) < n_points:
                    cv2.imshow(name, view)
                    if cv2.waitKey(50) & 0xFF == 27:
                        cv2.destroyAllWindows()
                        return False
                cv2.destroyWindow(name)
            return self._finish(np.float32(self.rgb_points), np.float32(self.thermal_points), "manual",
                                thermal_frame, rgb_frame, ransac=False)
        except Exception as e:
            logger.error(f"Manual calibration error: {e}")
            return False

    # ------------------------------------------------------------------ check / persistence

    def warp_rgb(self, thermal_frame: np.ndarray, rgb_frame: np.ndarray) -> np.ndarray:
        h, w = thermal_frame.shape[:2]
        return cv2.warpPerspective(rgb_frame, self.homography_matrix, (w, h))

    def test_calibration(self, thermal_frame: np.ndarray, rgb_frame: np.ndarray) -> np.ndarray:
        """Side-by-side check: thermal | warped RGB."""
        thermal_bgr = cv2.cvtColor(to_gray8(thermal_frame), cv2.COLOR_GRAY2BGR) if thermal_frame.ndim == 2 or \
            thermal_frame.dtype != np.uint8 else thermal_frame
        if not self.calibration_complete or self.homography_matrix is None:
            logger.error("No calibration available")
            return np.hstack([thermal_bgr, cv2.resize(rgb_frame, thermal_bgr.shape[1::-1])])
        try:
            warped = self.warp_rgb(thermal_bgr, rgb_frame)
            h, w = thermal_bgr.shape[:2]
            out = np.hstack([thermal_bgr, warped])
            cv2.putText(out, "THERMAL", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(out, "RGB (WARPED)", (w + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            return out
        except Exception as e:
            logger.error(f"Test calibration error: {e}")
            return thermal_bgr

    def save_calibration(self, filename: str, working_distance_m: Optional[float] = None) -> bool:
        """Write the JSON FusionProcessor.load_calibration reads. working_distance_m is the distance to the plane the
        calibration images showed: needed so parallax correction and this homography can be used together."""
        if not self.calibration_complete or self.homography_matrix is None:
            logger.error("No calibration to save")
            return False
        try:
            data = {
                "homography": np.asarray(self.homography_matrix).tolist(),
                "timestamp": time.time(),
                "working_distance_m": float(working_distance_m) if working_distance_m else None,
                "thermal_shape": list(self.thermal_shape) if self.thermal_shape else None,
                "rgb_shape": list(self.rgb_shape) if self.rgb_shape else None,
                **{k: v for k, v in self.quality.items()},
            }
            data = {k: v for k, v in data.items() if v is not None}
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Calibration saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            return False

    def load_calibration(self, filename: str) -> bool:
        try:
            with open(filename, encoding="utf-8") as f:
                data = json.load(f)
            self.homography_matrix = np.array(data["homography"], dtype=np.float32)
            self.thermal_shape = tuple(data["thermal_shape"]) if data.get("thermal_shape") else None
            self.rgb_shape = tuple(data["rgb_shape"]) if data.get("rgb_shape") else None
            self.quality = {k: data[k] for k in ("method", "points", "inliers", "rms_px") if k in data}
            self.calibration_complete = True
            return True
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            return False


# ---------------------------------------------------------------------- command line

def _read(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)           # keeps 16-bit radiometric PNG/TIFF as 16-bit
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    return img


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m thermal_inspection.cameras.camera_calibration",
        description="Compute the RGB->thermal alignment homography from a pair of snapshots of the same scene.")
    p.add_argument("--thermal", required=True, help="thermal snapshot (8-bit or 16-bit)")
    p.add_argument("--rgb", required=True, help="RGB snapshot taken at the same moment")
    p.add_argument("--distance", type=float, required=True, metavar="METERS",
                   help="distance from the cameras to the flat plane/target the images show (recorded in the file)")
    p.add_argument("--method", choices=["checkerboard", "features"], default="features")
    p.add_argument("--checkerboard", default="9x6", metavar="CxR", help="internal corners, e.g. 9x6 (default)")
    p.add_argument("--edges", action="store_true", help="match features on gradient magnitude (thermal vs visible)")
    p.add_argument("--out", default="camera_calibration.json", help="output JSON (default: camera_calibration.json)")
    p.add_argument("--preview", metavar="PNG", help="write a thermal | warped-RGB check image")
    p.add_argument("--max-rms", type=float, default=DEFAULT_MAX_RMS_PX, metavar="PX",
                   help=f"refuse to save a fit with a larger RMS error (default {DEFAULT_MAX_RMS_PX} px)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.distance <= 0:
        p.error("--distance must be positive")
    try:
        thermal, rgb = _read(args.thermal), _read(args.rgb)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    cal = CameraCalibrator()
    if args.method == "checkerboard":
        try:
            cols, rows = (int(v) for v in args.checkerboard.lower().split("x"))
        except ValueError:
            p.error("--checkerboard must look like 9x6")
        ok = cal.calibrate_with_checkerboard(thermal, rgb, (cols, rows))
    else:
        ok = cal.calibrate_with_features(thermal, rgb, use_edges=args.edges)
    if not ok:
        print("ERROR: calibration failed - no usable correspondence between the two images "
              "(try --edges, --method checkerboard, or a scene with more structure).", file=sys.stderr)
        return 1

    q = cal.quality
    print(f"Fit: {q['inliers']}/{q['points']} points, RMS error {q['rms_px']:.2f} px (thermal pixels)")
    if args.preview:
        cv2.imwrite(args.preview, cal.test_calibration(thermal, rgb))
        print(f"Check image written to {args.preview}")
    if q["rms_px"] > args.max_rms:
        print(f"ERROR: RMS {q['rms_px']:.2f} px exceeds --max-rms {args.max_rms:g}: not saved.", file=sys.stderr)
        return 1
    if not cal.save_calibration(args.out, working_distance_m=args.distance):
        return 1
    print(f"Saved {args.out} (calibrated at {args.distance:g} m).\n"
          f"Use it with:  python -m thermal_inspection --calibration-file {args.out}")
    return 0


def calibration_wizard(thermal_cam: Any, rgb_cam: Any, output_file: str = "camera_calibration.json",
                       working_distance_m: Optional[float] = None) -> bool:
    """Interactive wizard for live cameras (objects with a read() method). Prefer the command line on snapshots; this
    exists for scripting against already-open cameras."""
    print("=" * 60 + "\nCAMERA CALIBRATION WIZARD\n" + "=" * 60)
    if working_distance_m is None:
        while True:
            try:
                working_distance_m = float(input("Distance to the target in metres: ").strip())
                if working_distance_m > 0:
                    break
            except ValueError:
                pass
            print("Enter a positive number.")
    cal = CameraCalibrator()
    choice = ""
    while choice not in ("1", "2", "3"):
        choice = input("Method: 1 checkerboard, 2 feature matching, 3 manual points: ").strip()
    ok_t, thermal = thermal_cam.read()
    ok_r, rgb = rgb_cam.read()
    if not ok_t or not ok_r:
        print("ERROR: failed to capture frames")
        return False
    input("Press Enter when both cameras see the target...")
    ok = (cal.calibrate_with_checkerboard(thermal, rgb) if choice == "1"
          else cal.calibrate_with_features(thermal, rgb, use_edges=True) if choice == "2"
          else cal.calibrate_manual(thermal, rgb))
    if not ok:
        print("Calibration failed")
        return False
    print(f"RMS error {cal.quality['rms_px']:.2f} px")
    cv2.imshow("Calibration check (thermal | warped RGB)", cal.test_calibration(thermal, rgb))
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    return cal.save_calibration(output_file, working_distance_m=working_distance_m)


if __name__ == "__main__":
    sys.exit(main())
