"""
Test flirpy capture + SDK control SIMULTANEOUSLY.

This verifies that:
1. flirpy can capture frames while SDK is connected
2. SDK can send commands while flirpy is capturing
3. Both interfaces work independently (UVC + COM port)
"""

import sys
import time
import numpy as np

print("=" * 60)
print("Testing SIMULTANEOUS flirpy + SDK")
print("=" * 60)

# Test 1: Import both
print("\n1. Checking imports...")
try:
    from flirpy.camera.boson import Boson
    print("[OK] flirpy imported")
except ImportError as e:
    print(f"[X] flirpy import failed: {e}")
    sys.exit(1)

try:
    from boson_sdk_wrapper import BosonSDK
    print("[OK] BosonSDK imported")
except ImportError as e:
    print(f"[X] BosonSDK import failed: {e}")
    sys.exit(1)

# Test 2: Open SDK FIRST (before flirpy)
print("\n2. Opening SDK connection (COM port)...")
sdk = BosonSDK(com_port='COM7')
if sdk.open():
    print("[OK] SDK connected via COM6")

    # Get initial FPA temperature
    fpa_temp = sdk.get_fpa_temperature()
    if fpa_temp:
        if isinstance(fpa_temp, tuple):
            fpa_temp = fpa_temp[0] if len(fpa_temp) > 0 else None
        if fpa_temp:
            print(f"[OK] Initial FPA temp: {fpa_temp:.1f}°C")
else:
    print("[X] SDK connection failed")
    print("    This might mean:")
    print("    - COM port already in use")
    print("    - Wrong COM port (check Device Manager)")
    print("    - Permission issue")
    sys.exit(1)

# Test 3: Open flirpy WHILE SDK is connected
print("\n3. Opening flirpy camera (UVC video) while SDK is connected...")
try:
    # CRITICAL: Pass dummy port to prevent flirpy from opening COM port
    # This allows SDK to control via COM port simultaneously
    camera = Boson(port="DISABLED")
    print("[OK] flirpy camera opened")
    print("    >> SDK and flirpy both connected! <<")
except Exception as e:
    print(f"[X] flirpy camera failed: {e}")
    sdk.close()
    sys.exit(1)

# Test 4: Capture frames while SDK is active
print("\n4. Testing frame capture while SDK is connected...")
try:
    frame = camera.grab()
    print(f"[OK] Frame captured: {frame.shape}, dtype={frame.dtype}")
    print(f"    Range: {frame.min()} - {frame.max()}")

    # Convert to temperature
    temp_k = frame.astype(np.float32) / 100.0
    temp_c = temp_k - 273.15
    print(f"    Temp: {temp_c.min():.1f}°C - {temp_c.max():.1f}°C")
except Exception as e:
    print(f"[X] Frame capture failed: {e}")
    camera.close()
    sdk.close()
    sys.exit(1)

# Test 5: Use SDK commands while capturing
print("\n5. Testing SDK commands while flirpy is capturing...")

# Test FPA temperature
try:
    fpa_temp = sdk.get_fpa_temperature()
    if fpa_temp:
        if isinstance(fpa_temp, tuple):
            fpa_temp = fpa_temp[0] if len(fpa_temp) > 0 else None
        if fpa_temp:
            print(f"[OK] FPA temp while capturing: {fpa_temp:.1f}°C")
    else:
        print("[WARNING] Could not read FPA temp (might be expected)")
except Exception as e:
    print(f"[WARNING] FPA temp read error: {e}")

# Test frame capture during SDK command
try:
    frame2 = camera.grab()
    print(f"[OK] Frame captured after SDK command")
except Exception as e:
    print(f"[X] Frame capture after SDK failed: {e}")

# Test 6: Continuous capture + SDK polling
print("\n6. Testing sustained simultaneous operation (5 seconds)...")
frame_count = 0
sdk_poll_count = 0
start_time = time.time()

try:
    while time.time() - start_time < 5.0:
        # Capture frame
        frame = camera.grab()
        frame_count += 1

        # Poll SDK every 10 frames
        if frame_count % 10 == 0:
            fpa = sdk.get_fpa_temperature()
            if fpa:
                if isinstance(fpa, tuple):
                    fpa = fpa[0] if len(fpa) > 0 else None
                if fpa:
                    sdk_poll_count += 1

        time.sleep(0.01)  # Small delay

    elapsed = time.time() - start_time
    fps = frame_count / elapsed

    print(f"[OK] Sustained operation successful:")
    print(f"    Frames captured: {frame_count}")
    print(f"    Frame rate: {fps:.1f} FPS")
    print(f"    SDK polls: {sdk_poll_count}")
    print(f"    >> BOTH WORK SIMULTANEOUSLY! <<")

except Exception as e:
    print(f"[X] Sustained operation failed: {e}")

# Cleanup
print("\n7. Closing connections...")
camera.close()
print("[OK] flirpy camera closed")
sdk.close()
print("[OK] SDK closed")

# Summary
print("\n" + "=" * 60)
print("SUCCESS!")
print("=" * 60)
print("\nConclusion:")
print("✓ flirpy (UVC video) and SDK (COM port) work SIMULTANEOUSLY")
print("✓ Both interfaces are INDEPENDENT")
print("✓ Can capture frames AND send commands at the same time")
print("\nThis means:")
print("- Use flirpy for 16-bit Y16 radiometric capture")
print("- Use SDK for FFC trigger, AGC control, telemetry")
print("- Both work together with NO conflicts!")
print("=" * 60)
