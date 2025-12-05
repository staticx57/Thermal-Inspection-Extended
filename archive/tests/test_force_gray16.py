#!/usr/bin/env python3
"""Test forcing grayscale/Y16 capture with different methods."""
import sys
import time
import cv2
import numpy as np
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Testing Various Y16 Capture Methods")
print("="*60)

# First set camera to T-Linear mode
print("\n[Setting camera to T-Linear mode via SDK]")
sdk = BosonSDK(com_port='COM7')
if sdk.open():
    cam = sdk.camera

    class Int32Wrapper:
        def __init__(self, val):
            self.value = val

    # Set USB IR16 mode to T-Linear
    mode_arg = Int32Wrapper(2)
    result = cam.sysctrlSetUsbVideoIR16Mode(mode_arg)

    # Enable T-Linear control
    tlin_arg = Int32Wrapper(1)
    cam.CLIENT_pkg_TLinear_SetControl(tlin_arg)

    sdk.close()
    print("  [OK] Camera configured for T-Linear")
    time.sleep(0.5)

# Test Method 1: Y16 with CONVERT_RGB=0
print("\n[Method 1] Y16 + CONVERT_RGB=0")
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
if cap.isOpened():
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)

    time.sleep(0.3)
    ret, frame = cap.read()
    if ret and frame is not None:
        print(f"  dtype: {frame.dtype}, shape: {frame.shape}")
    cap.release()

# Test Method 2: GREY/Y800 format
print("\n[Method 2] GREY (Y800) format")
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
if cap.isOpened():
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('G','R','E','Y'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)

    time.sleep(0.3)
    ret, frame = cap.read()
    if ret and frame is not None:
        print(f"  dtype: {frame.dtype}, shape: {frame.shape}")
    cap.release()

# Test Method 3: Try MSMF backend
print("\n[Method 3] MSMF backend with Y16")
try:
    cap = cv2.VideoCapture(1, cv2.CAP_MSMF)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)

        time.sleep(0.3)
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"  dtype: {frame.dtype}, shape: {frame.shape}")
        cap.release()
except Exception as e:
    print(f"  Error: {e}")

# Test Method 4: Raw read with explicit format
print("\n[Method 4] Using VideoCapture with manual format")
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
if cap.isOpened():
    # Try setting format FIRST before resolution
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    cap.set(cv2.CAP_PROP_MODE, cv2.CAP_MODE_GRAY)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)

    # Check what we got
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"  Negotiated FOURCC: '{fourcc_str}'")
    print(f"  CONVERT_RGB: {cap.get(cv2.CAP_PROP_CONVERT_RGB)}")
    print(f"  MODE: {cap.get(cv2.CAP_PROP_MODE)}")

    time.sleep(0.3)
    ret, frame = cap.read()
    if ret and frame is not None:
        print(f"  Frame: dtype={frame.dtype}, shape={frame.shape}")
        if frame.dtype == np.uint16:
            print(f"  [SUCCESS] Got 16-bit data!")
    cap.release()

print("\n" + "="*60)
print("Analysis Complete")
print("="*60)
print("\nConclusion:")
print("  If all methods return 8-bit I420, the issue is:")
print("    1. OpenCV/DirectShow cannot negotiate Y16 with this camera")
print("    2. Need to use different capture library (e.g., PyCapture2, direct USB)")
print("    3. Or camera firmware needs specific USB descriptor mode")
