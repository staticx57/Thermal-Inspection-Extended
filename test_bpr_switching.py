#!/usr/bin/env python3
"""Test BPR (Boson Processing & Routing) for runtime mode switching."""
import sys
import time
import cv2
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Testing BPR Mode Switching (8-bit AGC <-> 16-bit RAW)")
print("="*60)

sdk = BosonSDK(com_port='COM7')

if sdk.open():
    print("\n[OK] SDK connected")
    cam = sdk.camera

    # Get current BPR state and display mode
    print("\n[Step 1] Reading current BPR settings:")
    try:
        result, state = cam.bprGetState()
        print(f"  BPR State: {state} (result: {result.value})")

        result, mode = cam.bprGetDisplayMode()
        print(f"  Display Mode: {mode} (result: {result.value})")
    except Exception as e:
        print(f"  Error reading BPR: {e}")

    # Try to set BPR to different modes
    # BPR Display Modes typically:
    # 0 = AGC (8-bit processed)
    # 1 = Raw 14-bit
    # May vary by firmware

    print("\n[Step 2] Testing BPR mode switching:")

    print("\n  Testing Mode 0 (AGC 8-bit):")
    try:
        result = cam.bprSetDisplayMode(0)
        result_val = result.value if hasattr(result, 'value') else result
        print(f"    SetDisplayMode(0) result: {result_val}")

        # Verify
        get_result = cam.bprGetDisplayMode()
        if isinstance(get_result, tuple):
            result, mode = get_result
            print(f"    Current mode: {mode}")
        else:
            print(f"    Current mode: {get_result}")

        # Test video capture
        print("    Opening video capture...")
        cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
            time.sleep(0.3)
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"      Frame: dtype={frame.dtype}, shape={frame.shape}")
            cap.release()
    except Exception as e:
        print(f"    Error: {e}")

    print("\n  Testing Mode 1 (Raw 14-bit / 16-bit):")
    try:
        result = cam.bprSetDisplayMode(1)
        result_val = result.value if hasattr(result, 'value') else result
        print(f"    SetDisplayMode(1) result: {result_val}")

        # Verify
        get_result = cam.bprGetDisplayMode()
        if isinstance(get_result, tuple):
            result, mode = get_result
            print(f"    Current mode: {mode}")
        else:
            print(f"    Current mode: {get_result}")

        # Test video capture
        print("    Opening video capture...")
        cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)
            time.sleep(0.3)
            ret, frame = cap.read()
            if ret and frame is not None:
                print(f"      Frame: dtype={frame.dtype}, shape={frame.shape}")
                if frame.dtype == 'uint16':
                    print(f"      SUCCESS: 16-bit raw data!")
            cap.release()
    except Exception as e:
        print(f"    Error: {e}")

    # Restore to AGC mode
    print("\n  Restoring to Mode 0 (AGC)...")
    try:
        result = cam.bprSetDisplayMode(0)
        print(f"    Restored to mode 0")
    except:
        pass

    sdk.close()
    print("\n[OK] SDK closed")

print("\n" + "="*60)
print("BPR Mode Switching Test Complete")
print("="*60)
