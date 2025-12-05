#!/usr/bin/env python3
"""Detailed BPR testing with better error handling."""
import sys
import time
import cv2
import traceback
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Detailed BPR Testing")
print("="*60)

sdk = BosonSDK(com_port='COM7')

if sdk.open():
    print("\n[OK] SDK connected")
    cam = sdk.camera

    # Get current state
    print("\n[Current BPR Settings]")
    try:
        result, state = cam.bprGetState()
        print(f"  BPR State: {state}")
        result, mode = cam.bprGetDisplayMode()
        print(f"  Display Mode: {mode}")
    except Exception as e:
        print(f"  Error: {e}")
        traceback.print_exc()

    # Try to switch to mode 1 (raw)
    print("\n[Switching to Raw Mode 1]")
    try:
        print("  Calling bprSetDisplayMode(1)...")

        # Create ctypes wrapper for integer
        class Int32Wrapper:
            def __init__(self, val):
                self.value = val

        mode_arg = Int32Wrapper(1)
        result = cam.bprSetDisplayMode(mode_arg)
        print(f"  Result type: {type(result)}")
        print(f"  Result value: {result}")

        # Check if successful
        time.sleep(0.2)
        result2, mode = cam.bprGetDisplayMode()
        print(f"  Verified mode: {mode}")

        if mode == 1:
            print("  SUCCESS: Switched to Raw Mode!")

            # Now test OpenCV capture
            print("\n  Testing video capture in Raw Mode:")
            cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
            if cap.isOpened():
                # Try Y16 format
                cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)

                # Get FOURCC
                fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
                print(f"    FOURCC: {fourcc_str}")

                time.sleep(0.3)
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"    Frame captured:")
                    print(f"      dtype: {frame.dtype}")
                    print(f"      shape: {frame.shape}")
                    print(f"      min: {frame.min()}, max: {frame.max()}")
                else:
                    print(f"    Failed to capture frame")
                cap.release()
        else:
            print(f"  Mode did not switch (still {mode})")

    except Exception as e:
        print(f"  Error: {e}")
        traceback.print_exc()

    # Switch back to AGC
    print("\n[Switching back to AGC Mode 0]")
    try:
        class Int32Wrapper:
            def __init__(self, val):
                self.value = val
        mode_arg = Int32Wrapper(0)
        result = cam.bprSetDisplayMode(mode_arg)
        print(f"  Switched back to AGC")
    except Exception as e:
        print(f"  Error: {e}")

    sdk.close()
    print("\n[OK] SDK closed")

print("\n" + "="*60)
