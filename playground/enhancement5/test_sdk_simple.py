#!/usr/bin/env python3
"""
Simple SDK Bridge Test - Debug GET commands
"""

import sys
import os
import logging

# Setup verbose logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(name)s - %(levelname)s: %(message)s'
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)

from flirpy.camera.boson import Boson
from flirpy_sdk_bridge import FlirpySDKBridge, GainMode

print("=" * 60)
print("Simple SDK Test - Debug GET Commands")
print("=" * 60)

camera = Boson(port='COM7')
print(f"Connected to camera on COM7")

bridge = FlirpySDKBridge(camera)
print(f"SDK Available: {bridge.is_sdk_available()}")

print("\n--- Testing SET gamma ---")
success = bridge.set_agc_gamma(1.5)
print(f"Set gamma result: {success}")

print("\n--- Testing GET gamma ---")
gamma = bridge.get_agc_gamma()
print(f"Get gamma result: {gamma}")

print("\n--- Testing SET emissivity ---")
success = bridge.set_emissivity(0.90)
print(f"Set emissivity result: {success}")

print("\n--- Testing GET emissivity ---")
emissivity = bridge.get_emissivity()
print(f"Get emissivity result: {emissivity}")

print("\n--- Testing GET gain mode ---")
gain_mode = bridge.get_gain_mode()
print(f"Get gain mode result: {gain_mode}")

camera.close()
print("\nCamera closed")
