#!/bin/bash
# Run thermal + RGB fusion road monitor with proper EGL configuration
#
# Usage:
#   ./run_vpi.sh                  # Default with RGB fusion
#   ./run_vpi.sh --disable-rgb    # Thermal only mode
#   ./run_vpi.sh --scale 2.5      # Custom scaling
#   ./run_vpi.sh --fullscreen     # Fullscreen mode

export EGL_PLATFORM=surfaceless
python3 main.py "$@"