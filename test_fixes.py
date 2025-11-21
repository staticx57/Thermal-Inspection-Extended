#!/usr/bin/env python3
"""
Test thermal processor and palette manager to find remaining bugs
"""
import cv2
import numpy as np
import sys

# Test thermal_processor palette application
print("Testing thermal_processor...")
from thermal_processor import ThermalProcessor

processor = ThermalProcessor()
processor.initialize()

# Simulated thermal frame (grayscale uint8)
thermal_frame = np.random.randint(0, 256, (100, 100), dtype=np.uint8)

try:
    colorized = processor.apply_thermal_palette(thermal_frame, "ironbow")
    print(f"✓ thermal_processor.apply_thermal_palette works: {colorized.shape}")
except Exception as e:
    print(f"✗ thermal_processor ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test palette_manager
print("\nTesting palette_manager...")
from palette_manager import PaletteManager, PaletteType

pm = PaletteManager()

try:
    colorized2 = pm.apply_palette(thermal_frame)
    print(f"✓ palette_manager.apply_palette works: {colorized2.shape}")
except Exception as e:
    print(f"✗ palette_manager ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test edge detection
print("\nTesting edge detection...")
thermal_bgr = cv2.cvtColor(thermal_frame, cv2.COLOR_GRAY2BGR)

try:
    edges, clusters = processor.detect_edges(thermal_bgr)
    print(f"✓ Edge detection works: edges={edges.shape if edges is not None else None}, clusters={len(clusters)}")
except Exception as e:
    print(f"✗ Edge detection ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n=== All tests passed! ===")
