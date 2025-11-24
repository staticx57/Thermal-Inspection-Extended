#!/usr/bin/env python3
"""
Quick GUI test to identify polish issues
"""
import sys
from PyQt6.QtWidgets import QApplication
from inspection_gui_qt import InspectionAppWindow

class MockApp:
    """Mock application for testing GUI"""
    def __init__(self):
        self.thermal_connected = False
        self.rgb_available = False
        self.is_flir_boson = False
        self.thermal_camera = None

    def cycle_palette(self):
        print("Palette cycled")

    def cycle_view_mode(self):
        print("View mode cycled")

    def cycle_fusion_mode(self):
        print("Fusion mode cycled")

    def cycle_fusion_alpha(self):
        print("Alpha cycled")

    def cycle_fusion_priority(self):
        print("Priority cycled")

    def toggle_recording(self, enabled):
        print(f"Recording: {enabled}")

    def capture_snapshot(self):
        print("Snapshot captured")

    def toggle_freeze(self, enabled):
        print(f"Freeze: {enabled}")

    def toggle_motion(self, enabled):
        print(f"Motion: {enabled}")

    def toggle_edge(self, enabled):
        print(f"Edge: {enabled}")

    def toggle_anomaly_priority(self, enabled):
        print(f"Anomaly priority: {enabled}")

    def set_enabled_anomaly_types(self, types):
        print(f"Anomaly types: {types}")

    def set_manual_threshold_enabled(self, enabled):
        print(f"Manual threshold: {enabled}")

    def lock_baseline(self, enabled):
        print(f"Baseline locked: {enabled}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mock_app = MockApp()
    window = InspectionAppWindow(mock_app)
    window.show()

    print("=" * 60)
    print("GUI TEST - Look for:")
    print("  - Layout issues")
    print("  - Missing tooltips")
    print("  - Inconsistent styling")
    print("  - Unclear labels")
    print("  - Poor spacing")
    print("=" * 60)

    sys.exit(app.exec())
