"""
Camera Calibration tab: ONE place for everything that registers the thermal and RGB views, laid out in the order you use it.

  Strip (always visible)   registration + parallax status at a glance, ONE shared scene distance (typed, or measured
                           from a depth camera), alignment overlay, and a "Check alignment" residual measurement.
  1 Register               the fixed part: calibrate from the live feeds / load / save, fine-tune shift and zoom,
                           auto-estimate, crop.
  2 Parallax               the distance-dependent part: enable, correction target, depth method, depth/displacement views.
  3 Rig                    the physical mounting the maths needs: baseline, lens focal length / sensor width.

The Temp Calibration tab (radiometric, absolute temperature) is unrelated and stays separate.
"""
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QTabWidget, QVBoxLayout, QWidget)

from thermal_inspection.gui.panels.alignment_panel import AlignmentPanel, make_distance_spin
from thermal_inspection.gui.panels.parallax_panel import ParallaxPanel

logger = logging.getLogger(__name__)


class AlignmentTab(QWidget):
    show_alignment_overlay_toggled = pyqtSignal(bool)
    measure_distance_requested = pyqtSignal()
    check_alignment_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # ---- strip
        strip = QFrame()
        strip.setFrameShape(QFrame.Shape.StyledPanel)
        sv = QVBoxLayout(strip)
        sv.setContentsMargins(8, 6, 8, 6)
        sv.setSpacing(4)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        sv.addWidget(self.summary_label)

        row = QHBoxLayout()
        row.addWidget(QLabel("Scene distance:"))
        self.distance_spin = make_distance_spin()
        self.distance_spin.setToolTip("How far away the scene you are aligning on is. Used when calibrating, "
                                      "auto-estimating, and recorded with the calibration so it can be combined "
                                      "with parallax correction.")
        row.addWidget(self.distance_spin)
        self.measure_btn = QPushButton("Measure")
        self.measure_btn.setToolTip("Read the distance from the depth camera (centre of the view). Needs a RealSense.")
        self.measure_btn.clicked.connect(self.measure_distance_requested.emit)
        row.addWidget(self.measure_btn)
        row.addStretch()
        sv.addLayout(row)

        row = QHBoxLayout()
        self.overlay_checkbox = QCheckBox("Alignment overlay")
        self.overlay_checkbox.setToolTip(
            "Thermal edges (cyan) and RGB edges (magenta) on the corrected frames: aligned edges land on top of each "
            "other, misalignment shows as colour-fringed double edges. Use it while adjusting anything here.")
        self.overlay_checkbox.toggled.connect(self.show_alignment_overlay_toggled.emit)
        row.addWidget(self.overlay_checkbox)
        self.check_btn = QPushButton("Check alignment")
        self.check_btn.setToolTip("Measure the residual misregistration between the live thermal and corrected RGB "
                                  "frames (all corrections applied)")
        self.check_btn.clicked.connect(self.check_alignment_requested.emit)
        row.addWidget(self.check_btn)
        row.addStretch()
        sv.addLayout(row)
        self.check_label = QLabel("")
        self.check_label.setWordWrap(True)
        self.check_label.setStyleSheet("font-size: 9pt;")
        sv.addWidget(self.check_label)
        outer.addWidget(strip)

        # ---- pages
        self.parallax_panel = ParallaxPanel()
        self.register_panel = AlignmentPanel(distance_spin=self.distance_spin)
        self.pages = QTabWidget()
        self.pages.addTab(self.register_panel, "1 Register")
        self.pages.addTab(self.parallax_panel, "2 Parallax")
        self.pages.addTab(self._rig_page(), "3 Rig")
        outer.addWidget(self.pages, 1)

        self._registration = {"loaded": False}
        self._parallax_on = False
        self._method = self.parallax_panel.get_depth_method()
        self.parallax_panel.parallax_toggled.connect(self._on_parallax_toggled)
        self.parallax_panel.depth_method_changed.connect(self._on_method_changed)
        self._refresh_summary()

    def _rig_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(8, 8, 8, 8)
        note = QLabel("The physical mounting. Parallax correction and the auto-estimate use these numbers; a "
                      "calibration from the live feeds measures the result directly and does not depend on them.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 9pt;")
        v.addWidget(note)
        v.addWidget(self.parallax_panel.geometry_group)
        v.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(page)
        return scroll

    # -------------------------------------------------------------- state from the app

    def set_registration_status(self, st: dict):
        self._registration = st
        self.register_panel.set_status(st)
        self._refresh_summary()

    def set_distance(self, metres: float):
        self.distance_spin.setValue(metres)

    def set_check_result(self, result: dict):
        verdict = result.get("verdict", "")
        colour = {"good": "#66bb6a", "ok": "#d4a017", "poor": "#ff6666"}.get(result.get("level"), "#888888")
        self.check_label.setStyleSheet(f"font-size: 9pt; color: {colour};")
        self.check_label.setText(verdict)

    # -------------------------------------------------------------- summary strip

    def _on_parallax_toggled(self, on: bool):
        self._parallax_on = on
        self._refresh_summary()

    def _on_method_changed(self, method: str):
        self._method = method
        self._refresh_summary()

    @staticmethod
    def _pill(text, colour):
        return f"<span style='color:{colour}; font-weight:bold'>{text}</span>"

    def _refresh_summary(self):
        r = self._registration
        if not r.get("loaded"):
            reg = self._pill("not calibrated", "#ff4444") + " (aspect-ratio crop only)"
        else:
            bits = []
            if r.get("rms_px") is not None:
                bits.append(f"RMS {r['rms_px']:.2f} px")
            bits.append(f"at {r['distance_m']:g} m" if r.get("distance_m") else "distance unknown")
            reg = (self._pill("calibrated", "#4CAF50") if r.get("enabled")
                   else self._pill("calibrated, switched off", "#d4a017")) + " " + ", ".join(bits)
        par = (self._pill("on", "#4CAF50") + f" ({self._method})") if self._parallax_on else self._pill("off", "#888888")
        text = f"<b>Registration:</b> {reg}<br><b>Parallax:</b> {par}"
        if r.get("loaded") and r.get("enabled") and self._parallax_on:
            if r.get("parallax_composed"):
                text += "<br>" + self._pill("Combined correctly", "#66bb6a") + " (baseline shift not applied twice)"
            else:
                text += "<br>" + self._pill("Applied twice", "#ff6666") + ": re-calibrate here to record the distance"
        self.summary_label.setText(text)
