#!/usr/bin/env python3
"""Test proper sequence for 16-bit mode: SDK first, then video capture."""
import sys
import time
import cv2
import numpy as np
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Proper 16-bit Initialization Sequence Test")
print("="*60)

print("\n[STEP 1] Connect SDK and configure camera FIRST")
print("(Before opening any video streams)")

sdk = BosonSDK(com_port='COM7')

if sdk.open():
    print("  [OK] SDK connected")
    cam = sdk.camera

    # Get current mode
    result, current_mode = cam.sysctrlGetUsbVideoIR16Mode()
    print(f"  Current USB IR16 mode: {current_mode}")

    # Set to T-Linear mode (2)
    print("\n  Setting USB IR16 to T-Linear mode...")
    class Int32Wrapper:
        def __init__(self, val):
            self.value = val

    mode_arg = Int32Wrapper(2)  # T-Linear radiometric
    result = cam.sysctrlSetUsbVideoIR16Mode(mode_arg)
    print(f"  Set result: {result.value if hasattr(result, 'value') else result}")

    # Verify
    time.sleep(0.3)
    result, new_mode = cam.sysctrlGetUsbVideoIR16Mode()
    print(f"  Verified mode: {new_mode}")

    if new_mode == 2:
        print("  [OK] T-Linear mode active")

    # Also enable T-Linear processing
    print("\n  Enabling T-Linear control...")
    try:
        class CTypesInt:
            def __init__(self, val):
                self.value = val

        arg = CTypesInt(1)
        res = cam.CLIENT_pkg_TLinear_SetControl(arg)
        val = res.value if hasattr(res, 'value') else res
        if val == 0:
            print("  [OK] T-Linear control enabled")
    except Exception as e:
        print(f"  Warning: {e}")

    # Close SDK but keep settings
    sdk.close()
    print("\n  SDK closed (settings persist)")

print("\n[STEP 2] Now open video capture with Y16 format")
print("(Camera should now output 16-bit data)")

# Small delay
time.sleep(0.5)

print("\n  Opening video capture...")
cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

if cap.isOpened():
    print("  [OK] Video capture opened")

    # CRITICAL: Set Y16 format IMMEDIATELY after opening
    print("\n  Requesting Y16 format...")
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
    fourcc_set = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
    print(f"  FOURCC set result: {fourcc_set}")

    # Set resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    # Verify FOURCC
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
    print(f"  Active FOURCC: '{fourcc_str}' ({fourcc})")

    # Flush first few frames
    print("\n  Flushing initial frames...")
    for _ in range(5):
        cap.grab()
    time.sleep(0.2)

    # Now read frame
    print("\n  Reading frame...")
    ret, frame = cap.read()

    if ret and frame is not None:
        print(f"\n[FRAME ANALYSIS]")
        print(f"  dtype: {frame.dtype}")
        print(f"  shape: {frame.shape}")
        print(f"  min: {frame.min()}")
        print(f"  max: {frame.max()}")
        print(f"  mean: {frame.mean():.2f}")
        print(f"  std: {frame.std():.2f}")

        if frame.dtype == np.uint16:
            print(f"\n{'='*60}")
            print(f"SUCCESS! TRUE 16-BIT RADIOMETRIC DATA CAPTURED!")
            print(f"{'='*60}")
            print(f"\n  Frame contains raw thermal counts with full dynamic range")
            print(f"  Ready for absolute temperature conversion")

            # Sample some pixels
            h, w = frame.shape[:2]
            center_val = frame[h//2, w//2]
            print(f"\n  Sample pixel values:")
            print(f"    Center: {center_val}")
            print(f"    Top-left: {frame[0, 0]}")
            print(f"    Top-right: {frame[0, -1]}")

        else:
            print(f"\n[WARNING] Still {frame.dtype}")
            if len(frame.shape) == 3:
                print(f"  Frame has {frame.shape[2]} channels - still color output")
            print(f"\n  This may indicate:")
            print(f"    1. Camera needs power cycle to apply USB mode change")
            print(f"    2. DirectShow backend doesn't support Y16")
            print(f"    3. Need to use different video endpoint/backend")
    else:
        print("  [ERROR] Failed to read frame")

    cap.release()
    print("\n  Video capture released")
else:
    print("  [ERROR] Failed to open video capture")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
