#!/usr/bin/env python3
"""
FLIR Boson Camera Detection and Test Utility
Cross-platform: Windows, Linux, macOS

Usage:
    python test_flir_detection.py              # Auto-detect and test
    python test_flir_detection.py --id 0       # Test specific camera
    python test_flir_detection.py --list       # List all cameras
"""
import sys
import argparse
import platform
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_camera_import():
    """Test if required modules are available"""
    print("="*70)
    print("STEP 1: Testing Python modules")
    print("="*70)

    try:
        import cv2
        print(f"[OK] OpenCV installed: {cv2.__version__}")
    except ImportError:
        print("[FAIL] OpenCV not installed!")
        print("\nInstall with: pip install opencv-python")
        return False

    try:
        import numpy as np
        print(f"[OK] NumPy installed: {np.__version__}")
    except ImportError:
        print("[FAIL] NumPy not installed!")
        print("\nInstall with: pip install numpy")
        return False

    print(f"[OK] Platform: {platform.system()} ({platform.machine()})")
    print()
    return True


def list_all_cameras():
    """List all detected cameras"""
    from camera_detector import CameraDetector

    print("="*70)
    print("STEP 2: Detecting cameras")
    print("="*70)

    cameras = CameraDetector.detect_all_cameras()
    CameraDetector.print_camera_list(cameras)

    return cameras


def test_flir_camera(camera_id=None):
    """Test FLIR Boson camera connection"""
    from flir_camera import FLIRBosonCamera
    from camera_detector import CameraDetector
    import cv2
    import time

    print("="*70)
    print("STEP 3: Testing FLIR Boson Camera")
    print("="*70)

    # Auto-detect if not specified
    if camera_id is None:
        print("Auto-detecting FLIR Boson camera...")
        flir_cam = CameraDetector.find_flir_boson()
        if flir_cam:
            camera_id = flir_cam.device_id
            print(f"[OK] Found FLIR Boson: {flir_cam}")
        else:
            print("[FAIL] No FLIR Boson camera detected!")
            print("\nTroubleshooting:")
            print("  1. Check USB connection")
            print("  2. For FLIR Boson via USB adapter: install UVC drivers")
            print("  3. On Windows: check Device Manager")
            print("  4. Try listing all cameras with --list")
            return False

    # Test camera
    print(f"\nOpening camera {camera_id}...")

    # Try both resolutions (640x512 and 320x256)
    resolutions = [(640, 512), (320, 256)]

    for resolution in resolutions:
        print(f"\nTrying resolution: {resolution[0]}x{resolution[1]}")

        camera = FLIRBosonCamera(device_id=camera_id, resolution=resolution)

        if camera.open():
            actual_res = camera.get_actual_resolution()
            print(f"[OK] Camera opened successfully!")
            print(f"  Device ID: {camera_id}")
            print(f"  Requested: {resolution[0]}x{resolution[1]}")
            print(f"  Actual: {actual_res[0]}x{actual_res[1]}")

            # Test frame capture
            print("\nTesting frame capture (10 frames)...")
            success_count = 0

            for i in range(10):
                ret, frame = camera.read()
                if ret and frame is not None:
                    success_count += 1
                    print(f"  Frame {i+1}: {frame.shape} ({frame.dtype})")
                else:
                    print(f"  Frame {i+1}: FAILED")

            print(f"\nCapture success rate: {success_count}/10")

            if success_count >= 8:
                print("\n[OK] Camera is working correctly!")

                # Live preview test
                print("\nLive preview test (press 'q' to quit, 's' to save screenshot)...")
                print("This will display thermal video for 30 seconds or until you press 'q'")

                cv2.namedWindow("FLIR Boson Test", cv2.WINDOW_NORMAL)

                frame_count = 0
                start_time = time.time()

                while True:
                    ret, frame = camera.read()

                    if not ret:
                        print("Failed to read frame")
                        break

                    # Calculate FPS
                    frame_count += 1
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0

                    # Add FPS text
                    display_frame = frame.copy()
                    cv2.putText(display_frame, f"FPS: {fps:.1f}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    cv2.putText(display_frame, f"Resolution: {frame.shape[1]}x{frame.shape[0]}", (10, 70),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(display_frame, "Press 'q' to quit, 's' to save", (10, 110),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                    cv2.imshow("FLIR Boson Test", display_frame)

                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        print("\nQuitting preview...")
                        break
                    elif key == ord('s'):
                        from datetime import datetime
                        filename = f"flir_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        cv2.imwrite(filename, frame)
                        print(f"\nScreenshot saved: {filename}")

                    # Auto-quit after 30 seconds
                    if elapsed > 30:
                        print("\n30 second test complete")
                        break

                cv2.destroyAllWindows()
                camera.release()

                print("\n" + "="*70)
                print("FLIR BOSON TEST COMPLETE - CAMERA IS WORKING!")
                print("="*70)
                print(f"\nCamera details:")
                print(f"  Device ID: {camera_id}")
                print(f"  Resolution: {actual_res[0]}x{actual_res[1]}")
                print(f"  Average FPS: {fps:.1f}")
                print(f"  Platform: {platform.system()}")
                print("\nYou can now run the main application:")
                print(f"  python main.py --camera-id {camera_id} --width {actual_res[0]} --height {actual_res[1]}")
                print("="*70)
                return True

            else:
                print("\n[FAIL] Camera opened but frame capture is unreliable")
                camera.release()
        else:
            print(f"[FAIL] Failed to open camera with resolution {resolution[0]}x{resolution[1]}")

    print("\n[FAIL] Camera test failed!")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="FLIR Boson Camera Detection and Test Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_flir_detection.py              # Auto-detect and test
  python test_flir_detection.py --id 0       # Test camera ID 0
  python test_flir_detection.py --list       # List all cameras
        """
    )

    parser.add_argument('--id', type=int, default=None,
                       help='Camera device ID to test (auto-detect if not specified)')
    parser.add_argument('--list', action='store_true',
                       help='List all detected cameras and exit')

    args = parser.parse_args()

    print("""
==================================================================
          FLIR Boson Camera Detection & Test Utility
==================================================================
  This tool will:
    1. Check Python dependencies
    2. Detect all connected cameras
    3. Test FLIR Boson camera functionality
    4. Display live thermal preview
==================================================================
    """)

    # Step 1: Test imports
    if not test_camera_import():
        print("\n[ERROR] Module import test failed!")
        print("\nInstall required modules:")
        print("  pip install opencv-python numpy")
        sys.exit(1)

    # Step 2: List cameras
    cameras = list_all_cameras()

    if args.list:
        print("\nCamera list complete. Use --id <N> to test a specific camera.")
        sys.exit(0)

    if not cameras:
        print("\n[ERROR] No cameras detected!")
        print("\nTroubleshooting:")
        print("  1. Check camera USB connection")
        print("  2. On Windows: check Device Manager > Imaging devices")
        print("  3. Try a different USB port (USB 3.0 recommended)")
        print("  4. For FLIR Boson: ensure UVC driver is installed")
        sys.exit(1)

    # Step 3: Test camera
    success = test_flir_camera(camera_id=args.id)

    if success:
        print("\n[SUCCESS] FLIR Boson camera is working correctly!")
        sys.exit(0)
    else:
        print("\n[FAILED] Camera test was unsuccessful.")
        print("\nTroubleshooting:")
        print("  1. Try a different camera ID with --id <N>")
        print("  2. Check camera is not in use by another application")
        print("  3. On Windows: close Skype, Teams, or other apps using camera")
        print("  4. Restart camera or reconnect USB cable")
        sys.exit(1)


if __name__ == "__main__":
    main()
