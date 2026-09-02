#!/bin/bash
cd "$(dirname "$0")/.."
# Run the thermal + RGB fusion tool with proper EGL configuration
# (for Jetson/headless-GPU setups where VPI needs a surfaceless EGL platform).
# Run from repo root: ./scripts/run_vpi.sh [thermal_inspection CLI args]
#
# Usage:
#   ./scripts/run_vpi.sh                  # Default with RGB fusion
#   ./scripts/run_vpi.sh --disable-rgb    # Thermal only mode

export EGL_PLATFORM=surfaceless
python3 -m thermal_inspection "$@"