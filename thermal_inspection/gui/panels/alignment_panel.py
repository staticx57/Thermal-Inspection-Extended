"""
Alignment Calibration Panel

Controls for the static RGB -> thermal homography (cameras/camera_calibration.py): calibrate from the live feeds, load or
save a file, switch it on/off, and see how it is composed with parallax correction. The counterpart of the Parallax
panel for the fixed part of the geometry. (The "Calibration" tab is the RADIOMETRIC, temperature calibration.)
"""
import logging
import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGroupBox, QHBoxLayout, QLabel,
                             QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from thermal_inspection.gui.themes import set_role

logger = logging.getLogger(__name__)

METHOD_LABELS = [("Edges (thermal vs visible)", "edges"), ("Features (brightness)", "features"),
                 ("Checkerboard", "checkerboard")]


def make_distance_spin() -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.1, 50.0)
    spin.setValue(2.0)
    spin.setDecimals(2)
    spin.setSuffix(" m")
    spin.setSingleStep(0.1)
    spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return spin


class AlignmentPanel(QWidget):
    load_requested = pyqtSignal(str)
    save_requested = pyqtSignal(str)
    clear_requested = pyqtSignal()
    enabled_changed = pyqtSignal(bool)
    capture_requested = pyqtSignal(float, str, int, int)     # distance_m, method, board cols, board rows
    shift_changed = pyqtSignal(int, int)  # (dx, dy) pixels
    auto_alignment_requested = pyqtSignal(float, bool, bool)  # working_distance_m, refine_with_depth, refine_from_image
    auto_crop_requested = pyqtSignal()
    crop_reset_requested = pyqtSignal()
    zoom_changed = pyqtSignal(float)  # crop-in zoom factor, 1.0 = none

    def __init__(self, distance_spin=None, parent=None):
        super().__init__(parent)
        # the scene distance is shared with the tab's strip (calibrate + auto-estimate use the same number)
        self.distance_spin = distance_spin if distance_spin is not None else make_distance_spin()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # ---- status
        box = QGroupBox("Registration")
        v = QVBoxLayout(box)
        self.status_label = QLabel("Not calibrated")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        set_role(self.status_label, "heading")
        v.addWidget(self.status_label)
        self.detail_label = QLabel("RGB is cropped to the thermal aspect ratio (no registration).")
        self.detail_label.setWordWrap(True)
        set_role(self.detail_label, "hint")
        v.addWidget(self.detail_label)
        self.enable_checkbox = QCheckBox("Apply calibration")
        self.enable_checkbox.setEnabled(False)
        self.enable_checkbox.setToolTip("Switch the loaded calibration on or off without discarding it")
        v.addWidget(self.enable_checkbox)
        self.stack_note_label = QLabel("")
        self.stack_note_label.setWordWrap(True)
        set_role(self.stack_note_label, "warn")
        self.composition_label = QLabel("")
        self.composition_label.setWordWrap(True)
        set_role(self.composition_label, "small")
        v.addWidget(self.composition_label)
        v.addWidget(self.stack_note_label)
        layout.addWidget(box)

        # ---- capture
        cap = QGroupBox("Calibrate From Live Feeds")
        c = QVBoxLayout(cap)
        hint = QLabel("Point both cameras at the same flat, textured scene (or a heated checkerboard), hold still, "
                      "set the scene distance above, and capture. The distance is recorded with the calibration so "
                      "parallax correction can be combined with it.")
        hint.setWordWrap(True)
        set_role(hint, "hint")
        c.addWidget(hint)
        row = QHBoxLayout()
        row.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        for label, key in METHOD_LABELS:
            self.method_combo.addItem(label, key)
        row.addWidget(self.method_combo)
        row.addStretch()
        c.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Inner corners:"))
        self.cols_spin, self.rows_spin = QSpinBox(), QSpinBox()
        for s, val in ((self.cols_spin, 9), (self.rows_spin, 6)):
            s.setRange(3, 30)
            s.setValue(val)
            s.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        row.addWidget(self.cols_spin)
        row.addWidget(QLabel("x"))
        row.addWidget(self.rows_spin)
        row.addStretch()
        self.board_row = QWidget()
        self.board_row.setLayout(row)
        c.addWidget(self.board_row)
        self.board_row.setVisible(False)
        self.capture_btn = QPushButton("Capture && Calibrate")
        self.capture_btn.setMinimumHeight(35)
        c.addWidget(self.capture_btn)
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        set_role(self.message_label, "small")
        self.message_label.setVisible(False)           # only takes space while there is something to say
        c.addWidget(self.message_label)
        layout.addWidget(cap)

        # ---- static camera-position corrections (moved here from the Parallax tab)
        # A fixed mounting offset between the two cameras doesn't vary with
        # distance, so depth-based correction (which only handles the X-axis
        # baseline disparity) can't and shouldn't try to correct for it -
        # this is a plain constant translation, independent of and additive
        # to whatever depth-based correction does. Works even when
        # depth-based correction (above) is disabled. Just the manual
        # shift/zoom controls here - the automatic Auto-Calculate
        # Alignment/Auto-Crop actions get their OWN group below, since
        # calling both "Manual Alignment Shift" was misleading about what
        # was actually inside it.
        shift_group = QGroupBox("Fine-Tune (Manual)")
        shift_layout = QVBoxLayout()
        shift_layout.setSpacing(6)
        shift_layout.setContentsMargins(8, 8, 8, 8)

        shift_info_label = QLabel(
            "Fine-tune registration with a constant pixel shift - useful for\n"
            "a fixed mounting offset that doesn't change with distance."
        )
        shift_info_label.setWordWrap(True)
        set_role(shift_info_label, "hint")
        shift_layout.addWidget(shift_info_label)

        shift_x_layout = QHBoxLayout()
        shift_x_layout.setContentsMargins(0, 0, 0, 0)
        shift_x_layout.addWidget(QLabel("Horizontal:"))
        self.shift_x_spin = QSpinBox()
        self.shift_x_spin.setRange(-200, 200)
        self.shift_x_spin.setValue(0)
        self.shift_x_spin.setSuffix(" px")
        self.shift_x_spin.setToolTip("Positive shifts the thermal image right")
        self.shift_x_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.shift_x_spin.valueChanged.connect(self._on_shift_changed)
        shift_x_layout.addWidget(self.shift_x_spin)
        shift_layout.addLayout(shift_x_layout)

        shift_y_layout = QHBoxLayout()
        shift_y_layout.setContentsMargins(0, 0, 0, 0)
        shift_y_layout.addWidget(QLabel("Vertical:"))
        self.shift_y_spin = QSpinBox()
        self.shift_y_spin.setRange(-200, 200)
        self.shift_y_spin.setValue(0)
        self.shift_y_spin.setSuffix(" px")
        self.shift_y_spin.setToolTip("Positive shifts the thermal image down")
        self.shift_y_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.shift_y_spin.valueChanged.connect(self._on_shift_changed)
        shift_y_layout.addWidget(self.shift_y_spin)
        shift_layout.addLayout(shift_y_layout)

        self.reset_shift_btn = QPushButton("Reset Shift")
        self.reset_shift_btn.setToolTip("Reset horizontal/vertical shift to 0")
        self.reset_shift_btn.clicked.connect(self._on_reset_shift)
        shift_layout.addWidget(self.reset_shift_btn)

        # Manual zoom / crop factor - the same crop-and-scale mechanism
        # Auto-Calculate Alignment uses to correct a real FOV mismatch
        # (fov_zoom_factor), but directly user-settable for cases the
        # geometric calculation can't cover on its own: correcting for
        # inaccurate/unknown lens specs by eye, or a deliberate manual
        # crop-in/out. 1.0 = no change; above 1.0 crops in (narrows
        # effective FOV, magnifying the center); below 1.0 shrinks the
        # frame's content and pads the border with black (for when this
        # camera's FOV is narrower than the other's - there's no real
        # pixel data to widen it with, but this at least matches angular
        # scale so real features still line up in position).
        zoom_layout = QHBoxLayout()
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.addWidget(QLabel("Zoom / Crop Factor:"))
        self.zoom_spin = QDoubleSpinBox()
        self.zoom_spin.setRange(0.2, 3.0)
        self.zoom_spin.setValue(1.0)
        self.zoom_spin.setDecimals(3)
        self.zoom_spin.setSuffix("x")
        self.zoom_spin.setSingleStep(0.01)
        self.zoom_spin.setToolTip(
            "Manually crop/scale this frame for correcting FOV mismatch by "
            "eye, independent of the lens geometry on the Parallax tab. 1.0 = no "
            "change; above 1.0 crops in (zooms); below 1.0 shrinks the "
            "content and pads the border with black (for a narrower-FOV "
            "camera - it can't actually see wider, so this only matches "
            "angular scale, not fills in real detail)."
        )
        self.zoom_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_spin)
        shift_layout.addLayout(zoom_layout)

        self.reset_zoom_btn = QPushButton("Reset Zoom")
        self.reset_zoom_btn.setToolTip("Reset zoom/crop factor to 1.0x (no change)")
        self.reset_zoom_btn.clicked.connect(lambda: self.zoom_spin.setValue(1.0))
        shift_layout.addWidget(self.reset_zoom_btn)

        shift_group.setLayout(shift_layout)
        layout.addWidget(shift_group)

        # ====================================================================
        # Auto-Detect Alignment & Crop
        # ====================================================================
        # Both actions here are one-time/on-demand (not run every frame) -
        # Auto-Calculate Alignment computes shift + FOV crop-zoom from the
        # live image (if the checkbox below is on and a confident match is
        # found) or camera geometry otherwise, writing into the SAME
        # shift/zoom fields the Manual Alignment group above shows -
        # manual fine-tuning stays available afterward, this doesn't
        # replace it. Auto-Crop is a second, independent one-time action
        # (not tied to Auto-Calculate Alignment - a purely manual
        # shift/zoom also leaves a border to crop): computes and stores a
        # FIXED border-blank extent once, from whatever shift/zoom is
        # currently in effect - _remap_thermal then uses that fixed value
        # every frame instead of re-deriving it live.
        auto_align_group = QGroupBox("Fine-Tune (Auto) && Crop")
        auto_align_layout = QVBoxLayout()
        auto_align_layout.setSpacing(6)
        auto_align_layout.setContentsMargins(8, 8, 8, 8)

        auto_align_label = QLabel(
            "Or auto-calculate from camera geometry (baseline + FOV, set on the Parallax tab) -\n"
            "runs once, not every frame:"
        )
        auto_align_label.setWordWrap(True)
        set_role(auto_align_label, "hint")
        auto_align_layout.addWidget(auto_align_label)

        self.working_distance_spin = self.distance_spin      # one shared scene distance (strip above)

        self.refine_with_depth_checkbox = QCheckBox("Refine using depth estimation")
        self.refine_with_depth_checkbox.setToolTip(
            "Run the selected depth estimation method (Parallax tab) once on the current frame "
            "to measure the actual scene distance instead of the assumed value above"
        )
        auto_align_layout.addWidget(self.refine_with_depth_checkbox)

        self.refine_from_image_checkbox = QCheckBox("Refine from image content")
        self.refine_from_image_checkbox.setChecked(True)
        self.refine_from_image_checkbox.setToolTip(
            "Measure the actual current shift directly from the live thermal and "
            "RGB frames (image registration) instead of trusting the geometry "
            "formula above - takes priority over it when both frames are "
            "available and the match is confident enough to trust. This is "
            "what \"align based on crop and shift settings in the image\" means: "
            "get the two cameras' physical mounting as good as you can by hand "
            "first, THEN run this to fine-tune the remaining offset from what "
            "the cameras actually see, not from an assumed distance."
        )
        auto_align_layout.addWidget(self.refine_from_image_checkbox)

        self.auto_align_btn = QPushButton("Auto-Calculate Alignment")
        self.auto_align_btn.setToolTip(
            "Compute shift + FOV crop-zoom once from the live image (if the "
            "checkbox above is on and a confident match is found) or camera "
            "geometry otherwise - not run every frame"
        )
        self.auto_align_btn.clicked.connect(self._on_auto_align_clicked)
        auto_align_layout.addWidget(self.auto_align_btn)

        self.auto_align_result_label = QLabel("")
        self.auto_align_result_label.setWordWrap(True)
        set_role(self.auto_align_result_label, "ok")
        auto_align_layout.addWidget(self.auto_align_result_label)

        autocrop_label = QLabel(
            "Once alignment looks right, remove the leftover border -\n"
            "also a one-time action, not recomputed every frame:"
        )
        autocrop_label.setWordWrap(True)
        set_role(autocrop_label, "hint")
        auto_align_layout.addWidget(autocrop_label)

        autocrop_btn_layout = QHBoxLayout()
        autocrop_btn_layout.setContentsMargins(0, 0, 0, 0)
        self.auto_crop_btn = QPushButton("Auto-Crop")
        self.auto_crop_btn.setToolTip(
            "Compute and fix the border-blank extent once from the current "
            "shift/zoom, replacing the per-frame live computation"
        )
        self.auto_crop_btn.clicked.connect(self.auto_crop_requested.emit)
        autocrop_btn_layout.addWidget(self.auto_crop_btn)

        self.reset_crop_btn = QPushButton("Reset Crop")
        self.reset_crop_btn.setToolTip("Discard the fixed crop - recompute the border live every frame again")
        self.reset_crop_btn.clicked.connect(self.crop_reset_requested.emit)
        autocrop_btn_layout.addWidget(self.reset_crop_btn)
        auto_align_layout.addLayout(autocrop_btn_layout)

        self.auto_crop_result_label = QLabel("")
        self.auto_crop_result_label.setWordWrap(True)
        set_role(self.auto_crop_result_label, "ok")
        auto_align_layout.addWidget(self.auto_crop_result_label)

        auto_align_group.setLayout(auto_align_layout)
        layout.addWidget(auto_align_group)


        # ---- files
        files = QGroupBox("Files")
        f = QHBoxLayout(files)
        self.load_btn = QPushButton("Load...")
        self.save_btn = QPushButton("Save...")
        self.clear_btn = QPushButton("Clear")
        for b in (self.load_btn, self.save_btn, self.clear_btn):
            f.addWidget(b)
        layout.addWidget(files)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self.save_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.method_combo.currentIndexChanged.connect(
            lambda: self.board_row.setVisible(self.method_combo.currentData() == "checkerboard"))
        self.capture_btn.clicked.connect(self._on_capture)
        self.enable_checkbox.toggled.connect(self.enabled_changed.emit)
        self.clear_btn.clicked.connect(self.clear_requested.emit)
        self.load_btn.clicked.connect(self._on_load)
        self.save_btn.clicked.connect(self._on_save)

    # -------------------------------------------------------------- user actions

    def _on_capture(self):
        self.show_message("Capturing...", False)
        self.capture_requested.emit(self.distance_spin.value(), self.method_combo.currentData(),
                                    self.cols_spin.value(), self.rows_spin.value())

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Alignment Calibration", "",
                                              "JSON Files (*.json);;All Files (*.*)")
        if path:
            self.load_requested.emit(path)

    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Alignment Calibration", "alignment_calibration.json",
                                              "JSON Files (*.json);;All Files (*.*)")
        if path:
            self.save_requested.emit(path)

    # -------------------------------------------------------------- moved controls

    def _on_shift_changed(self, _value: int):
        """Handle horizontal/vertical shift spinbox change — emit combined (dx, dy)."""
        self.shift_changed.emit(self.shift_x_spin.value(), self.shift_y_spin.value())


    def _on_reset_shift(self):
        """Reset both shift spinboxes to 0 (each valueChanged emits shift_changed)."""
        self.shift_x_spin.setValue(0)
        self.shift_y_spin.setValue(0)


    def _on_zoom_changed(self, value: float):
        """Handle manual zoom/crop-factor spinbox change — emit signal live."""
        self.zoom_changed.emit(value)


    def _on_auto_align_clicked(self):
        """Request a one-time auto-alignment calculation."""
        self.auto_alignment_requested.emit(
            self.working_distance_spin.value(),
            self.refine_with_depth_checkbox.isChecked(),
            self.refine_from_image_checkbox.isChecked(),
        )




    def get_manual_shift(self) -> tuple:
        """Get the current (dx, dy) manual alignment shift in pixels."""
        return (self.shift_x_spin.value(), self.shift_y_spin.value())


    def set_auto_alignment_result(self, dx: int, dy: int, fov_zoom_factor: float):
        """
        Reflect a completed auto-alignment calculation: syncs the manual
        shift spinboxes and the Zoom/Crop-In spinbox to the computed
        values, so they show what's actually active and can be fine-tuned
        further with the same controls a user would use manually.
        """
        self.shift_x_spin.blockSignals(True)
        self.shift_y_spin.blockSignals(True)
        self.zoom_spin.blockSignals(True)
        self.shift_x_spin.setValue(dx)
        self.shift_y_spin.setValue(dy)
        self.zoom_spin.setValue(fov_zoom_factor)
        self.shift_x_spin.blockSignals(False)
        self.shift_y_spin.blockSignals(False)
        self.zoom_spin.blockSignals(False)

        zoom_note = (f", zoom {fov_zoom_factor:.3f}x"
                    if abs(fov_zoom_factor - 1.0) > 1e-3 else "")
        self.auto_align_result_label.setText(
            f"Applied: shift ({dx}, {dy})px{zoom_note}"
        )


    def set_auto_crop_result(self, rect: object):
        """
        Reflect a completed Auto-Crop (or Reset Crop) action.

        Args:
            rect: (top, bottom, left, right) px tuple, or None if the crop
                was reset (or Auto-Crop had nothing to crop yet).
        """
        if rect is None:
            self.auto_crop_result_label.setText("No fixed crop (recomputed live each frame)")
        else:
            top, bottom, left, right = rect
            self.auto_crop_result_label.setText(
                f"Applied: crop (top={top}, bottom={bottom}, left={left}, right={right})px"
            )



    # -------------------------------------------------------------- display

    def show_message(self, text: str, is_error: bool):
        self.message_label.setText(text or "")
        set_role(self.message_label, "error" if is_error else "ok")
        self.message_label.setVisible(bool(text))

    def set_status(self, st: dict):
        loaded, enabled = st.get("loaded"), st.get("enabled")
        blocked = self.enable_checkbox.blockSignals(True)
        self.enable_checkbox.setEnabled(bool(loaded))
        self.enable_checkbox.setChecked(bool(loaded and enabled))
        self.enable_checkbox.blockSignals(blocked)
        self.save_btn.setEnabled(bool(loaded))
        self.clear_btn.setEnabled(bool(loaded))
        self.stack_note_label.setText(
            "Fine-tune shift/zoom below stack on top of this calibration (it already contains the fixed offset and "
            "scale). Use them only for a small residual." if loaded and enabled else "")
        if not loaded:
            self.status_label.setText("Not calibrated")
            set_role(self.status_label, "error-strong")
            self.detail_label.setText("RGB is cropped to the thermal aspect ratio (no registration).")
            self.composition_label.setText("")
            self.composition_label.setVisible(False)
            self.stack_note_label.setVisible(False)
            return
        self.stack_note_label.setVisible(bool(self.stack_note_label.text()))
        self.composition_label.setVisible(True)
        self.status_label.setText("Calibrated" if enabled else "Calibrated (switched off)")
        set_role(self.status_label, "ok-strong" if enabled else "warn-strong")
        parts = []
        if st.get("method"):
            parts.append(f"{st['method']}")
        if st.get("rms_px") is not None:
            parts.append(f"RMS {st['rms_px']:.2f} px")
        if st.get("inliers") is not None:
            parts.append(f"{st['inliers']}/{st.get('points')} points")
        parts.append(f"at {st['distance_m']:g} m" if st.get("distance_m") else "distance not recorded")
        if st.get("path"):
            parts.append(os.path.basename(st["path"]))
        self.detail_label.setText(" | ".join(parts))

        if not enabled:
            self.composition_label.setText("")
        elif not st.get("parallax_on"):
            self.composition_label.setText("Parallax correction is off: alignment is exact only near the "
                                           "calibration distance.")
            set_role(self.composition_label, "hint")
        elif st.get("parallax_composed"):
            self.composition_label.setText("Parallax correction is on and composed with this calibration "
                                           "(its baseline shift is not applied twice).")
            set_role(self.composition_label, "ok")
        else:
            self.composition_label.setText("Parallax correction is on but this file records no distance, so the "
                                           "baseline shift is applied twice. Re-calibrate here to fix it.")
            set_role(self.composition_label, "error")
