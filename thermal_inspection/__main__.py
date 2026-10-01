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
import importlib.util

# Open3D (3D Mapping Fusion) must be imported BEFORE PyQt6: if Qt's DLLs load first, Open3D's pybind module fails with
# "DLL load failed ... initialization routine failed" on Windows. ~0.6 s; skipped when it isn't installed.
if importlib.util.find_spec("open3d") is not None:
    try:
        import open3d  # noqa: F401
    except Exception as _e:
        logging.getLogger(__name__).warning(f"Open3D preload failed, 3D Mapping Fusion unavailable: {_e}")

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
