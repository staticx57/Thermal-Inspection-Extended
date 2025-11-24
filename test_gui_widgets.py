#!/usr/bin/env python3
"""
Test script to launch the GUI and visually inspect widget layout issues
"""

import sys
from PyQt6.QtWidgets import QApplication
from inspection_main import ThermalInspectionApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Create main application
    main_window = ThermalInspectionApp()
    main_window.show()
    
    # Enable developer mode to see all controls
    main_window.gui.control_panel.show_developer_controls(True)
    
    print("=" * 60)
    print("GUI Widget Test Launched")
    print("=" * 60)
    print("Please visually inspect for:")
    print("  1. Text truncation in buttons")
    print("  2. Text truncation in labels")
    print("  3. Text truncation in list items")
    print("  4. Improper spacing between widgets")
    print("  5. Overlapping widgets")
    print("  6. Widgets that don't fit in their containers")
    print("=" * 60)
    
    sys.exit(app.exec())
