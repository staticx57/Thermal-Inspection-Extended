"""
Entry point for running thermal_inspection as a module:
    python -m thermal_inspection

This uses the modular CLI extracted from inspection_main.py.
"""
import sys
import os

# Add parent directory to path for legacy imports during migration
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Use the new modular CLI
from .cli import main

if __name__ == '__main__':
    sys.exit(main())
