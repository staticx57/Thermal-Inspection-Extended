"""
Test auto-detection with detailed logging
"""
import sys
import logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

from camera_factory import autodetect_camera_types

print("=" * 80)
print("TESTING AUTO-DETECTION")
print("=" * 80)

thermal_id, rgb_id = autodetect_camera_types()

print("=" * 80)
print(f"RESULTS: Thermal={thermal_id}, RGB={rgb_id}")
print("=" * 80)
