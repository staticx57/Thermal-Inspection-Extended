#!/usr/bin/env python3
"""
Test different property setting orders for Y16 capture.

Based on OpenCV PR #12454 finding:
"If the user selects Y16 via CAP_PROP_FOURCC, DirectShow retrieves a 16-bit
image but it is implicitly converted to a grey RGB image unless the user sets
CV_CAP_PROP_CONVERT_RGB to false."

This script tests different orders of setting CAP_PROP_CONVERT_RGB to find
if order matters for Y16 capture.
"""

import cv2
import numpy as np
import sys

def print_frame_info(frame, test_name):
    """Print detailed frame information."""
    if frame is None:
        print(f"{test_name}: FAILED - No frame captured")
        return False

    print(f"\n{test_name}:")
    print(f"  dtype: {frame.dtype}")
    print(f"  shape: {frame.shape}")
    print(f"  min value: {frame.min()}")
    print(f"  max value: {frame.max()}")

    # Check if 16-bit
    is_16bit = frame.dtype == np.uint16
    is_grayscale = len(frame.shape) == 2

    print(f"  16-bit? {is_16bit}")
    print(f"  Grayscale? {is_grayscale}")

    if is_16bit and is_grayscale:
        print(f"  ✓ SUCCESS - Got 16-bit Y16!")
        return True
    else:
        print(f"  ✗ FAILED - Still 8-bit or color")
        return False


def test_1_convert_before_fourcc():
    """Test 1: Set CONVERT_RGB before FOURCC."""
    print("\n" + "="*70)
    print("TEST 1: Set CAP_PROP_CONVERT_RGB BEFORE CAP_PROP_FOURCC")
    print("="*70)

    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    # Order: CONVERT_RGB first
    result1 = cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)  # 0.0 = False for double
    print(f"Set CONVERT_RGB: {result1}")

    result2 = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
    print(f"Set FOURCC: {result2}")

    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

    # Read actual FOURCC
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"Actual FOURCC: '{fourcc_str}'")

    ret, frame = cap.read()
    cap.release()

    if ret:
        return print_frame_info(frame, "Test 1")
    else:
        print("Failed to capture frame")
        return False


def test_2_convert_after_fourcc():
    """Test 2: Set CONVERT_RGB after FOURCC."""
    print("\n" + "="*70)
    print("TEST 2: Set CAP_PROP_CONVERT_RGB AFTER CAP_PROP_FOURCC")
    print("="*70)

    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    # Order: FOURCC first
    result1 = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
    print(f"Set FOURCC: {result1}")

    result2 = cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)  # 0.0 = False for double
    print(f"Set CONVERT_RGB: {result2}")

    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

    # Read actual FOURCC
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"Actual FOURCC: '{fourcc_str}'")

    ret, frame = cap.read()
    cap.release()

    if ret:
        return print_frame_info(frame, "Test 2")
    else:
        print("Failed to capture frame")
        return False


def test_3_convert_rgb_as_zero():
    """Test 3: Set CONVERT_RGB as 0 instead of False."""
    print("\n" + "="*70)
    print("TEST 3: Set CAP_PROP_CONVERT_RGB as 0 (integer) instead of False")
    print("="*70)

    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    result1 = cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)  # 0.0 as double
    print(f"Set CONVERT_RGB: {result1}")

    result2 = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
    print(f"Set FOURCC: {result2}")

    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

    # Read actual FOURCC
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"Actual FOURCC: '{fourcc_str}'")

    ret, frame = cap.read()
    cap.release()

    if ret:
        return print_frame_info(frame, "Test 3")
    else:
        print("Failed to capture frame")
        return False


def test_4_reopen_after_setting():
    """Test 4: Reopen capture after setting properties."""
    print("\n" + "="*70)
    print("TEST 4: Set properties, then reopen capture")
    print("="*70)

    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

    # Release and reopen
    cap.release()

    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))

    # Read actual FOURCC
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"Actual FOURCC: '{fourcc_str}'")

    ret, frame = cap.read()
    cap.release()

    if ret:
        return print_frame_info(frame, "Test 4")
    else:
        print("Failed to capture frame")
        return False


def test_5_set_all_at_once():
    """Test 5: Open with index only, set all properties immediately."""
    print("\n" + "="*70)
    print("TEST 5: Open without backend, then set all properties")
    print("="*70)

    cap = cv2.VideoCapture(1)  # No explicit backend

    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

    # Read actual FOURCC
    actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"Actual FOURCC: '{fourcc_str}'")

    # Check backend
    backend = cap.getBackendName()
    print(f"Backend: {backend}")

    ret, frame = cap.read()
    cap.release()

    if ret:
        return print_frame_info(frame, "Test 5")
    else:
        print("Failed to capture frame")
        return False


def main():
    """Run all tests."""
    print("="*70)
    print("OpenCV Y16 Capture - Property Order Tests")
    print("="*70)
    print(f"OpenCV version: {cv2.__version__}")
    print(f"Device: FLIR Boson 640 (device_id=1)")
    print(f"Target: 16-bit Y16 grayscale (dtype=uint16, shape=(512, 640))")

    results = {}

    # Run all tests
    results['Test 1'] = test_1_convert_before_fourcc()
    results['Test 2'] = test_2_convert_after_fourcc()
    results['Test 3'] = test_3_convert_rgb_as_zero()
    results['Test 4'] = test_4_reopen_after_setting()
    results['Test 5'] = test_5_set_all_at_once()

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    any_success = False
    for test_name, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{test_name}: {status}")
        if success:
            any_success = True

    print("\n" + "="*70)
    if any_success:
        print("RESULT: At least one method achieved 16-bit Y16 capture!")
        print("Check successful test(s) above for the working configuration.")
    else:
        print("RESULT: All tests failed to achieve 16-bit Y16 capture.")
        print("\nPossible reasons:")
        print("  1. OpenCV version issue (try 4.6.0)")
        print("  2. Windows 11 DirectShow limitation")
        print("  3. Missing FLIR DirectShow filter")
        print("  4. Camera firmware/configuration issue")
        print("\nNext steps:")
        print("  - Test with OpenCV 4.6.0 + Python 3.7.9")
        print("  - Test on Windows 10 machine")
        print("  - Implement direct USB capture")
    print("="*70)


if __name__ == "__main__":
    main()
