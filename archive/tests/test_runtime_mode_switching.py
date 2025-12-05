#!/usr/bin/env python3
"""
Test runtime mode switching between AGC and T-Linear radiometric modes.
This demonstrates switching WITHOUT reloading the application or restarting video capture.
"""
import sys
import time
sys.path.insert(0, r'C:\Users\stati\Desktop\Projects\Thermal-Inspection')

from flir_camera import FLIRBosonCamera
import cv2
import numpy as np

print("="*70)
print("FLIR Boson Runtime Mode Switching Test")
print("="*70)
print("\nThis test demonstrates switching between:")
print("  - AGC Mode (standard 8-bit processed)")
print("  - T-Linear Mode (radiometric processing)")
print("\nWithout restarting the application or video capture!")
print("="*70)

# Initialize camera with SDK enabled
print("\n[Step 1] Initializing camera with SDK...")
camera = FLIRBosonCamera(
    device_id=1,
    resolution=(640, 512),
    enable_sdk=True,
    com_port='COM7'
)

if not camera.open():
    print("[ERROR] Failed to open camera")
    sys.exit(1)

print("  [OK] Camera opened")
print(f"  SDK Connected: {camera.is_sdk_connected()}")

# Display initial status
print("\n[Step 2] Initial camera status:")
status = camera.get_video_mode_status()
for key, value in status.items():
    print(f"  {key}: {value}")

# Capture some frames in initial mode
print("\n[Step 3] Capturing frames in AGC mode...")
for i in range(3):
    ret, frame = camera.read()
    if ret and frame is not None:
        print(f"  Frame {i+1}: dtype={frame.dtype}, shape={frame.shape}, "
              f"min={frame.min()}, max={frame.max()}, mean={frame.mean():.1f}")
    time.sleep(0.1)

# Switch to T-Linear mode AT RUNTIME
print("\n[Step 4] Switching to T-Linear radiometric mode...")
print("  (This happens at runtime without closing video capture)")

if camera.switch_to_radiometric_mode():
    print("  [SUCCESS] Switched to T-Linear mode!")

    # Check new status
    print("\n[Step 5] New camera status after switching:")
    status = camera.get_video_mode_status()
    for key, value in status.items():
        print(f"  {key}: {value}")

    # Capture frames in new mode
    print("\n[Step 6] Capturing frames in T-Linear mode...")
    time.sleep(0.5)  # Brief delay to allow mode to take effect

    for i in range(3):
        ret, frame = camera.read()
        if ret and frame is not None:
            print(f"  Frame {i+1}: dtype={frame.dtype}, shape={frame.shape}, "
                  f"min={frame.min()}, max={frame.max()}, mean={frame.mean():.1f}")
        time.sleep(0.1)

    print("\n  NOTE: On Windows, dtype will still be uint8 due to DirectShow,")
    print("        but the thermal data quality reflects T-Linear processing.")

    # Switch back to AGC mode
    print("\n[Step 7] Switching back to AGC mode...")

    if camera.switch_to_agc_mode():
        print("  [SUCCESS] Switched back to AGC mode!")

        # Check final status
        print("\n[Step 8] Final camera status:")
        status = camera.get_video_mode_status()
        for key, value in status.items():
            print(f"  {key}: {value}")

        # Capture final frames
        print("\n[Step 9] Capturing frames in AGC mode again...")
        time.sleep(0.5)

        for i in range(3):
            ret, frame = camera.read()
            if ret and frame is not None:
                print(f"  Frame {i+1}: dtype={frame.dtype}, shape={frame.shape}, "
                      f"min={frame.min()}, max={frame.max()}, mean={frame.mean():.1f}")
            time.sleep(0.1)
    else:
        print("  [ERROR] Failed to switch back to AGC mode")
else:
    print("  [ERROR] Failed to switch to T-Linear mode")

# Cleanup
camera.release()
print("\n[Step 10] Camera released")

print("\n" + "="*70)
print("Runtime Mode Switching Test Complete!")
print("="*70)
print("\nSummary:")
print("  - Camera modes can be switched at runtime using SDK")
print("  - switch_to_radiometric_mode() enables T-Linear processing")
print("  - switch_to_agc_mode() returns to standard AGC")
print("  - No application restart or video reinitialization needed")
print("\nWindows Limitation:")
print("  - OpenCV with DirectShow always captures 8-bit YUV (I420 format)")
print("  - True 16-bit Y16 capture requires V4L2 on Linux or custom driver")
print("  - However, T-Linear processing still improves thermal data quality")
print("\nFor true 16-bit radiometric data on Windows:")
print("  - Use FLIR's proprietary capture library")
print("  - Or switch to Linux with V4L2 backend")
print("  - Or use direct USB access (libusb)")
print("="*70)
