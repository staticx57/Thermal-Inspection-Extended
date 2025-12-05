"""
Test flirpy after configuring camera via SDK.

Strategy:
1. Configure camera via SDK (T-Linear mode)
2. Close SDK connection
3. Open flirpy and capture frames
"""
import time
from boson_sdk_wrapper import BosonSDK

print("="*60)
print("Testing flirpy with SDK pre-configuration")
print("="*60)

# Step 1: Configure via SDK
print("\n[STEP 1] Configuring camera via SDK on COM7...")
sdk = BosonSDK(com_port='COM7')

if not sdk.open():
    print("[X] Failed to open SDK connection on COM7")
    print("    Check Device Manager for correct COM port")
    exit(1)

print("[OK] SDK connected")

# Enable T-Linear mode
print("Setting T-Linear radiometric mode...")
if sdk.set_usb_ir16_mode('tlinear'):
    print("[OK] T-Linear mode enabled")
else:
    print("[WARNING] Could not set T-Linear mode")

# Get FPA temperature for verification
fpa_temp = sdk.get_fpa_temperature()
if fpa_temp:
    if isinstance(fpa_temp, tuple):
        fpa_temp = fpa_temp[0] if len(fpa_temp) > 0 else None
    if fpa_temp:
        print(f"[OK] FPA temp: {fpa_temp:.1f}°C")

# Step 2: Close SDK to release COM port
print("\n[STEP 2] Closing SDK to release COM port...")
sdk.close()
print("[OK] SDK closed")

# Give it a moment
time.sleep(1)

# Step 3: Open flirpy
print("\n[STEP 3] Opening camera via flirpy...")
try:
    from flirpy.camera.boson import Boson
    camera = Boson()  # No COM port parameter
    print("[OK] flirpy camera opened")
except Exception as e:
    print(f"[X] Failed to open flirpy camera: {e}")
    exit(1)

# Step 4: Try to capture frames
print("\n[STEP 4] Capturing frames...")
success_count = 0
for i in range(10):
    try:
        frame = camera.grab()
        if frame is not None and frame.dtype == 'uint16':
            if i == 0:
                print(f"[OK] Frame captured successfully!")
                print(f"    Shape: {frame.shape}")
                print(f"    Dtype: {frame.dtype}")
                print(f"    Range: {frame.min()} - {frame.max()}")
            success_count += 1
        else:
            print(f"[X] Frame {i+1}: Invalid frame")
    except Exception as e:
        print(f"[X] Frame {i+1}: Error: {e}")

    time.sleep(0.15)  # ~7-8 FPS

print(f"\n[RESULT] Captured {success_count}/10 frames successfully")

# Step 5: Cleanup
print("\n[STEP 5] Closing flirpy camera...")
camera.close()
print("[OK] Camera closed")

if success_count >= 8:
    print("\n" + "="*60)
    print("SUCCESS! flirpy is working correctly")
    print("="*60)
else:
    print("\n" + "="*60)
    print(f"PARTIAL SUCCESS: {success_count}/10 frames")
    print("="*60)
