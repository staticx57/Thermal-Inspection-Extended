#!/usr/bin/env python3
"""
Test power cycle approach - configure SDK, close everything, then capture.
This simulates what happens when FLIR app starts fresh.
"""
import sys
import time
import cv2
import numpy as np
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')

from boson_sdk_wrapper import BosonSDK

print("="*70)
print("Power Cycle Test: Configure, Close ALL, Then Capture")
print("="*70)

# Phase 1: Configure camera ONLY
print("\n[PHASE 1] Configure camera via SDK")
print("  Opening SDK...")

sdk = BosonSDK(com_port='COM7')
if not sdk.open():
    print("ERROR: Failed to open SDK")
    sys.exit(1)

cam = sdk.camera

print("  Getting camera info...")
try:
    result, sn = cam.bosonGetCameraSN()
    print(f"    Serial Number: {sn}")

    result, major, minor, patch = cam.bosonGetSoftwareRev()
    print(f"    Firmware: {major}.{minor}.{patch}")

    result, pn = cam.bosonGetCameraPN()
    print(f"    Part Number: {pn}")
except:
    print("    Info query failed")

print("\n  Configuring for T-Linear radiometric mode...")

try:
    sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection\3.0 IDD & SDK\SDK_USER_PERMISSIONS\SDK_USER_PERMISSIONS')
    from ClientFiles_Python.EnumTypes import (
        FLR_BOSON_GAINMODE_E,
        FLR_ENABLE_E,
        FLR_SYSCTRL_USBIR16_MODE_E
    )

    cam.bosonSetGainMode(FLR_BOSON_GAINMODE_E.FLR_BOSON_HIGH_GAIN)
    print("    Gain mode: HIGH")

    cam.TLinearSetControl(FLR_ENABLE_E.FLR_ENABLE)
    print("    T-Linear: ENABLED")

    cam.sysctrlSetUsbVideoIR16Mode(FLR_SYSCTRL_USBIR16_MODE_E.FLR_SYSCTRL_USBIR16_MODE_TLINEAR)
    print("    USB IR16 Mode: T-LINEAR")

    # Verify
    result, mode = cam.sysctrlGetUsbVideoIR16Mode()
    print(f"    Verified USB IR16: {mode} (2=T-Linear)")

    result = cam.CLIENT_pkg_TLinear_GetControl()
    print(f"    Verified T-Linear: {result}")

    print("  [OK] Camera configured")

except Exception as e:
    print(f"  ERROR: {e}")
    sdk.close()
    sys.exit(1)

# Close SDK
sdk.close()
print("\n  SDK closed")

print("\n[PHASE 2] Waiting for camera to apply settings...")
print("  Please wait 3 seconds...")
time.sleep(3)

print("\n[PHASE 3] Fresh video capture (no active SDK)")
print("  Opening video with EXACT FLIR method...")

device_index = 1
cap = cv2.VideoCapture(device_index + cv2.CAP_DSHOW)

if not cap.isOpened():
    print("ERROR: Cannot open video")
    sys.exit(1)

# FLIR's exact sequence
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
fourcc_result = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc('Y', '1', '6', ' '))
cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)

print(f"  FOURCC set: {fourcc_result}")

# Check actual format
fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
print(f"  Actual FOURCC: '{fourcc_str}'")

# Flush first frames
print("\n  Flushing first 10 frames...")
for _ in range(10):
    cap.grab()

time.sleep(0.5)

# Capture and analyze
print("\n  Capturing frame...")
ret, frame = cap.read()

if ret and frame is not None:
    print(f"\n  RESULT:")
    print(f"    dtype: {frame.dtype}")
    print(f"    shape: {frame.shape}")
    print(f"    min: {frame.min()}")
    print(f"    max: {frame.max()}")

    if frame.dtype == np.uint16:
        print(f"\n  SUCCESS: 16-bit radiometric data!")

        # Test temperature conversion
        h, w = frame.shape[:2]
        center_val = frame[h//2, w//2]
        temp_c = (center_val / 100.0) - 273.15
        print(f"    Center temp: {temp_c:.1f} C")
    else:
        print(f"\n  Still 8-bit output")

        # Check if it's at least grayscale
        if len(frame.shape) == 2:
            print(f"    At least it's grayscale!")
        else:
            print(f"    Color output: {frame.shape[2]} channels")
else:
    print("  ERROR: Failed to capture")

cap.release()

print("\n" + "="*70)
print("Conclusion:")
if frame is not None and frame.dtype == np.uint16:
    print("  16-bit capture working!")
else:
    print("  16-bit capture NOT working with this approach")
    print("\n  Possible reasons:")
    print("    1. Camera firmware doesn't support Y16 over DirectShow")
    print("    2. Windows DirectShow version incompatibility")
    print("    3. Need FLIR's custom DirectShow filter")
    print("    4. Device driver issue")
print("="*70)
