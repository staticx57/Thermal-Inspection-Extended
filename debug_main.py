#!/usr/bin/env python3
"""Debug wrapper for main.py with full error capture"""
import sys
import traceback
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

try:
    # Import and run main
    import main
    main.main()
except SystemExit as e:
    print(f"\nSystemExit caught with code: {e.code}")
    sys.exit(e.code)
except Exception as e:
    print("\n" + "=" * 70)
    print("EXCEPTION CAUGHT:")
    print("=" * 70)
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    print("=" * 70)
    sys.exit(1)
