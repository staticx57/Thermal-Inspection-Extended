"""
Test dual-path radiometric backend.

Verifies:
1. SDK connects via COM port
2. T-Linear mode is configured
3. flirpy captures 16-bit frames
4. Temperature readings are correct
5. FFC trigger works while capturing
"""

import sys
import numpy as np

print("=" * 70)
print("Dual-Path Radiometric Backend Test")
print("=" * 70)

from flirpy_thermal_backend import FlirpyThermalBackend

# Create backend with SDK auto-configuration
print("\n1. Creating backend with SDK integration...")
backend = FlirpyThermalBackend(com_port='COM7', auto_configure=True)

print(f"   COM port: {backend.com_port}")
print(f"   Auto-configure: enabled")

# Open camera (this connects SDK + configures T-Linear + opens flirpy)
print("\n2. Opening camera (SDK + T-Linear + flirpy)...")
if not backend.open():
    print("[ERROR] Failed to open camera")
    sys.exit(1)

print("[OK] Camera opened")
print(f"   SDK connected: {backend.is_sdk_connected}")
print(f"   T-Linear enabled: {backend.is_tlinear_enabled}")

# Capture frame
print("\n3. Capturing 16-bit frame...")
ret, frame = backend.read()

if not ret or frame is None:
    print("[ERROR] Failed to capture frame")
    backend.release()
    sys.exit(1)

print(f"[OK] Frame captured")
print(f"   Shape: {frame.shape}")
print(f"   Dtype: {frame.dtype}")
print(f"   Min: {frame.min()}")
print(f"   Max: {frame.max()}")
print(f"   Mean: {frame.mean():.1f}")

# Temperature conversion
print("\n4. Temperature conversion (Y16 → Celsius)...")
temp_k = frame.astype(np.float32) / 100.0
temp_c = temp_k - 273.15

print(f"   Min temp: {temp_c.min():.1f}°C")
print(f"   Max temp: {temp_c.max():.1f}°C")
print(f"   Mean temp: {temp_c.mean():.1f}°C")

# Check if temperature is reasonable
if 10 < temp_c.mean() < 50:
    print("[OK] Temperature in expected room temp range!")
else:
    print(f"[WARNING] Temperature {temp_c.mean():.1f}°C outside expected range")
    print("         Check T-Linear configuration")

# Test SDK functions while capturing
print("\n5. Testing SDK control while capturing...")

# Get FPA temperature
fpa = backend.get_fpa_temperature()
if fpa:
    print(f"   FPA temperature: {fpa:.1f}°C")
else:
    print("   FPA temperature: unavailable")

# Get lens temperature
lens = backend.get_lens_temperature()
if lens:
    print(f"   Lens temperature: {lens:.1f}°C")
else:
    print("   Lens temperature: unavailable")

# Test FFC trigger
print("\n6. Testing FFC trigger...")
if backend.trigger_ffc():
    print("[OK] FFC triggered successfully")
else:
    print("[WARNING] FFC trigger failed")

# Capture another frame after FFC
print("\n7. Capturing frame after FFC...")
ret, frame2 = backend.read()

if ret and frame2 is not None:
    temp_c2 = (frame2.astype(np.float32) / 100.0) - 273.15
    print(f"[OK] Post-FFC frame captured")
    print(f"   Mean temp: {temp_c2.mean():.1f}°C")
else:
    print("[WARNING] Post-FFC capture failed")

# Get backend info
print("\n8. Backend info:")
info = backend.get_info()
for key, value in info.items():
    if key != 'features':
        print(f"   {key}: {value}")

# Cleanup
print("\n9. Closing camera...")
backend.release()
print("[OK] Camera closed")

print("\n" + "=" * 70)
print("Test Complete")
print("=" * 70)
