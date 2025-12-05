#!/usr/bin/env python3
"""
Quick test for OpenCV 4.9.0 - specifically targeting the MSMF backend.

Based on GitHub issue #27166 which confirms OpenCV 4.9.0.80 works for
FLIR Boson 16-bit capture, while 4.11+ has a flattening bug.

This test focuses on the MSMF (MediaFoundation) backend which showed
promise in our previous Test 5 (got data but flattened).
"""

import cv2
import numpy as np
import sys

print("="*70)
print("OpenCV 4.9.0 Quick Test for Y16 16-bit Capture")
print("="*70)
print(f"OpenCV version: {cv2.__version__}")
print(f"Python version: {sys.version}")
print()

if not cv2.__version__.startswith("4.9.0"):
    print("⚠ WARNING: This test is designed for OpenCV 4.9.0")
    print(f"   You are running: {cv2.__version__}")
    print()
    response = input("Continue anyway? (y/n): ").lower().strip()
    if response != 'y':
        print("Aborted.")
        sys.exit(0)

print("Target: FLIR Boson 640")
print("Expected: dtype=uint16, shape=(512, 640)")
print()

# ============================================================================
# Test 1: MSMF Backend (Auto-select)
# ============================================================================
print("="*70)
print("TEST 1: Auto Backend (should select MSMF on Windows)")
print("="*70)

cap = cv2.VideoCapture(1)  # No explicit backend - let it choose

# Set properties
print("Setting properties...")
result1 = cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)  # Critical for 16-bit
print(f"  CAP_PROP_CONVERT_RGB: {result1}")

result2 = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
print(f"  CAP_PROP_FOURCC: {result2}")

cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

# Check backend
backend = cap.getBackendName()
print(f"\nBackend selected: {backend}")

# Get actual FOURCC
actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
print(f"Actual FOURCC: '{fourcc_str}'")

# Capture frame
print("\nCapturing frame...")
ret, frame = cap.read()

if not ret:
    print("✗ FAILED: Could not capture frame")
    cap.release()
    sys.exit(1)

# Analyze frame
print("\nFrame Analysis:")
print(f"  dtype: {frame.dtype}")
print(f"  shape: {frame.shape}")
print(f"  size: {frame.size}")
print(f"  ndim: {frame.ndim}")
print(f"  min: {frame.min()}")
print(f"  max: {frame.max()}")

# Check success
is_16bit = frame.dtype == np.uint16
is_2d = len(frame.shape) == 2
is_correct_size = frame.shape == (512, 640) if is_2d else False
has_16bit_range = frame.max() > 255

print("\nSuccess Criteria:")
print(f"  16-bit (uint16): {is_16bit} {'✓' if is_16bit else '✗'}")
print(f"  2D shape: {is_2d} {'✓' if is_2d else '✗'}")
print(f"  Correct size (512, 640): {is_correct_size} {'✓' if is_correct_size else '✗'}")
print(f"  16-bit range (>255): {has_16bit_range} {'✓' if has_16bit_range else '✗'}")

if is_16bit and is_2d and is_correct_size:
    print("\n" + "="*70)
    print("✓✓✓ SUCCESS! Got 16-bit Y16 capture!")
    print("="*70)

    # Temperature conversion (for reference)
    center_val = frame[256, 320]
    temp_k = center_val / 100.0
    temp_c = temp_k - 273.15
    temp_f = temp_c * 9/5 + 32

    print(f"\nCenter pixel value: {center_val}")
    print(f"  Temperature: {temp_c:.1f}°C ({temp_f:.1f}°F)")
    print(f"  Formula: (pixel / 100.0) - 273.15")

    test1_success = True
else:
    print("\n" + "="*70)
    print("✗ Test 1 Failed")
    print("="*70)
    test1_success = False

cap.release()

# ============================================================================
# Test 2: Explicit DirectShow Backend (for comparison)
# ============================================================================
print("\n\n" + "="*70)
print("TEST 2: DirectShow Backend (for comparison)")
print("="*70)

cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

print("Setting properties...")
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

backend = cap.getBackendName()
print(f"Backend: {backend}")

actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
print(f"Actual FOURCC: '{fourcc_str}'")

ret, frame = cap.read()

if ret:
    print(f"\nFrame: dtype={frame.dtype}, shape={frame.shape}")

    is_16bit = frame.dtype == np.uint16
    is_2d = len(frame.shape) == 2
    is_correct_size = frame.shape == (512, 640) if is_2d else False

    if is_16bit and is_2d and is_correct_size:
        print("✓ DirectShow also works!")
        test2_success = True
    else:
        print("✗ DirectShow failed (expected on Windows 11)")
        test2_success = False
else:
    print("✗ Could not capture with DirectShow")
    test2_success = False

cap.release()

# ============================================================================
# Test 3: Explicit MSMF Backend
# ============================================================================
print("\n\n" + "="*70)
print("TEST 3: Explicit MSMF (MediaFoundation) Backend")
print("="*70)

cap = cv2.VideoCapture(1, cv2.CAP_MSMF)

print("Setting properties...")
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y','1','6',' '))
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

backend = cap.getBackendName()
print(f"Backend: {backend}")

actual_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join([chr((actual_fourcc >> 8 * i) & 0xFF) for i in range(4)])
print(f"Actual FOURCC: '{fourcc_str}'")

ret, frame = cap.read()

if ret:
    print(f"\nFrame: dtype={frame.dtype}, shape={frame.shape}")

    is_16bit = frame.dtype == np.uint16
    is_2d = len(frame.shape) == 2
    is_correct_size = frame.shape == (512, 640) if is_2d else False

    if is_16bit and is_2d and is_correct_size:
        print("✓ MSMF works!")
        test3_success = True
    else:
        print("✗ MSMF failed")
        test3_success = False
else:
    print("✗ Could not capture with MSMF")
    test3_success = False

cap.release()

# ============================================================================
# Summary
# ============================================================================
print("\n\n" + "="*70)
print("SUMMARY")
print("="*70)

results = {
    "Test 1 (Auto/MSMF)": test1_success,
    "Test 2 (DirectShow)": test2_success,
    "Test 3 (Explicit MSMF)": test3_success
}

for test_name, success in results.items():
    status = "✓ SUCCESS" if success else "✗ FAILED"
    print(f"{test_name}: {status}")

print("\n" + "="*70)

if any(results.values()):
    print("RESULT: At least one backend achieved 16-bit Y16 capture!")
    print("\nOpenCV 4.9.0 SOLVES THE PROBLEM! 🎉")
    print("\nNext steps:")
    print("1. Use OpenCV 4.9.0 for your thermal camera work")
    print("2. Or wait for OpenCV 4.12.0 (has fix for 4.11 bug)")
    print("3. Update flir_camera.py to use working backend/settings")
else:
    print("RESULT: All backends failed.")
    print("\nThis is unexpected for OpenCV 4.9.0 based on GitHub issue #27166")
    print("\nPossible reasons:")
    print("1. Windows 11 limitation affects all backends")
    print("2. Camera configuration issue")
    print("3. Different camera model than issue reporter")
    print("\nNext steps:")
    print("1. Try OpenCV 4.8.0 or 4.7.0 (older versions)")
    print("2. Implement direct USB capture (guaranteed to work)")
    print("3. Test on Windows 10 machine")

print("="*70)

# ============================================================================
# Additional Info
# ============================================================================
print("\n" + "="*70)
print("CONTEXT")
print("="*70)
print("\nGitHub Issue #27166:")
print("  - Reports FLIR Boson works with OpenCV 4.9.0.80")
print("  - OpenCV 4.11+ has flattening bug (frames become 1D arrays)")
print("  - Fix merged for OpenCV 4.12.0")
print("\nYour Previous Tests:")
print("  - OpenCV 4.11.0: All tests failed")
print("  - OpenCV 4.6.0: All tests failed")
print("  - Test 5 (MSMF) got data but flattened: (1, 460800)")
print("\nThis Test:")
print(f"  - OpenCV {cv2.__version__}")
print("  - Focuses on MSMF backend")
print("  - Expects proper 2D arrays without flattening bug")
print("\n" + "="*70)
