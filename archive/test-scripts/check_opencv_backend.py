#!/usr/bin/env python3
"""
Diagnostic script to check OpenCV backend and build configuration
This helps identify window backend issues that might cause GUI jitter
"""
import cv2
import sys

print("=" * 70)
print("OpenCV Backend Diagnostics")
print("=" * 70)

# OpenCV version
print(f"\nOpenCV Version: {cv2.__version__}")

# Build information
print("\nOpenCV Build Information:")
print("-" * 70)
build_info = cv2.getBuildInformation()

# Extract relevant lines
relevant_keywords = ['GUI', 'GTK', 'QT', 'OpenGL', 'Video I/O', 'backend']
for line in build_info.split('\n'):
    line_lower = line.lower()
    if any(keyword.lower() in line_lower for keyword in relevant_keywords):
        print(line)

# Check available window flags
print("\n" + "=" * 70)
print("Available Window Flags:")
print("-" * 70)
window_flags = [attr for attr in dir(cv2) if 'WINDOW' in attr]
for flag in window_flags:
    print(f"  {flag}")

# Test window backend by creating a small test window
print("\n" + "=" * 70)
print("Testing Window Creation...")
print("-" * 70)
try:
    import numpy as np

    # Create a small test frame
    test_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    test_frame[:] = (50, 50, 50)  # Gray background

    # Create window
    cv2.namedWindow("Backend Test", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Backend Test", 100, 100)
    cv2.imshow("Backend Test", test_frame)

    print("✓ Window created successfully")
    print("  Press any key to close...")

    cv2.waitKey(2000)  # Wait 2 seconds
    cv2.destroyAllWindows()

    print("✓ Window closed successfully")

except Exception as e:
    print(f"✗ Error creating window: {e}")
    sys.exit(1)

print("\n" + "=" * 70)
print("Diagnostics Complete")
print("=" * 70)
