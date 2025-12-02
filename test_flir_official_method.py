#!/usr/bin/env python3
"""
Test FLIR's official method for 16-bit Y16 capture on Windows.
Based on official FLIR documentation: boson16bit.txt
"""
import sys
import time
import cv2
import numpy as np
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')

from boson_sdk_wrapper import BosonSDK

print("="*70)
print("FLIR Official Method: 16-bit Y16 Capture on Windows")
print("="*70)
print("\nBased on official FLIR documentation")
print("Source: FLIR OEM Support - Boson Video and Image Capture using OpenCV")
print("="*70)

# Step 1: Configure camera via SDK (BEFORE opening video)
print("\n[Step 1] Configuring camera via SDK...")
print("  (This must happen BEFORE opening video capture)")

sdk = BosonSDK(com_port='COM7')
if not sdk.open():
    print("[ERROR] Failed to open SDK")
    sys.exit(1)

print("  [OK] SDK connected")
cam = sdk.camera

# Configure for radiometric capture
print("\n[Step 2] Setting radiometric parameters...")

try:
    # Import SDK enums
    sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection\3.0 IDD & SDK\SDK_USER_PERMISSIONS\SDK_USER_PERMISSIONS')
    from ClientFiles_Python.EnumTypes import (
        FLR_BOSON_GAINMODE_E,
        FLR_ENABLE_E,
        FLR_SYSCTRL_USBIR16_MODE_E
    )

    # Set gain mode (HIGH for normal temps, LOW for >120°C)
    print("  Setting HIGH gain mode...")
    cam.bosonSetGainMode(FLR_BOSON_GAINMODE_E.FLR_BOSON_HIGH_GAIN)

    # Enable T-Linear
    print("  Enabling T-Linear...")
    cam.TLinearSetControl(FLR_ENABLE_E.FLR_ENABLE)

    # Set USB IR16 mode to T-Linear (THIS IS THE KEY!)
    print("  Setting USB Video IR16 mode to T-Linear...")
    cam.sysctrlSetUsbVideoIR16Mode(FLR_SYSCTRL_USBIR16_MODE_E.FLR_SYSCTRL_USBIR16_MODE_TLINEAR)

    # Set transmission window (100% = no window)
    print("  Setting transmission window to 100%...")
    cam.radiometrySetTransmissionWindow(100)

    # Refresh LUT
    print("  Refreshing T-Linear LUT...")
    cam.TLinearRefreshLUT(FLR_BOSON_GAINMODE_E.FLR_BOSON_HIGH_GAIN)

    # Run FFC
    print("  Running FFC...")
    cam.bosonRunFFC()

    print("  [SUCCESS] Camera configured for radiometric capture")

except Exception as e:
    print(f"  [ERROR] SDK configuration failed: {e}")
    import traceback
    traceback.print_exc()
    sdk.close()
    sys.exit(1)

# Close SDK
sdk.close()
print("  SDK closed (settings persist in camera)")

# Wait for camera to settle
print("\n[Step 3] Waiting for camera to settle...")
time.sleep(1.0)

# Step 2: Open video capture using FLIR's exact method
print("\n[Step 4] Opening video capture using FLIR's method...")
print("  CRITICAL: Following FLIR's exact sequence!")

device_index = 1

# FLIR's exact sequence:
print("  1. Creating VideoCapture with DirectShow backend...")
cap = cv2.VideoCapture(device_index + cv2.CAP_DSHOW)

if not cap.isOpened():
    print("[ERROR] Failed to open video capture")
    sys.exit(1)

print("  2. Setting frame dimensions...")
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)  # Boson 640
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)

print("  3. Setting FOURCC to Y16...")
result = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y', '1', '6', ' '))
print(f"     FOURCC set result: {result}")

print("  4. Disabling RGB conversion...")
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)

# Verify settings
fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
print(f"\n  Verified settings:")
print(f"    Width: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}")
print(f"    Height: {int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
print(f"    FOURCC: '{fourcc_str}' ({fourcc})")
print(f"    Convert RGB: {cap.get(cv2.CAP_PROP_CONVERT_RGB)}")

# Step 3: Capture frames
print("\n[Step 5] Capturing test frames...")
time.sleep(0.5)

for i in range(5):
    ret, frame = cap.read()

    if ret and frame is not None:
        print(f"\n  Frame {i+1}:")
        print(f"    dtype: {frame.dtype}")
        print(f"    shape: {frame.shape}")
        print(f"    min: {frame.min()}")
        print(f"    max: {frame.max()}")
        print(f"    mean: {frame.mean():.2f}")

        if frame.dtype == np.uint16:
            print(f"    ✓ SUCCESS: TRUE 16-BIT RADIOMETRIC DATA!")

            # Calculate temperature for center pixel (FLIR's formula)
            h, w = frame.shape[:2]
            center_val = frame[h//2, w//2]
            # High gain: temp_c = (pixel_val / 100) - 273
            temp_c = (center_val / 100.0) - 273.15
            temp_f = temp_c * 9/5 + 32
            print(f"    Center pixel: {center_val} counts = {temp_c:.1f}°C ({temp_f:.1f}°F)")
        else:
            print(f"    ✗ Still {frame.dtype} - not 16-bit")

        time.sleep(0.1)
    else:
        print(f"  Frame {i+1}: Failed to capture")

cap.release()
print("\n[Step 6] Video capture released")

print("\n" + "="*70)
print("Test Complete")
print("="*70)

if frame is not None and frame.dtype == np.uint16:
    print("\n✓✓✓ SUCCESS! ✓✓✓")
    print("16-bit Y16 radiometric capture is working on Windows!")
    print("\nKey factors:")
    print("  1. SDK configuration BEFORE video capture")
    print("  2. sysctrlSetUsbVideoIR16Mode(TLINEAR)")
    print("  3. Proper DirectShow initialization sequence")
    print("  4. Camera had time to settle after SDK config")
else:
    print("\nStill capturing 8-bit data.")
    print("\nPossible issues:")
    print("  1. Camera may need power cycle after SDK configuration")
    print("  2. Check if device_index=1 is correct Boson device")
    print("  3. Try closing all other applications using the camera")

print("="*70)
