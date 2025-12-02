#!/usr/bin/env python3
"""Test different OpenCV backends and formats for radiometric capture."""
import cv2
import numpy as np
import sys
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Testing OpenCV Format Support for Radiometric Capture")
print("="*60)

# First enable T-Linear mode via SDK
print("\nStep 1: Enabling T-Linear mode via SDK...")
sdk = BosonSDK(com_port='COM7')
if sdk.open():
    print("  SDK connected")
    # T-Linear should already be enabled, but let's verify
    cam_obj = sdk.camera
    result = cam_obj.CLIENT_pkg_TLinear_GetControl()
    print(f"  T-Linear state: {result}")
    sdk.close()
    print("  SDK closed")
else:
    print("  ERROR: Could not connect to SDK")
    sys.exit(1)

# Test different backends
backends = [
    ('DSHOW', cv2.CAP_DSHOW),
    ('MSMF', cv2.CAP_MSMF),
    ('ANY', cv2.CAP_ANY)
]

print("\nStep 2: Testing different OpenCV backends...")

for name, backend in backends:
    print(f"\n[Testing {name} backend]")
    cap = cv2.VideoCapture(1, backend)

    if not cap.isOpened():
        print(f"  Failed to open with {name}")
        continue

    print(f"  Opened successfully")

    # Try setting format
    print(f"  Attempting to set Y16 format...")
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    fourcc_result = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
    print(f"    FOURCC set result: {fourcc_result}")

    # Get current format
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"    Current FOURCC: {fourcc_str} ({fourcc})")
    print(f"    Convert RGB: {cap.get(cv2.CAP_PROP_CONVERT_RGB)}")

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)

    # Read frame
    ret, frame = cap.read()
    if ret and frame is not None:
        print(f"    Frame captured:")
        print(f"      dtype: {frame.dtype}")
        print(f"      shape: {frame.shape}")
        print(f"      min: {frame.min()}, max: {frame.max()}")

        if frame.dtype == np.uint16:
            print(f"      SUCCESS: 16-bit capture!")
        else:
            print(f"      Still 8-bit")
    else:
        print(f"    Failed to read frame")

    cap.release()

print("\n" + "="*60)
print("Format Test Complete")
print("="*60)
print("\nConclusion:")
print("  If all backends show 8-bit, the FLIR Boson may be outputting")
print("  8-bit AGC data over USB even with T-Linear enabled via serial.")
print("  The T-Linear mode may require a different UVC mode or firmware setting.")
