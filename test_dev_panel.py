#!/usr/bin/env python3
"""Test DeveloperPanel initialization"""
import sys

# Test importing DeveloperPanel directly
try:
    from PyQt5.QtWidgets import QApplication
    from developer_panel import DeveloperPanel
    
    app = QApplication(sys.argv)
    panel = DeveloperPanel()
    print("SUCCESS: DeveloperPanel created without errors!")
    sys.exit(0)
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
