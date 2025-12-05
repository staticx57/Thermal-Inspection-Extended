"""
Diagnostic script for radiometric calibration investigation.

This script captures raw frames from the FLIR Boson and analyzes:
1. Raw pixel values and their distribution
2. Temperature conversion results
3. Whether the camera is in T-Linear mode
4. Comparison with expected values
"""

import sys
import numpy as np

print("=" * 70)
print("FLIR Boson Radiometric Calibration Diagnostic")
print("=" * 70)

# Check flirpy import
try:
    from flirpy.camera.boson import Boson
    print("[OK] flirpy imported")
except ImportError as e:
    print(f"[ERROR] flirpy not available: {e}")
    sys.exit(1)

# Check SDK import
try:
    from boson_sdk_wrapper import BosonSDK
    SDK_AVAILABLE = True
    print("[OK] BosonSDK imported")
except ImportError as e:
    SDK_AVAILABLE = False
    print(f"[WARNING] BosonSDK not available: {e}")

print("\n" + "-" * 70)
print("Step 1: Capture frame via flirpy")
print("-" * 70)

try:
    camera = Boson()
    print("[OK] Camera opened")
    
    # Capture multiple frames and average to reduce noise
    frames = []
    for i in range(5):
        frame = camera.grab()
        if frame is not None:
            frames.append(frame)
    
    if not frames:
        print("[ERROR] No frames captured!")
        camera.close()
        sys.exit(1)
    
    # Use most recent frame
    frame = frames[-1]
    camera.close()
    print("[OK] Camera closed")
    
    print(f"\nFrame Properties:")
    print(f"  Shape: {frame.shape}")
    print(f"  Dtype: {frame.dtype}")
    print(f"  Min value: {frame.min()}")
    print(f"  Max value: {frame.max()}")
    print(f"  Mean value: {frame.mean():.1f}")
    print(f"  Std dev: {frame.std():.1f}")
    
    # Check if truly 16-bit
    if frame.dtype == np.uint16:
        print(f"  [OK] TRUE 16-bit data")
        if frame.max() > 255:
            print(f"  [OK] Values exceed 8-bit range")
        else:
            print(f"  [WARNING] Values within 8-bit range - might not be radiometric")
    else:
        print(f"  [WARNING] Not 16-bit: {frame.dtype}")
    
except Exception as e:
    print(f"[ERROR] Failed to capture: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "-" * 70)
print("Step 2: Temperature Conversion Analysis")
print("-" * 70)

# Y16 standard conversion: pixel / 100 = Kelvin, Kelvin - 273.15 = Celsius
def y16_to_celsius(value):
    """Standard Y16 to Celsius conversion."""
    return (value / 100.0) - 273.15

def celsius_to_y16(temp_c):
    """Celsius to Y16 value."""
    return (temp_c + 273.15) * 100

# Calculate temperatures with standard Y16 conversion
min_temp_c = y16_to_celsius(frame.min())
max_temp_c = y16_to_celsius(frame.max())
mean_temp_c = y16_to_celsius(frame.mean())

print(f"\nUsing standard Y16 conversion: temp_C = (pixel / 100.0) - 273.15")
print(f"  Min temp: {min_temp_c:.1f}°C")
print(f"  Max temp: {max_temp_c:.1f}°C")
print(f"  Mean temp: {mean_temp_c:.1f}°C")

# Check if temperatures are reasonable
reasonable_range = (-40.0, 120.0)  # HIGH gain mode range
if reasonable_range[0] <= mean_temp_c <= reasonable_range[1]:
    print(f"  [OK] Mean temperature is within reasonable range for HIGH gain mode")
else:
    print(f"  [WARNING] Mean temperature {mean_temp_c:.1f}°C is outside expected range")
    print(f"           Expected range for HIGH gain: {reasonable_range[0]}°C to {reasonable_range[1]}°C")

# Calculate what Y16 values we'd expect for typical room temperature
expected_room_temp_c = 22.0  # Room temperature
expected_y16 = celsius_to_y16(expected_room_temp_c)
print(f"\n  Expected Y16 value for {expected_room_temp_c}°C: {expected_y16:.0f}")
print(f"  Actual mean Y16 value: {frame.mean():.0f}")
print(f"  Difference: {expected_y16 - frame.mean():.0f}")

print("\n" + "-" * 70)
print("Step 3: Possible Causes of Incorrect Temperature")
print("-" * 70)

# Check for common issues
if frame.mean() < 20000:
    print("\n[ISSUE] Raw values are VERY LOW - possible causes:")
    print("  1. Camera NOT in T-Linear (radiometric) mode")
    print("  2. Camera in AGC mode outputting scene-dependent values")
    print("  3. Camera needs FFC (Flat Field Correction)")
    print("  4. Wrong gain mode (low gain when should be high gain)")
    
    print("\n  Expected Y16 range for T-Linear mode:")
    print(f"    -40°C (low limit): {celsius_to_y16(-40.0):.0f}")
    print(f"    0°C (freezing):    {celsius_to_y16(0.0):.0f}")
    print(f"    20°C (room temp):  {celsius_to_y16(20.0):.0f}")
    print(f"    37°C (body temp):  {celsius_to_y16(37.0):.0f}")
    print(f"    100°C (boiling):   {celsius_to_y16(100.0):.0f}")
    
elif 25000 < frame.mean() < 35000:
    print("\n[OK] Raw values are in expected T-Linear range")
    
else:
    print(f"\n[WARNING] Raw values ({frame.mean():.0f}) are unusual")

# Alternative conversion formulas to try
print("\n" + "-" * 70)
print("Step 4: Alternative Conversion Formulas")
print("-" * 70)

print("\nTrying different conversion assumptions:")

# Option 1: Standard Y16 (already tried)
print(f"\n  A) Standard Y16 (pixel/100 - 273.15): {mean_temp_c:.1f}°C")

# Option 2: Low gain mode (divide by 50)
mean_temp_low_gain = (frame.mean() / 50.0) - 273.15
print(f"  B) Low gain mode (pixel/50 - 273.15): {mean_temp_low_gain:.1f}°C")

# Option 3: Maybe it's already Celsius x 100?
mean_temp_direct = frame.mean() / 100.0
print(f"  C) Direct (pixel/100 = celsius): {mean_temp_direct:.1f}°C")

# Option 4: Maybe Kelvin x 10?
mean_temp_k10 = (frame.mean() / 10.0) - 273.15
print(f"  D) Kelvin x 10 (pixel/10 - 273.15): {mean_temp_k10:.1f}°C")

# Option 5: Raw 14-bit sensor + offset
mean_temp_14bit = (frame.mean() / 40.0) - 273.15
print(f"  E) 14-bit scale (pixel/40 - 273.15): {mean_temp_14bit:.1f}°C")

# Option 6: Fixed offset issue
offset_to_room_temp = frame.mean() - celsius_to_y16(22.0)
print(f"\n  Offset needed to reach 22°C: {offset_to_room_temp:.0f}")
if abs(offset_to_room_temp) < 1000:
    print(f"  [SUGGESTION] Small calibration offset might fix this")
else:
    print(f"  [SUGGESTION] Large offset suggests wrong mode or scale")

print("\n" + "-" * 70)
print("Step 5: SDK Verification (if available)")
print("-" * 70)

if SDK_AVAILABLE:
    try:
        print("\n  Checking camera settings via SDK...")
        sdk = BosonSDK(com_port='COM6')  # Adjust COM port as needed
        
        if sdk.open():
            print("  [OK] SDK connected")
            
            # Get FPA temperature (ground truth)
            fpa_temp = sdk.get_fpa_temperature()
            if fpa_temp:
                print(f"  FPA temperature (SDK): {fpa_temp:.1f}°C")
                print(f"  This is the internal chip temperature")
            
            # Try to get radiometric mode settings
            # Note: Check your SDK wrapper for available methods
            
            sdk.close()
            print("  [OK] SDK closed")
        else:
            print("  [WARNING] Could not connect to SDK")
            print("  Check COM port availability")
    except Exception as e:
        print(f"  [ERROR] SDK check failed: {e}")
else:
    print("\n  SDK not available - cannot verify camera settings")
    print("  Consider checking camera configuration manually")

print("\n" + "-" * 70)
print("Step 6: Recommendations")
print("-" * 70)

print("\n  Based on the analysis:")

if mean_temp_c < -50:
    print("\n  [CRITICAL] Temperature is very negative - likely causes:")
    print("  1. Camera is NOT in T-Linear (radiometric) mode")
    print("     → Solution: Enable T-Linear via SDK before starting")
    print("  2. flirpy is not receiving true Y16 data")
    print("     → Solution: Verify FOURCC format in flirpy capture")
    print("  3. Camera needs SDK configuration first")
    print("     → Solution: Run SDK setup script before capture")
    
    print("\n  To fix, try these SDK commands:")
    print("    sdk.enable_tlinear_mode()")
    print("    sdk.set_gain_mode(0)  # HIGH gain for -40 to 120°C")
    print("    sdk.trigger_ffc()     # Flat field correction")
    
elif -40 < mean_temp_c < 50:
    print("\n  [OK] Temperature appears reasonable!")
    print("  If you still see issues in the app, check:")
    print("  1. The thermal_analyzer radiometric mode flag")
    print("  2. The camera_manager backend settings")
    print("  3. Any additional calibration offsets")
    
else:
    print("\n  [CHECK] Review camera configuration")
    print("  Temperature reading seems unusual for indoor environment")

print("\n" + "=" * 70)
print("Diagnostic Complete")
print("=" * 70)

# Save frame for further analysis
np.save('diagnostic_frame.npy', frame)
print(f"\nFrame saved to: diagnostic_frame.npy")
print("Load with: frame = np.load('diagnostic_frame.npy')")
