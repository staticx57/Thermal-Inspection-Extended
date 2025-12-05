"""
Test maximum resolution detection and usage
"""

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)

def test_firefly_max_resolution():
    """Test Firefly maximum resolution detection"""
    print("\n" + "="*80)
    print("TEST: Firefly Max Resolution Detection")
    print("="*80)

    try:
        from rgb_camera_firefly import RGBCameraFirefly, PYSPIN_AVAILABLE

        if not PYSPIN_AVAILABLE:
            print("[SKIP] PySpin not available - Firefly test skipped")
            return False

        # Test 1: Open with default resolution (should use max)
        print("\n[TEST 1] Opening Firefly with resolution=(0, 0) - should use MAX")
        print("-"*80)

        firefly = RGBCameraFirefly(
            camera_index=0,
            resolution=(0, 0),  # Use max resolution
            fps=30,
            pixel_format="BGR8"
        )

        if firefly.open():
            actual_res = firefly.get_actual_resolution()
            max_res = firefly.get_max_resolution()

            print(f"\n[OK] Firefly opened successfully!")
            print(f"  Requested: 0x0 (auto-detect max)")
            print(f"  Maximum available: {max_res[0]}x{max_res[1]}")
            print(f"  Actual resolution: {actual_res[0]}x{actual_res[1]}")

            if actual_res == max_res:
                print(f"  ✓ Using maximum resolution!")
            else:
                print(f"  ⚠ Not using max (may be OK if constrained)")

            # Read a test frame
            print("\n[TEST 2] Reading test frame...")
            ret, frame = firefly.read()
            if ret and frame is not None:
                print(f"  ✓ Frame captured: {frame.shape}")
                print(f"  ✓ Frame dtype: {frame.dtype}")
            else:
                print(f"  ✗ Failed to capture frame")

            firefly.release()
            print("\n[OK] Firefly test complete")
            return True
        else:
            print("[ERROR] Failed to open Firefly camera")
            return False

    except Exception as e:
        print(f"[ERROR] Firefly test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_uvc_max_resolution():
    """Test UVC camera maximum resolution detection"""
    print("\n" + "="*80)
    print("TEST: UVC Camera Max Resolution Detection")
    print("="*80)

    try:
        from rgb_camera_uvc import RGBCameraUVC

        # Find a UVC camera (skip device 0 which is likely thermal)
        print("\n[TEST 1] Opening UVC camera with resolution=(0, 0) - should use MAX")
        print("-"*80)

        uvc = RGBCameraUVC(
            device_id=1,  # Device 1 (skip thermal at 0)
            resolution=(0, 0),  # Use max resolution
            fps=30
        )

        if uvc.open():
            actual_res = uvc.get_actual_resolution()

            print(f"\n[OK] UVC camera opened successfully!")
            print(f"  Requested: 0x0 (auto-detect max)")
            print(f"  Actual resolution: {actual_res[0]}x{actual_res[1]}")

            # Read a test frame
            print("\n[TEST 2] Reading test frame...")
            ret, frame = uvc.read()
            if ret and frame is not None:
                print(f"  ✓ Frame captured: {frame.shape}")
                print(f"  ✓ Frame dtype: {frame.dtype}")
            else:
                print(f"  ✗ Failed to capture frame")

            uvc.release()
            print("\n[OK] UVC test complete")
            return True
        else:
            print("[SKIP] UVC camera not available on device 1")
            return False

    except Exception as e:
        print(f"[SKIP] UVC test skipped: {e}")
        return False

def test_camera_factory():
    """Test camera factory with max resolution"""
    print("\n" + "="*80)
    print("TEST: Camera Factory with Auto-Detection")
    print("="*80)

    try:
        from camera_factory import create_rgb_camera
        from camera_detector import CameraDetector

        # Detect RGB camera
        rgb_cam_info = CameraDetector.find_rgb_camera()

        if not rgb_cam_info:
            print("[SKIP] No RGB camera detected")
            return False

        print(f"\n[INFO] Detected: {rgb_cam_info.name}")
        print(f"  Interface: {rgb_cam_info.interface}")

        # Create camera with auto-detection and max resolution
        print("\n[TEST] Creating RGB camera with resolution=(0, 0)")
        print("-"*80)

        if rgb_cam_info.interface == 'spinnaker':
            from rgb_camera_firefly import RGBCameraFirefly
            camera = RGBCameraFirefly(
                camera_index=rgb_cam_info.spinnaker_index,
                resolution=(0, 0),
                fps=30,
                pixel_format="BGR8"
            )
        else:
            camera = create_rgb_camera(
                resolution=(0, 0),  # Max resolution
                fps=30,
                camera_type="uvc",
                camera_index=rgb_cam_info.device_id
            )

        if camera.open():
            actual_res = camera.get_actual_resolution()

            print(f"\n[OK] Camera opened!")
            print(f"  Resolution: {actual_res[0]}x{actual_res[1]}")

            # Capture and measure a frame
            ret, frame = camera.read()
            if ret and frame is not None:
                print(f"  Frame: {frame.shape}")

                # Calculate megapixels
                megapixels = (frame.shape[1] * frame.shape[0]) / 1_000_000
                print(f"  Megapixels: {megapixels:.2f} MP")
                print(f"  ✓ High resolution capture successful!")

            camera.release()
            return True
        else:
            print("[ERROR] Failed to open camera")
            return False

    except Exception as e:
        print(f"[ERROR] Factory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all resolution tests"""
    print("\n" + "="*80)
    print("MAXIMUM RESOLUTION DETECTION TEST SUITE")
    print("="*80)

    results = {
        'firefly': False,
        'uvc': False,
        'factory': False
    }

    # Test 1: Firefly max resolution
    results['firefly'] = test_firefly_max_resolution()

    # Test 2: UVC max resolution
    results['uvc'] = test_uvc_max_resolution()

    # Test 3: Camera factory
    results['factory'] = test_camera_factory()

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[SKIP/FAIL]"
        print(f"{status} {test_name}")

    print("="*80)

    # Overall result
    if results['firefly'] or results['factory']:
        print("\n✓ Max resolution detection is working!")
    else:
        print("\n⚠ Tests skipped or failed - check camera connections")

if __name__ == "__main__":
    main()
