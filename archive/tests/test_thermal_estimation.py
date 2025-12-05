#!/usr/bin/env python3
"""
Test script for thermal temperature estimation.

Demonstrates 8-bit pseudo-radiometric temperature estimation
using FPA temperature reference.

Note: Hobby project - trading complexity for time.
      True 16-bit radiometric can be added later.
"""

import cv2
import numpy as np
from thermal_estimator import ThermalTemperatureEstimator, celsius_to_fahrenheit
from flir_camera import FLIRBosonCamera

print("="*70)
print("Thermal Temperature Estimation Test")
print("="*70)
print()
print("This demonstrates 8-bit pseudo-radiometric temperature estimation.")
print("Accuracy: ±5-10°C (good enough for hot spot detection)")
print()
print("Note: This is a hobby project trading complexity for time.")
print("      True 16-bit can be added later via USB backend.")
print()

# Initialize camera
print("Initializing FLIR Boson camera...")
camera = FLIRBosonCamera(device_id=1, enable_sdk=True, com_port='COM7')

if not camera.open():
    print("Failed to open camera!")
    exit(1)

print("Camera opened successfully")
print()

# Enable T-Linear mode for better quality
print("Enabling T-Linear mode...")
camera.switch_to_radiometric_mode()
print()

# Create temperature estimator
print("Creating temperature estimator...")
estimator = ThermalTemperatureEstimator(
    scene_min_c=15.0,    # Expected minimum (room temp)
    scene_max_c=100.0,   # Expected maximum (hot objects)
    use_adaptive_range=True  # Dynamically adjust range
)

# Get calibration info
calib_info = estimator.get_calibration_info()
print("Calibration settings:")
for key, value in calib_info.items():
    print(f"  {key}: {value}")
print()

# Capture and process
print("Capturing frame...")
ret, frame = camera.read()

if not ret:
    print("Failed to capture frame!")
    camera.release()
    exit(1)

print(f"Frame captured: {frame.shape}, {frame.dtype}")
print()

# Get FPA temperature
fpa_temp = camera.get_fpa_temperature()
if fpa_temp:
    fpa_temp_k, fpa_temp_c = fpa_temp
    print(f"FPA Temperature: {fpa_temp_c:.2f}°C ({celsius_to_fahrenheit(fpa_temp_c):.2f}°F)")
else:
    print("Warning: Could not read FPA temperature, using default")
    fpa_temp_c = 25.0

print()

# Estimate temperature map
print("Estimating temperature map...")
temp_map = estimator.estimate_temperature_map(frame, fpa_temp_c)

if temp_map is None:
    print("Failed to estimate temperatures!")
    camera.release()
    exit(1)

print(f"Temperature map generated: {temp_map.shape}")
print()

# Get statistics
print("="*70)
print("Temperature Statistics")
print("="*70)

stats = estimator.get_statistics(frame, fpa_temp_c)

print(f"Minimum: {stats['min_temp_c']:.1f}°C ({celsius_to_fahrenheit(stats['min_temp_c']):.1f}°F)")
print(f"  Location: {stats['min_location']}")
print()
print(f"Maximum: {stats['max_temp_c']:.1f}°C ({celsius_to_fahrenheit(stats['max_temp_c']):.1f}°F)")
print(f"  Location: {stats['max_location']}")
print()
print(f"Mean: {stats['mean_temp_c']:.1f}°C ({celsius_to_fahrenheit(stats['mean_temp_c']):.1f}°F)")
print(f"Std Dev: {stats['std_temp_c']:.1f}°C")
print()
print(f"Range: {stats['max_temp_c'] - stats['min_temp_c']:.1f}°C")
print()
print(f"FPA Reference: {stats['fpa_temp_c']:.2f}°C")
print()
print(stats['note'])
print("="*70)
print()

# Sample specific pixels
print("Sample Pixel Temperatures:")
print("="*70)

# Center pixel
center_x, center_y = 320, 256
center_temp = estimator.get_pixel_temperature(frame, center_x, center_y, fpa_temp_c)
print(f"Center ({center_x}, {center_y}): {center_temp:.1f}°C ({celsius_to_fahrenheit(center_temp):.1f}°F)")

# Top-left corner
corner_temp = estimator.get_pixel_temperature(frame, 100, 100, fpa_temp_c)
print(f"Corner (100, 100): {corner_temp:.1f}°C ({celsius_to_fahrenheit(corner_temp):.1f}°F)")

# Hottest spot
hot_x, hot_y = stats['max_location']
hot_temp = estimator.get_pixel_temperature(frame, hot_x, hot_y, fpa_temp_c)
print(f"Hottest ({hot_x}, {hot_y}): {hot_temp:.1f}°C ({celsius_to_fahrenheit(hot_temp):.1f}°F)")

# Coldest spot
cold_x, cold_y = stats['min_location']
cold_temp = estimator.get_pixel_temperature(frame, cold_x, cold_y, fpa_temp_c)
print(f"Coldest ({cold_x}, {cold_y}): {cold_temp:.1f}°C ({celsius_to_fahrenheit(cold_temp):.1f}°F)")

print("="*70)
print()

# Visualize temperature map
print("Creating temperature visualization...")

# Normalize temperature map for display
temp_min = temp_map.min()
temp_max = temp_map.max()
temp_normalized = ((temp_map - temp_min) / (temp_max - temp_min) * 255).astype(np.uint8)

# Apply colormap
temp_colored = cv2.applyColorMap(temp_normalized, cv2.COLORMAP_JET)

# Add temperature overlay
temp_overlay = temp_colored.copy()

# Draw crosshair at hottest spot
cv2.circle(temp_overlay, stats['max_location'], 10, (255, 255, 255), 2)
cv2.line(temp_overlay,
         (stats['max_location'][0] - 15, stats['max_location'][1]),
         (stats['max_location'][0] + 15, stats['max_location'][1]),
         (255, 255, 255), 2)
cv2.line(temp_overlay,
         (stats['max_location'][0], stats['max_location'][1] - 15),
         (stats['max_location'][0], stats['max_location'][1] + 15),
         (255, 255, 255), 2)

# Add text
cv2.putText(temp_overlay, f"Max: {stats['max_temp_c']:.1f}C",
           (stats['max_location'][0] + 20, stats['max_location'][1]),
           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

cv2.putText(temp_overlay, f"Range: {temp_min:.1f}C to {temp_max:.1f}C",
           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

# Display
print("Displaying temperature map (press 'q' to quit)...")
print()

cv2.imshow("Temperature Map (Pseudo-Radiometric)", temp_overlay)
cv2.imshow("Original Thermal", frame)

print("="*70)
print("Interactive Mode")
print("="*70)
print("Press 'q' to quit")
print("Press 's' to save screenshot")
print("Press 'c' to perform calibration (instructions will appear)")
print("="*70)

while True:
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord('s'):
        cv2.imwrite('temperature_map.png', temp_overlay)
        cv2.imwrite('thermal_original.png', frame)
        print("Screenshots saved!")
    elif key == ord('c'):
        print()
        print("="*70)
        print("Calibration Instructions")
        print("="*70)
        print("For best accuracy, calibrate using known temperature references:")
        print()
        print("Single-point calibration:")
        print("  1. Point camera at object with known temperature")
        print("  2. Note AGC value of that pixel")
        print("  3. Call: estimator.calibrate_single_point(agc_value, known_temp, fpa_temp)")
        print()
        print("Two-point calibration (better):")
        print("  1. Point camera at cold reference (e.g., ice water = 0°C)")
        print("  2. Point camera at hot reference (e.g., hot water = 80°C)")
        print("  3. Call: estimator.calibrate_two_point(agc_low, temp_low, agc_high, temp_high, fpa_temp)")
        print()
        print("Example:")
        print("  estimator.calibrate_single_point(128, 25.0, fpa_temp_c)")
        print("  estimator.calibrate_two_point(50, 0.0, 200, 100.0, fpa_temp_c)")
        print("="*70)
        print()

cv2.destroyAllWindows()
camera.release()

print()
print("="*70)
print("Test Complete")
print("="*70)
print()
print("Summary:")
print(f"  Temperature range: {temp_min:.1f}°C to {temp_max:.1f}°C")
print(f"  Hot spot: {stats['max_temp_c']:.1f}°C at {stats['max_location']}")
print(f"  Accuracy: ±5-10°C (pseudo-radiometric)")
print()
print("Next steps:")
print("  1. Use this for hot spot detection and relative measurements")
print("  2. Calibrate with known temperatures for better accuracy")
print("  3. Integrate into main application")
print("  4. Optionally add true 16-bit USB backend later")
print()
print("Note: This is a hobby project - we're trading complexity for time!")
print("="*70)
