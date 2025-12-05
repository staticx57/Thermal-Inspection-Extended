#!/usr/bin/env python3
"""Test sysctrl USB Video IR16 Mode for true 16-bit output."""
import sys
import time
import cv2
import numpy as np
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Testing sysctrl USB Video IR16 Mode (TRUE 16-BIT)")
print("="*60)

sdk = BosonSDK(com_port='COM7')

if sdk.open():
    print("\n[OK] SDK connected")
    cam = sdk.camera

    # Check for sysctrl functions
    print("\nChecking for sysctrl IR16 functions:")
    if hasattr(cam, 'sysctrlSetUsbVideoIR16Mode'):
        print("  [OK] sysctrlSetUsbVideoIR16Mode found")
    else:
        print("  [ERROR] sysctrlSetUsbVideoIR16Mode NOT found")

    if hasattr(cam, 'sysctrlGetUsbVideoIR16Mode'):
        print("  [OK] sysctrlGetUsbVideoIR16Mode found")
    else:
        print("  [ERROR] sysctrlGetUsbVideoIR16Mode NOT found")

    # Get current USB IR16 mode
    print("\n[Step 1] Reading current USB IR16 mode:")
    try:
        result, mode = cam.sysctrlGetUsbVideoIR16Mode()
        print(f"  Current mode: {mode}")
        print(f"    0 = 16-bit raw")
        print(f"    1 = 14-bit raw")
        print(f"    2 = T-Linear radiometric")
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

    # Try to set T-Linear mode (mode 2)
    print("\n[Step 2] Setting USB IR16 to T-Linear mode (mode 2):")
    try:
        # Create proper argument wrapper
        class Int32Wrapper:
            def __init__(self, val):
                self.value = val

        mode_arg = Int32Wrapper(2)  # T-Linear mode
        result = cam.sysctrlSetUsbVideoIR16Mode(mode_arg)
        result_val = result.value if hasattr(result, 'value') else result
        print(f"  Set result: {result_val} (0 = success)")

        # Verify the change
        time.sleep(0.3)
        result, current_mode = cam.sysctrlGetUsbVideoIR16Mode()
        print(f"  Verified mode: {current_mode}")

        if current_mode == 2:
            print("  [SUCCESS] USB IR16 mode set to T-Linear!")

            # Now test video capture with Y16
            print("\n[Step 3] Testing video capture with Y16 format:")

            # Close any existing video streams
            print("  Reinitializing video capture...")
            time.sleep(0.5)

            cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
            if cap.isOpened():
                # Request Y16 format
                print("  Setting Y16 format...")
                cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y','1','6',' '))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 512)

                # Check FOURCC
                fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
                fourcc_str = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
                print(f"  Active FOURCC: {fourcc_str}")

                # Capture frame
                time.sleep(0.5)
                ret, frame = cap.read()

                if ret and frame is not None:
                    print(f"\n  [FRAME CAPTURED]")
                    print(f"    dtype: {frame.dtype}")
                    print(f"    shape: {frame.shape}")
                    print(f"    min: {frame.min()}")
                    print(f"    max: {frame.max()}")
                    print(f"    mean: {frame.mean():.2f}")

                    if frame.dtype == np.uint16:
                        print(f"\n  [SUCCESS!] TRUE 16-BIT RADIOMETRIC DATA!")
                        print(f"    This is raw thermal data with full dynamic range")
                        print(f"    Can now compute absolute temperatures")
                    else:
                        print(f"\n  [WARNING] Still {frame.dtype}, not uint16")
                        print(f"    May need to close/reopen camera completely")
                else:
                    print(f"  [ERROR] Failed to capture frame")

                cap.release()
        else:
            print(f"  [ERROR] Mode did not change (still {current_mode})")

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()

    sdk.close()
    print("\n[OK] SDK closed")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
print("\nNOTE: If mode changed but capture still 8-bit, you may need to:")
print("  1. Close the application completely")
print("  2. Power cycle the camera")
print("  3. Reopen with Y16 format from the start")
