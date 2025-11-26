"""
Test script for robust camera detection
Tests the enhanced camera_detector.py with Spinnaker support
"""

import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)-8s | %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    """Test camera detection"""
    print("\n" + "="*80)
    print("CAMERA DETECTION TEST")
    print("="*80 + "\n")

    try:
        from camera_detector import CameraDetector

        # Test 1: Detect all cameras
        print("\n[TEST 1] Detecting all cameras...")
        print("-"*80)
        cameras = CameraDetector.detect_all_cameras()

        if not cameras:
            print("\n[WARN] No cameras detected!")
            print("\nPossible reasons:")
            print("  1. No cameras are connected")
            print("  2. Camera drivers not installed")
            print("  3. Cameras in use by another application")
            return

        # Test 2: Find best thermal camera
        print("\n[TEST 2] Finding best thermal camera...")
        print("-"*80)
        thermal_cam = CameraDetector.find_thermal_camera()

        if thermal_cam:
            print(f"\n[OK] THERMAL CAMERA SELECTED:")
            print(f"  Name: {thermal_cam.name}")
            print(f"  Interface: {thermal_cam.interface}")
            print(f"  Priority: {thermal_cam.priority}")
            if thermal_cam.interface == 'spinnaker':
                print(f"  Spinnaker Index: {thermal_cam.spinnaker_index}")
                print(f"  Serial: {thermal_cam.serial}")
            else:
                print(f"  Device ID: {thermal_cam.device_id}")
                print(f"  Resolution: {thermal_cam.resolution}")
        else:
            print("\n[WARN] No thermal camera found")

        # Test 3: Find best RGB camera
        print("\n[TEST 3] Finding best RGB camera...")
        print("-"*80)
        rgb_cam = CameraDetector.find_rgb_camera()

        if rgb_cam:
            print(f"\n[OK] RGB CAMERA SELECTED:")
            print(f"  Name: {rgb_cam.name}")
            print(f"  Interface: {rgb_cam.interface}")
            print(f"  Priority: {rgb_cam.priority}")
            if rgb_cam.interface == 'spinnaker':
                print(f"  Spinnaker Index: {rgb_cam.spinnaker_index}")
                print(f"  Serial: {rgb_cam.serial}")
            else:
                print(f"  Device ID: {rgb_cam.device_id}")
                print(f"  Resolution: {rgb_cam.resolution}")
        else:
            print("\n[WARN] No RGB camera found")

        # Test 4: Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total cameras detected: {len(cameras)}")
        print("\nNote: RGB and thermal cameras are graded SEPARATELY with COEQUAL importance")
        print("      Priority numbers only meaningful within each category\n")
        if thermal_cam:
            thermal_priority_label = {
                0: "FLIR Boson - BEST",
                1: "Generic thermal - GOOD"
            }.get(thermal_cam.priority, "Unknown")
            print(f"[OK] Thermal camera: {thermal_cam.name} [{thermal_priority_label}]")
            print(f"     (Thermal priority {thermal_cam.priority})")
        else:
            print("[X] No thermal camera")

        if rgb_cam:
            priority_label = {
                0: "Firefly (Spinnaker) - BEST",
                1: "External USB - GOOD",
                2: "Built-in webcam - OK"
            }.get(rgb_cam.priority, "Unknown")
            print(f"[OK] RGB camera: {rgb_cam.name} [{priority_label}]")
            print(f"     (RGB priority {rgb_cam.priority} - graded separately from thermal)")
        else:
            print("[X] No RGB camera")

        print("="*80 + "\n")

        # Test 5: Verify no conflicts
        if thermal_cam and rgb_cam:
            if thermal_cam.interface == 'opencv' and rgb_cam.interface == 'opencv':
                if thermal_cam.device_id == rgb_cam.device_id:
                    print("[WARN] WARNING: Thermal and RGB assigned to same device!")
                    print(f"  Both using device {thermal_cam.device_id}")
                else:
                    print("[OK] No device ID conflicts")
            else:
                print("[OK] Different interfaces - no conflicts possible")

    except ImportError as e:
        print(f"\n[ERROR] Failed to import camera_detector: {e}")
        print("\nMake sure camera_detector.py and camera_registry.py are in the same directory")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
