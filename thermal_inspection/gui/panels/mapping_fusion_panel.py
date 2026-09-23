"""
3D Mapping Fusion settings tab - Start/Finish/Reset scan controls, texture-
source selector, tracking-quality status, and the live world viewport.

Reuses Fusion3DPointCloudView (fusion_3d_panel.py) as-is for rendering -
its update_point_cloud(vertices, colors) method is already fully generic
(not RealSense-alignment-specific), so this panel just feeds it the frozen
WorldPointCloud's points/colors instead of a per-frame throwaway preview
cloud. This mode's state semantics (idle/scanning/mapped, tracking
good/degraded/lost) are different enough from the existing 3D Fusion tab's
(hardware-available/thermal-aligned) that they're tracked here, in this
panel, rather than added onto Fusion3DPointCloudView itself.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
)
from PyQt6.QtCore import pyqtSignal

from thermal_inspection.gui.panels.fusion_3d_panel import Fusion3DPointCloudView

TEXTURE_SOURCES = ["thermal", "rgb", "blend"]
TEXTURE_SOURCE_LABELS = {
    "thermal": "Thermal",
    "rgb": "RGB",
    "blend": "Blend",
}


class MappingFusionPanel(QWidget):
    start_scan_requested = pyqtSignal()
    finish_scan_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    texture_source_changed = pyqtSignal(str)
    save_requested = pyqtSignal()
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self._start_button = QPushButton("Start Mapping")
        self._finish_button = QPushButton("Finish Mapping")
        self._reset_button = QPushButton("Reset World")
        self._start_button.clicked.connect(self.start_scan_requested.emit)
        self._finish_button.clicked.connect(self.finish_scan_requested.emit)
        self._reset_button.clicked.connect(self.reset_requested.emit)
        controls.addWidget(self._start_button)
        controls.addWidget(self._finish_button)
        controls.addWidget(self._reset_button)
        layout.addLayout(controls)

        persistence_row = QHBoxLayout()
        self._save_button = QPushButton("Save World...")
        self._load_button = QPushButton("Load World...")
        self._save_button.clicked.connect(self.save_requested.emit)
        self._load_button.clicked.connect(self.load_requested.emit)
        persistence_row.addWidget(self._save_button)
        persistence_row.addWidget(self._load_button)
        layout.addLayout(persistence_row)

        texture_row = QHBoxLayout()
        texture_row.addWidget(QLabel("Texture source:"))
        self._texture_source_combo = QComboBox()
        for key in TEXTURE_SOURCES:
            self._texture_source_combo.addItem(TEXTURE_SOURCE_LABELS[key], key)
        self._texture_source_combo.currentIndexChanged.connect(self._on_texture_source_changed)
        texture_row.addWidget(self._texture_source_combo)
        layout.addLayout(texture_row)

        self._status_label = QLabel("State: idle")
        layout.addWidget(self._status_label)

        self.point_cloud_view = Fusion3DPointCloudView()
        layout.addWidget(self.point_cloud_view)

    def _on_texture_source_changed(self, index: int):
        key = self._texture_source_combo.itemData(index)
        if key:
            self.texture_source_changed.emit(key)

    def set_status(self, state: str, quality_state: str, point_count: int):
        """state: 'idle'|'scanning'|'mapped'. quality_state: 'n/a'|'good'|'degraded'|'lost'."""
        text = f"State: {state}  |  Tracking: {quality_state}  |  Points: {point_count:,}"
        if quality_state == "lost":
            text += "\nTracking lost - point the camera back at a mapped area, or Reset World."
        self._status_label.setText(text)

    def update_point_cloud(self, vertices, colors):
        """Delegates straight to the embedded Fusion3DPointCloudView."""
        self.point_cloud_view.update_point_cloud(vertices, colors)
