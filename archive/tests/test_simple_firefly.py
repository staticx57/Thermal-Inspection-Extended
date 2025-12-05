"""
Simple Firefly camera test - open, capture, display resolution
"""
import sys
import time

print("="*70)
print("SIMPLE FIREFLY TEST")
print("="*70)

try:
    from rgb_camera_firefly import RGBCameraFirefly, PYSPIN_AVAILABLE

    if not PYSPIN_AVAILABLE:
        print("[ERROR] PySpin not available")
        sys.exit(1)

    print("\n[1] Creating Firefly camera with resolution=(1920, 1200)...")
    firefly = RGBCameraFirefly(
        camera_index=0,
        resolution=(1920, 1200),  # Request high resolution
        fps=30,
        pixel_format="BGR8"
    )

    print("[2] Opening camera...")
    if firefly.open():
        print("[OK] Camera opened!")

        actual_res = firefly.get_actual_resolution()
        max_res = firefly.get_max_resolution()

        print(f"\n[INFO] Resolutions:")
        print(f"  Requested: 1920x1200")
        print(f"  Maximum: {max_res[0]}x{max_res[1]}")
        print(f"  Actual: {actual_res[0]}x{actual_res[1]}")

        print(f"\n[3] Capturing test frame...")
        ret, frame = firefly.read()

        if ret and frame is not None:
            print(f"[OK] Frame captured!")
            print(f"  Shape: {frame.shape}")
            print(f"  Dtype: {frame.dtype}")
            megapixels = (frame.shape[1] * frame.shape[0]) / 1_000_000
            print(f"  Megapixels: {megapixels:.2f} MP")
        else:
            print("[ERROR] Failed to capture frame")

        print(f"\n[4] Releasing camera...")
        firefly.release()
        print("[OK] Camera released")

        print("\n" + "="*70)
        print("TEST PASSED")
        print("="*70)

    else:
        print("[ERROR] Failed to open camera")
        print("\nPossible reasons:")
        print("  1. Camera is in use by another application")
        print("  2. Camera was not released from previous test")
        print("  3. Insufficient permissions")
        sys.exit(1)

except Exception as e:
    print(f"\n[ERROR] Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
