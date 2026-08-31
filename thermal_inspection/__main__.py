"""
Entry point for running thermal_inspection as a module:
    python -m thermal_inspection

This uses the modular CLI extracted from inspection_main.py.
"""
import os
os.environ["OPENCV_VIDEOIO_PRIORITY_OBSENSOR"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"

import sys
import logging

def _global_exception_handler(exctype, value, traceback):
    logger = logging.getLogger('CRASH')
    logger.critical("Unhandled exception", exc_info=(exctype, value, traceback))
    sys.__excepthook__(exctype, value, traceback)

sys.excepthook = _global_exception_handler
sys.coinit_flags = 0  # Force MTA so OpenCV DirectShow doesn't fail on the main thread

# Add parent directory to path for legacy imports during migration
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Use the new modular CLI
from .cli import main

if __name__ == '__main__':
    sys.exit(main())
