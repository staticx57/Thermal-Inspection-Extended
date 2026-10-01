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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QListWidget
)
from PyQt6.QtCore import pyqtSignal

from thermal_inspection.processing import world_units
from thermal_inspection.processing.world_thermal import VIEW_MODES, VIEW_MODE_LABELS

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
    view_mode_changed = pyqtSignal(str)
    export_thermal_requested = pyqtSignal()
    hotspot_selected = pyqtSignal(int)      # row in the hotspot list (same order as the last set_hotspots())

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

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("Show:"))
        self._view_mode_combo = QComboBox()
        for key in VIEW_MODES:
            self._view_mode_combo.addItem(VIEW_MODE_LABELS[key], key)
        self._view_mode_combo.currentIndexChanged.connect(self._on_view_mode_changed)
        view_row.addWidget(self._view_mode_combo)
        self._export_button = QPushButton("Export Temperatures...")
        self._export_button.setToolTip("Save every world point's position and temperature (live, peak, change) as CSV")
        self._export_button.clicked.connect(self.export_thermal_requested.emit)
        view_row.addWidget(self._export_button)
        layout.addLayout(view_row)

        self._status_label = QLabel("State: idle")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)
        self._header_text = "State: idle"
        self._default_note = ""
        self._message = ""

        self._thermal_label = QLabel("")
        self._thermal_label.setWordWrap(True)
        self._thermal_label.setVisible(False)
        layout.addWidget(self._thermal_label)

        # The 3D world itself is shown full-size in the MAIN view (gui/widgets/world_viewer.py) while this mode is
        # active; this tab holds the controls and text only.
        self._hint_label = QLabel(
            "The 3D world is shown in the main view. Click a point to read its temperature; use Measure there "
            "to measure between two points."
        )
        self._hint_label.setWordWrap(True)
        self._hint_label.setStyleSheet("color: gray;")
        layout.addWidget(self._hint_label)

        self._hotspot_title = QLabel("Hotspots (click to fly to one)")
        self._hotspot_title.setVisible(False)
        layout.addWidget(self._hotspot_title)
        self._hotspot_list = QListWidget()
        self._hotspot_list.setMaximumHeight(130)
        self._hotspot_list.setVisible(False)
        self._hotspot_list.currentRowChanged.connect(self._on_hotspot_row)
        layout.addWidget(self._hotspot_list)
        self._hotspot_rows = 0
        layout.addStretch(1)

        # Establishes the initial button-enabled states (idle: Start
        # enabled, Finish/Reset disabled) from one source of truth instead
        # of duplicating the gating logic here - see set_status().
        self.set_status("idle", "n/a", 0)

    def _on_view_mode_changed(self, index: int):
        key = self._view_mode_combo.itemData(index)
        if key:
            self.view_mode_changed.emit(key)

    def set_thermal_summary(self, text: str):
        """Temperature range / hottest places / changes-vs-loaded-world text from WorldMapper.thermal_summary()."""
        text = text or ""
        if text != self._thermal_label.text():
            self._thermal_label.setText(text)
        self._thermal_label.setVisible(bool(text))

    def _on_texture_source_changed(self, index: int):
        key = self._texture_source_combo.itemData(index)
        if key:
            self.texture_source_changed.emit(key)

    def set_status(self, state: str, quality_state: str, point_count: int):
        """state: 'idle'|'scanning'|'mapped'. quality_state: 'n/a'|'good'|'degraded'|'lost'.

        Also drives Start/Finish/Reset button gating from this single
        status update - without it, clicking Finish before Start (or
        twice) raised an uncaught RuntimeError from WorldMapper.finish_scan(),
        and clicking Reset with nothing scanned/mapped was a no-op with no
        indication either way.
        """
        self._header_text = f"State: {state}  |  Tracking: {quality_state}  |  Points: {point_count:,}"
        self._default_note = (
            "Tracking lost - point the camera back at a mapped area, or Reset World."
            if quality_state == "lost" else ""
        )
        self._message = ""          # guidance from the mapper is per-tick; a fresh status clears any stale one
        self._refresh_status_label()

        self._start_button.setEnabled(state in ("idle", "mapped"))
        self._finish_button.setEnabled(state == "scanning")
        self._reset_button.setEnabled(state != "idle" or point_count > 0)
        self._export_button.setEnabled(state == "mapped")
        if state != "mapped":
            self.set_thermal_summary("")
            self.set_hotspots([])

    def set_message(self, text: str):
        """Guidance line from WorldMapper (e.g. 'Scan tracking lost - slow down...', 'Looking for the camera...').
        Replaces the built-in note under the status line until the next set_status()."""
        text = text or ""
        if text != self._message:
            self._message = text
            self._refresh_status_label()

    def _refresh_status_label(self):
        note = self._message or self._default_note
        self._status_label.setText(self._header_text + (f"\n{note}" if note else ""))

    def set_hotspots(self, markers, unit: str = "C"):
        """List the world's hotspot/change markers (processing.world_thermal.Marker); clicking a row emits
        hotspot_selected(row). Replaces the list only when its content changed so a selection isn't lost each refresh."""
        rows = []
        for m in markers:
            shown = (world_units.format_delta(m.value, unit) if m.kind in ("warm", "cool")
                     else world_units.format_temp(m.value, unit))
            x, y, z = m.xyz
            rows.append(f"{m.label}  {shown}   ({x:+.2f}, {y:+.2f}, {z:+.2f}) m")
        current = [self._hotspot_list.item(i).text() for i in range(self._hotspot_list.count())]
        if rows != current:
            self._hotspot_list.blockSignals(True)
            self._hotspot_list.clear()
            self._hotspot_list.addItems(rows)
            self._hotspot_list.blockSignals(False)
        self._hotspot_rows = len(rows)
        self._hotspot_title.setVisible(bool(rows))
        self._hotspot_list.setVisible(bool(rows))

    def _on_hotspot_row(self, row: int):
        if 0 <= row < self._hotspot_rows:
            self.hotspot_selected.emit(row)
