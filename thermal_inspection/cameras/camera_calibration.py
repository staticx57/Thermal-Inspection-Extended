"""
Camera Calibration Utility for Thermal-RGB Alignment
Computes homography matrix to align RGB camera to thermal camera coordinate system
"""
import cv2
import numpy as np
import logging
import json
from typing import Tuple, Optional, List
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CameraCalibrator:
    """
    Calibrates thermal and RGB cameras for fusion
    Computes homography matrix to align RGB to thermal coordinate system
    """

    def __init__(self):
        """Initialize calibrator"""
        self.homography_matrix = None
        self.thermal_points = []
        self.rgb_points = []
        self.calibration_complete = False

    def calibrate_with_checkerboard(self, thermal_frame: np.ndarray,
                                     rgb_frame: np.ndarray,
                                     checkerboard_size: Tuple[int, int] = (9, 6)) -> bool:
        """
        Calibrate using checkerboard pattern
        Requires both cameras to see the same checkerboard

        Args:
            thermal_frame: Thermal frame (grayscale or BGR)
            rgb_frame: RGB frame (BGR)
            checkerboard_size: Internal corners of checkerboard (width, height)

        Returns:
            True if calibration successful
        """
        try:
            # Convert to grayscale
            if len(thermal_frame.shape) == 3:
                thermal_gray = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)
            else:
                thermal_gray = thermal_frame

            rgb_gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)

            # Find checkerboard corners
            logger.info("Finding checkerboard in thermal image...")
            ret_thermal, corners_thermal = cv2.findChessboardCorners(
                thermal_gray, checkerboard_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            )

            logger.info("Finding checkerboard in RGB image...")
            ret_rgb, corners_rgb = cv2.findChessboardCorners(
                rgb_gray, checkerboard_size,
                cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
            )

            if not ret_thermal or not ret_rgb:
                logger.error("Failed to find checkerboard in one or both images")
                logger.info(f"Thermal: {ret_thermal}, RGB: {ret_rgb}")
                return False

            # Refine corner positions
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_thermal = cv2.cornerSubPix(thermal_gray, corners_thermal, (11, 11), (-1, -1), criteria)
            corners_rgb = cv2.cornerSubPix(rgb_gray, corners_rgb, (11, 11), (-1, -1), criteria)

            # Reshape to 2D points
            pts_thermal = corners_thermal.reshape(-1, 2)
            pts_rgb = corners_rgb.reshape(-1, 2)

            # Compute homography (RGB -> Thermal)
            self.homography_matrix, mask = cv2.findHomography(pts_rgb, pts_thermal, cv2.RANSAC, 5.0)

            if self.homography_matrix is None:
                logger.error("Failed to compute homography")
                return False

            logger.info("Calibration successful!")
            logger.info(f"Homography matrix:\n{self.homography_matrix}")
            self.calibration_complete = True

            return True

        except Exception as e:
            logger.error(f"Calibration error: {e}")
            return False

    def calibrate_with_features(self, thermal_frame: np.ndarray,
                                rgb_frame: np.ndarray,
                                min_matches: int = 10) -> bool:
        """
        Calibrate using feature matching (ORB/SIFT)
        Good for scenes with natural features

        Args:
            thermal_frame: Thermal frame (grayscale or BGR)
            rgb_frame: RGB frame (BGR)
            min_matches: Minimum feature matches required

        Returns:
            True if calibration successful
        """
        try:
            # Convert to grayscale
            if len(thermal_frame.shape) == 3:
                thermal_gray = cv2.cvtColor(thermal_frame, cv2.COLOR_BGR2GRAY)
            else:
                thermal_gray = thermal_frame

            rgb_gray = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2GRAY)

            # Detect features using ORB (patent-free)
            orb = cv2.ORB_create(nfeatures=1000)

            logger.info("Detecting features in thermal image...")
            kp_thermal, des_thermal = orb.detectAndCompute(thermal_gray, None)

            logger.info("Detecting features in RGB image...")
            kp_rgb, des_rgb = orb.detectAndCompute(rgb_gray, None)

            if des_thermal is None or des_rgb is None:
                logger.error("Failed to detect features")
                return False

            # Match features
            logger.info("Matching features...")
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des_rgb, des_thermal)
            matches = sorted(matches, key=lambda x: x.distance)

            if len(matches) < min_matches:
                logger.error(f"Not enough matches: {len(matches)} < {min_matches}")
                return False

            logger.info(f"Found {len(matches)} feature matches")

            # Use top matches
            good_matches = matches[:min(50, len(matches))]

            # Extract matched points
            pts_rgb = np.float32([kp_rgb[m.queryIdx].pt for m in good_matches]).reshape(-1, 2)
            pts_thermal = np.float32([kp_thermal[m.trainIdx].pt for m in good_matches]).reshape(-1, 2)

            # Compute homography (RGB -> Thermal)
            self.homography_matrix, mask = cv2.findHomography(pts_rgb, pts_thermal, cv2.RANSAC, 5.0)

            if self.homography_matrix is None:
                logger.error("Failed to compute homography")
                return False

            inliers = mask.sum()
            logger.info(f"Homography computed with {inliers}/{len(good_matches)} inliers")
            logger.info(f"Homography matrix:\n{self.homography_matrix}")
            self.calibration_complete = True

            return True

        except Exception as e:
            logger.error(f"Feature calibration error: {e}")
            return False

    def calibrate_manual(self, thermal_frame: np.ndarray,
                        rgb_frame: np.ndarray,
                        n_points: int = 4) -> bool:
        """
        Manual calibration by clicking corresponding points
        User clicks N points in thermal, then same points in RGB

        Args:
            thermal_frame: Thermal frame (BGR)
            rgb_frame: RGB frame (BGR)
            n_points: Number of points to select (minimum 4)

        Returns:
            True if calibration successful
        """
        self.thermal_points = []
        self.rgb_points = []

        def click_thermal(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                self.thermal_points.append([x, y])
                cv2.circle(param, (x, y), 5, (0, 255, 0), -1)
                cv2.imshow('Thermal - Click Points', param)

        def click_rgb(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                self.rgb_points.append([x, y])
                cv2.circle(param, (x, y), 5, (0, 255, 0), -1)
                cv2.imshow('RGB - Click Points', param)

        try:
            # Select points in thermal
            thermal_display = thermal_frame.copy()
            cv2.imshow('Thermal - Click Points', thermal_display)
            cv2.setMouseCallback('Thermal - Click Points', click_thermal, thermal_display)

            logger.info(f"Click {n_points} corresponding points in THERMAL image, then press any key")

            while len(self.thermal_points) < n_points:
                cv2.waitKey(1)

            cv2.waitKey(0)
            cv2.destroyWindow('Thermal - Click Points')

            # Select corresponding points in RGB
            rgb_display = rgb_frame.copy()
            cv2.imshow('RGB - Click Points', rgb_display)
            cv2.setMouseCallback('RGB - Click Points', click_rgb, rgb_display)

            logger.info(f"Click the SAME {n_points} points in RGB image (in same order), then press any key")

            while len(self.rgb_points) < n_points:
                cv2.waitKey(1)

            cv2.waitKey(0)
            cv2.destroyWindow('RGB - Click Points')

            # Compute homography
            pts_thermal = np.float32(self.thermal_points)
            pts_rgb = np.float32(self.rgb_points)

            self.homography_matrix, _ = cv2.findHomography(pts_rgb, pts_thermal)

            if self.homography_matrix is None:
                logger.error("Failed to compute homography")
                return False

            logger.info("Manual calibration successful!")
            logger.info(f"Homography matrix:\n{self.homography_matrix}")
            self.calibration_complete = True

            return True

        except Exception as e:
            logger.error(f"Manual calibration error: {e}")
            return False

    def test_calibration(self, thermal_frame: np.ndarray,
                        rgb_frame: np.ndarray) -> np.ndarray:
        """
        Test calibration by warping RGB to match thermal

        Args:
            thermal_frame: Thermal frame (reference)
            rgb_frame: RGB frame to warp

        Returns:
            Side-by-side comparison (thermal | warped RGB)
        """
        if not self.calibration_complete or self.homography_matrix is None:
            logger.error("No calibration available")
            return np.hstack([thermal_frame, rgb_frame])

        try:
            # Warp RGB to thermal coordinate system
            h, w = thermal_frame.shape[:2]
            rgb_warped = cv2.warpPerspective(rgb_frame, self.homography_matrix, (w, h))

            # Create side-by-side comparison
            comparison = np.hstack([thermal_frame, rgb_warped])

            # Add labels
            cv2.putText(comparison, "THERMAL", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(comparison, "RGB (WARPED)", (w + 10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            return comparison

        except Exception as e:
            logger.error(f"Test calibration error: {e}")
            return np.hstack([thermal_frame, rgb_frame])

    def save_calibration(self, filename: str) -> bool:
        """
        Save calibration to file

        Args:
            filename: Output JSON file path

        Returns:
            True if successful
        """
        if not self.calibration_complete or self.homography_matrix is None:
            logger.error("No calibration to save")
            return False

        try:
            calib_data = {
                'homography': self.homography_matrix.tolist(),
                'timestamp': time.time()
            }

            with open(filename, 'w') as f:
                json.dump(calib_data, f, indent=2)

            logger.info(f"Calibration saved to {filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            return False

    def load_calibration(self, filename: str) -> bool:
        """
        Load calibration from file

        Args:
            filename: Input JSON file path

        Returns:
            True if successful
        """
        try:
            with open(filename, 'r') as f:
                calib_data = json.load(f)

            self.homography_matrix = np.array(calib_data['homography'], dtype=np.float32)
            self.calibration_complete = True

            logger.info(f"Calibration loaded from {filename}")
            logger.info(f"Homography matrix:\n{self.homography_matrix}")
            return True

        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            return False


def calibration_wizard(thermal_cam, rgb_cam, output_file: str = "camera_calibration.json"):
    """
    Interactive calibration wizard

    Args:
        thermal_cam: Thermal camera object (with read() method)
        rgb_cam: RGB camera object (with read() method)
        output_file: Output calibration file path
    """
    print("="*60)
    print("CAMERA CALIBRATION WIZARD")
    print("="*60)

    calibrator = CameraCalibrator()

    print("\nCalibration Methods:")
    print("1. Checkerboard (recommended - most accurate)")
    print("2. Feature Matching (automatic, works with natural scenes)")
    print("3. Manual Point Selection (flexible, works anywhere)")

    while True:
        choice = input("\nSelect method (1/2/3): ").strip()
        if choice in ['1', '2', '3']:
            break
        print("Invalid choice!")

    # Capture frames
    print("\nCapturing frames...")
    ret_thermal, thermal_frame = thermal_cam.read()
    ret_rgb, rgb_frame = rgb_cam.read()

    if not ret_thermal or not ret_rgb:
        print("ERROR: Failed to capture frames!")
        return False

    print(f"Thermal frame: {thermal_frame.shape}")
    print(f"RGB frame: {rgb_frame.shape}")

    # Show frames
    cv2.imshow("Thermal Frame", thermal_frame)
    cv2.imshow("RGB Frame", rgb_frame)
    cv2.waitKey(1000)

    # Run calibration
    success = False

    if choice == '1':
        print("\nUsing CHECKERBOARD calibration")
        print("Ensure both cameras can see the checkerboard clearly")
        print("Default: 9x6 internal corners")
        input("Press Enter when ready...")

        success = calibrator.calibrate_with_checkerboard(thermal_frame, rgb_frame)

    elif choice == '2':
        print("\nUsing FEATURE MATCHING calibration")
        print("Ensure both cameras see the same scene with distinctive features")
        input("Press Enter to start...")

        success = calibrator.calibrate_with_features(thermal_frame, rgb_frame)

    elif choice == '3':
        print("\nUsing MANUAL calibration")
        print("You will click 4+ corresponding points in both images")
        print("Choose distinctive features visible in both cameras")
        input("Press Enter to start...")

        success = calibrator.calibrate_manual(thermal_frame, rgb_frame, n_points=4)

    if success:
        print("\n✓ Calibration successful!")

        # Test calibration
        print("\nTesting calibration...")
        test_result = calibrator.test_calibration(thermal_frame, rgb_frame)
        cv2.imshow("Calibration Test (Thermal | Warped RGB)", test_result)
        print("Press any key to continue...")
        cv2.waitKey(0)

        # Save calibration
        if calibrator.save_calibration(output_file):
            print(f"\n✓ Calibration saved to: {output_file}")
            print("\nYou can now use this calibration file with fusion_processor.py")
            return True
        else:
            print("\n✗ Failed to save calibration")
            return False
    else:
        print("\n✗ Calibration failed!")
        return False


if __name__ == "__main__":
    """Test calibration with synthetic data"""
    print("="*60)
    print("Camera Calibration Test (Synthetic Data)")
    print("="*60)

    # Create synthetic frames
    thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
    rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Draw test pattern
    for i in range(5):
        for j in range(5):
            x, y = 100 + i*100, 100 + j*80
            cv2.circle(thermal, (x, y), 10, (0, 255, 0), -1)
            cv2.circle(rgb, (x+10, y+5), 10, (0, 255, 0), -1)  # Slight offset

    print("\nTesting manual calibration...")
    calibrator = CameraCalibrator()

    # Simulate manual point selection
    calibrator.thermal_points = [[100, 100], [500, 100], [500, 400], [100, 400]]
    calibrator.rgb_points = [[110, 105], [510, 105], [510, 405], [110, 405]]

    pts_thermal = np.float32(calibrator.thermal_points)
    pts_rgb = np.float32(calibrator.rgb_points)
    calibrator.homography_matrix, _ = cv2.findHomography(pts_rgb, pts_thermal)
    calibrator.calibration_complete = True

    print("Homography matrix:")
    print(calibrator.homography_matrix)

    # Test calibration
    result = calibrator.test_calibration(thermal, rgb)
    cv2.imshow("Calibration Test", result)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # Save/load test
    calibrator.save_calibration("test_calibration.json")
    calibrator2 = CameraCalibrator()
    calibrator2.load_calibration("test_calibration.json")

    print("\nTest complete!")
