"""
Camera Manager Dialog — non-blocking, live-updating camera assignment UI.

Design principles
-----------------
* Every operation that touches hardware (detect, apply, reconnect, assign)
  runs in a QThread worker so the dialog never freezes.
* A 1-second QTimer refreshes the status bar from the live CameraState so
  it always reflects hot-plug events that happened while the dialog is open.
* One "busy" state (progress bar + disabled buttons) prevents concurrent ops.
* Role changes are previewed in-dialog and only committed on Apply.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QSpinBox, QComboBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFrame,
    QProgressBar, QAbstractItemView,
)
from PyQt6.QtGui import QColor, QFont, QBrush

logger = logging.getLogger(__name__)

# ── constants ────────────────────────────────────────────────────────────────
_ROLE_LABELS = {
    "thermal":    "🌡  Thermal",
    "rgb":        "📷  RGB",
    "unassigned": "—  Unassigned",
}
_ROLE_KEYS = ["thermal", "rgb", "unassigned"]

_COL_DEVICE = 0
_COL_NAME   = 1
_COL_RES    = 2
_COL_TYPE   = 3
_COL_ROLE   = 4
_COL_ACTION = 5
_NCOLS      = 6

_ROW_TINT = {
    "thermal":    QColor(255, 120, 60, 35),
    "rgb":        QColor(60, 160, 255, 35),
    "unassigned": QColor(180, 180, 180, 18),
}

# ── background workers ───────────────────────────────────────────────────────

class _Worker(QThread):
    """Generic background task worker."""
    done    = pyqtSignal(object)   # result (any type)
    failed  = pyqtSignal(str)      # error message

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn   = fn
        self._args = args

    def run(self):
        try:
            result = self._fn(*self._args)
            self.done.emit(result)
        except Exception as exc:
            logger.error(f"Worker error: {exc}", exc_info=True)
            self.failed.emit(str(exc))


# ── dialog ───────────────────────────────────────────────────────────────────

class CameraManagerDialog(QDialog):
    """
    Camera assignment management dialog.

    All hardware operations run in background QThread workers.
    The dialog polls the live CameraState every 1 s via a QTimer so it
    always reflects changes made by the hot-plug monitor.
    """

    # Signal emitted when the dialog finishes applying new roles so
    # any parent widget can react (e.g. force a status-bar refresh).
    cameras_changed = pyqtSignal()

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self._app = app

        # Pending role overrides: device_id → role_str
        self._pending_roles: Dict[int, str] = {}

        # Last detected camera list
        self._cameras: list = []

        # Active background worker (keep strong reference to prevent GC during run)
        self._worker: Optional[_Worker] = None
        # Pool of all workers started — holds references until finished.connect fires
        self._worker_pool: list = []

        self.setWindowTitle("Camera Manager")
        self.setModal(False)           # non-modal so the live view keeps updating
        self.setMinimumSize(740, 540)
        self.resize(820, 600)

        self._build_ui()
        from thermal_inspection.gui.accessibility import apply_accessible_names, apply_tooltips
        apply_tooltips(self)
        apply_accessible_names(self)

        # Live status timer — polls CameraState every 1 s
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(1000)
        self._status_timer.timeout.connect(self._refresh_status)
        self._status_timer.start()

        # Kick off initial detection immediately (non-blocking)
        self._start_detect()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        # Header
        hdr = QLabel("Camera Manager")
        f = QFont(); f.setPointSize(14); f.setBold(True)
        hdr.setFont(f)
        root.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #334155;")
        root.addWidget(sep)

        # ── Live status cards ────────────────────────────────────────────
        status_row = QHBoxLayout()

        self._thermal_card = self._make_status_card("🌡  Thermal", "—")
        self._rgb_card      = self._make_status_card("📷  RGB",     "—")

        status_row.addWidget(self._thermal_card)
        status_row.addWidget(self._rgb_card)
        root.addLayout(status_row)

        # ── Detected cameras table ───────────────────────────────────────
        grp = QGroupBox("Detected Cameras")
        grp_layout = QVBoxLayout(grp)
        grp_layout.setContentsMargins(8, 8, 8, 8)

        self._table = QTableWidget(0, _NCOLS)
        self._table.setHorizontalHeaderLabels(
            ["Dev", "Name", "Resolution", "Detected Type", "Assign Role", "Action"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_NAME, QHeaderView.ResizeMode.Stretch
        )
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_ROLE, QHeaderView.ResizeMode.Fixed
        )
        self._table.setColumnWidth(_COL_DEVICE, 42)
        self._table.setColumnWidth(_COL_RES,    110)
        self._table.setColumnWidth(_COL_TYPE,   110)
        self._table.setColumnWidth(_COL_ROLE,   130)
        self._table.setColumnWidth(_COL_ACTION, 110)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet(
            "QTableWidget { border: 1px solid #334155; border-radius: 4px; }"
            "QTableWidget::item { padding: 4px 6px; }"
            "QHeaderView::section { background:#1e293b; color:#94a3b8; "
            "  padding:5px; border:none; font-size: 9pt; }"
        )
        grp_layout.addWidget(self._table)
        root.addWidget(grp, 1)

        # ── Progress bar (hidden when idle) ─────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { border: none; background: #1e293b; border-radius: 2px; }"
            "QProgressBar::chunk { background: #3b82f6; border-radius: 2px; }"
        )
        root.addWidget(self._progress)

        # ── Status label ─────────────────────────────────────────────────
        self._status_label = QLabel("Scanning for cameras…")
        self._status_label.setStyleSheet("color: #64748b; font-size: 9pt;")
        root.addWidget(self._status_label)

        # ── Manual ID fallback ───────────────────────────────────────────
        manual_grp = QGroupBox("Manual Override (use if camera not detected)")
        manual_layout = QHBoxLayout(manual_grp)

        manual_layout.addWidget(QLabel("Thermal device ID:"))
        self._thermal_spin = QSpinBox()
        self._thermal_spin.setRange(-1, 20)
        self._thermal_spin.setValue(-1)
        self._thermal_spin.setSpecialValueText("None")
        self._thermal_spin.setFixedWidth(70)
        manual_layout.addWidget(self._thermal_spin)

        manual_layout.addSpacing(20)
        manual_layout.addWidget(QLabel("RGB device ID:"))
        self._rgb_spin = QSpinBox()
        self._rgb_spin.setRange(-1, 20)
        self._rgb_spin.setValue(-1)
        self._rgb_spin.setSpecialValueText("None")
        self._rgb_spin.setFixedWidth(70)
        manual_layout.addWidget(self._rgb_spin)

        self._manual_apply_btn = QPushButton("Apply Manual IDs")
        self._manual_apply_btn.setFixedWidth(140)
        self._manual_apply_btn.clicked.connect(self._on_manual_apply)
        manual_layout.addWidget(self._manual_apply_btn)

        manual_layout.addStretch()
        root.addWidget(manual_grp)

        # ── Bottom button bar ────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._detect_btn = QPushButton("🔍  Re-Detect")
        self._detect_btn.setFixedHeight(34)
        self._detect_btn.clicked.connect(self._start_detect)

        self._apply_btn = QPushButton("✅  Apply Roles")
        self._apply_btn.setFixedHeight(34)
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._on_apply)
        self._apply_btn.setStyleSheet(
            "QPushButton { background: #1d4ed8; color: white; "
            "  border-radius: 5px; font-weight: 600; }"
            "QPushButton:hover { background: #2563eb; }"
            "QPushButton:disabled { background: #334155; color: #64748b; }"
        )

        self._swap_btn = QPushButton("🔄  Swap T ↔ RGB")
        self._swap_btn.setFixedHeight(34)
        self._swap_btn.clicked.connect(self._on_swap)

        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(self._detect_btn)
        btn_row.addWidget(self._swap_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── status card helper ───────────────────────────────────────────────────

    def _make_status_card(self, title: str, value: str) -> QGroupBox:
        card = QGroupBox(title)
        card.setStyleSheet(
            "QGroupBox { border: 1px solid #334155; border-radius: 6px; "
            "  margin-top: 8px; font-weight: 600; }"
            "QGroupBox::title { color: #94a3b8; padding: 0 4px; }"
        )
        layout = QVBoxLayout(card)
        lbl = QLabel(value)
        lbl.setStyleSheet("font-size: 9.75pt; color: #e2e8f0;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setObjectName("value_label")
        layout.addWidget(lbl)
        return card

    def _set_card(self, card: QGroupBox, text: str, ok: bool):
        lbl = card.findChild(QLabel, "value_label")
        if lbl:
            lbl.setText(text)
            color = "#4ade80" if ok else "#94a3b8"
            lbl.setStyleSheet(f"font-size: 9.75pt; color: {color};")

    # ── status refresh (called by 1 s timer) ─────────────────────────────────

    def _refresh_status(self):
        """Pull live CameraState and update the status cards."""
        try:
            state = getattr(self._app, 'camera_state', None)

            if state.thermal_connected:
                dev  = state.thermal_device_id
                kind = "FLIR Boson" if getattr(state, "is_flir_boson", False) else "Thermal"
                self._set_card(self._thermal_card, f"{kind}  [dev {dev}]  ✓ live", True)
            else:
                self._set_card(self._thermal_card, "Not connected", False)

            if state.rgb_available:
                dev = state.rgb_device_id
                self._set_card(self._rgb_card, f"RGB camera  [dev {dev}]  ✓ live", True)
            else:
                self._set_card(self._rgb_card, "Not connected", False)

            # Sync manual spin boxes with current state if not already set
            if self._thermal_spin.value() == -1 and state.thermal_device_id is not None:
                self._thermal_spin.setValue(state.thermal_device_id)
            if self._rgb_spin.value() == -1 and state.rgb_device_id is not None:
                self._rgb_spin.setValue(state.rgb_device_id)

        except Exception:
            pass

    # ── table population ─────────────────────────────────────────────────────

    def _populate_table(self, cameras: list):
        """Fill the table with detected CameraInfo objects."""
        self._cameras = cameras
        self._pending_roles.clear()

        table = self._table
        table.setRowCount(0)

        state = getattr(self._app, 'camera_state', None)

        for cam in cameras:
            row = table.rowCount()
            table.insertRow(row)

            # Determine current role
            if cam.device_id == state.thermal_device_id and state.thermal_connected:
                current_role = "thermal"
            elif cam.device_id == state.rgb_device_id and state.rgb_available:
                current_role = "rgb"
            else:
                # Use detector's classification as starting guess
                type_str = getattr(cam, "camera_type", None)
                if type_str is not None:
                    name = type_str.value.lower() if hasattr(type_str, "value") else str(type_str).lower()
                    current_role = "thermal" if name == "thermal" else "rgb"
                else:
                    current_role = "unassigned"

            self._pending_roles[cam.device_id] = current_role

            # Col 0: device ID
            item_dev = QTableWidgetItem(str(cam.device_id))
            item_dev.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, _COL_DEVICE, item_dev)

            # Col 1: name
            table.setItem(row, _COL_NAME, QTableWidgetItem(cam.name))

            # Col 2: resolution
            res_str = f"{cam.resolution[0]}×{cam.resolution[1]}" if cam.resolution else "?"
            item_res = QTableWidgetItem(res_str)
            item_res.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, _COL_RES, item_res)

            # Col 3: detected type (read-only)
            type_label = getattr(cam.camera_type, "value", "RGB") if hasattr(cam, "camera_type") else "RGB"
            item_type = QTableWidgetItem(type_label)
            item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row, _COL_TYPE, item_type)

            # Col 4: role combo
            combo = QComboBox()
            for key in _ROLE_KEYS:
                combo.addItem(_ROLE_LABELS[key], key)
            idx = _ROLE_KEYS.index(current_role) if current_role in _ROLE_KEYS else 2
            combo.setCurrentIndex(idx)
            dev_id = cam.device_id
            combo.currentIndexChanged.connect(
                lambda _, d=dev_id, c=combo: self._on_role_changed(d, c)
            )
            table.setCellWidget(row, _COL_ROLE, combo)

            # Col 5: action button (reconnect / assign now)
            is_active = (
                (cam.device_id == state.thermal_device_id and state.thermal_connected) or
                (cam.device_id == state.rgb_device_id     and state.rgb_available)
            )
            if is_active:
                action_lbl = QLabel("● Live")
                action_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                action_lbl.setStyleSheet("color: #4ade80; font-weight: 600;")
                table.setCellWidget(row, _COL_ACTION, action_lbl)
            else:
                btn = QPushButton("Connect Now")
                btn.setStyleSheet(
                    "QPushButton { background: #0f4c81; color: #e2e8f0; "
                    "  border-radius: 4px; padding: 3px 8px; }"
                    "QPushButton:hover { background: #1d6fba; }"
                )
                btn.clicked.connect(
                    lambda _, d=dev_id: self._on_connect_now(d)
                )
                table.setCellWidget(row, _COL_ACTION, btn)

            # Row tint
            tint = _ROW_TINT.get(current_role, _ROW_TINT["unassigned"])
            for c in range(_NCOLS):
                item = table.item(row, c)
                if item:
                    item.setBackground(QBrush(tint))

        if not cameras:
            self._status_label.setText("No cameras detected. Connect a camera and click Re-Detect.")
        else:
            self._status_label.setText(
                f"{len(cameras)} camera(s) detected.  "
                "Set each camera's role, then click Apply Roles."
            )

    # ── event handlers ───────────────────────────────────────────────────────

    def _on_role_changed(self, device_id: int, combo: QComboBox):
        """Update pending role and re-tint the row."""
        role = combo.currentData()
        self._pending_roles[device_id] = role
        # Re-tint — find the row
        for row in range(self._table.rowCount()):
            item = self._table.item(row, _COL_DEVICE)
            if item and int(item.text()) == device_id:
                tint = _ROW_TINT.get(role, _ROW_TINT["unassigned"])
                for c in range(_NCOLS):
                    it = self._table.item(row, c)
                    if it:
                        it.setBackground(QBrush(tint))
                break

    def _on_connect_now(self, device_id: int):
        """Immediately connect a detected device using its currently selected role."""
        role = self._pending_roles.get(device_id, "rgb")
        if role == "unassigned":
            QMessageBox.information(
                self, "Select Role",
                "Please set the camera role to Thermal or RGB first."
            )
            return
        self._set_busy(True, f"Connecting device {device_id} as {role}…")
        self._run_worker(
            self._app.assign_camera_to_slot,
            device_id, role,
            on_done=lambda ok: self._on_assign_done(device_id, role, ok),
        )

    def _on_assign_done(self, device_id: int, role: str, ok):
        self._set_busy(False)
        if ok:
            self._status_label.setText(
                f"✅  Device {device_id} connected as {role}."
            )
            self.cameras_changed.emit()
            self._start_detect()   # refresh table
        else:
            QMessageBox.warning(
                self, "Connection Failed",
                f"Could not open device {device_id} as {role}.\n\n"
                "Try a different device ID or role."
            )

    def _on_apply(self):
        """Apply all pending role changes — runs in background thread."""
        thermal_id = None
        rgb_id     = None

        for dev_id, role in self._pending_roles.items():
            if role == "thermal":
                thermal_id = dev_id
            elif role == "rgb":
                rgb_id = dev_id

        # If no table rows, fall back to manual spin boxes
        if not self._cameras:
            t_val = self._thermal_spin.value()
            r_val = self._rgb_spin.value()
            thermal_id = t_val if t_val >= 0 else None
            rgb_id     = r_val if r_val >= 0 else None

        if thermal_id is None and rgb_id is None:
            QMessageBox.warning(
                self, "No Cameras Assigned",
                "Assign at least one camera as Thermal or RGB before applying."
            )
            return

        self._set_busy(True, "Reinitialising cameras…")
        self._run_worker(
            self._app.apply_camera_roles,
            thermal_id, rgb_id,
            on_done=lambda _: self._on_apply_done(),
        )

    def _on_apply_done(self):
        self._set_busy(False)
        self._status_label.setText("✅  Camera roles applied successfully.")
        self.cameras_changed.emit()
        self._refresh_status()
        self._start_detect()   # refresh table after reinit

    def _on_swap(self):
        """Swap thermal and RGB assignments — runs in background thread."""
        self._set_busy(True, "Swapping cameras…")
        self._run_worker(
            self._app.swap_cameras,
            on_done=lambda _: self._on_swap_done(),
        )

    def _on_swap_done(self):
        self._set_busy(False)
        self._refresh_status()
        self._start_detect()

    def _on_manual_apply(self):
        """Apply the manual device-ID spin box values."""
        t_val = self._thermal_spin.value()
        r_val = self._rgb_spin.value()
        thermal_id = t_val if t_val >= 0 else None
        rgb_id     = r_val if r_val >= 0 else None
        if thermal_id is None and rgb_id is None:
            QMessageBox.warning(self, "No IDs Set",
                                "Set at least one device ID (not –1) first.")
            return
        self._set_busy(True, "Reinitialising cameras with manual IDs…")
        self._run_worker(
            self._app.apply_camera_roles,
            thermal_id, rgb_id,
            on_done=lambda _: self._on_apply_done(),
        )

    # ── background worker helpers ────────────────────────────────────────────

    def _start_detect(self):
        """Run camera detection in a background QThread."""
        # If a worker is running and it's the detect task, skip (don't queue duplicates)
        if self._worker and self._worker.isRunning():
            logger.debug("Detection already in progress — skipping duplicate request")
            return
        self._set_busy(True, "Scanning for cameras…")
        self._run_worker(
            self._app.detect_cameras,
            on_done=self._on_detect_done,
            on_fail=self._on_detect_failed,
        )

    def _on_detect_done(self, cameras: list):
        self._set_busy(False)
        self._populate_table(cameras)

    def _on_detect_failed(self, msg: str):
        self._set_busy(False)
        self._status_label.setText(f"⚠  Detection error: {msg}")

    def _run_worker(self, fn, *args, on_done=None, on_fail=None):
        """Launch a _Worker QThread for fn(*args). Only one at a time."""
        w = _Worker(fn, *args, parent=self)
        if on_done:
            # Wrap callbacks to guard against dialog being closed/deleted
            def _safe_done(result, _cb=on_done):
                # closeEvent's wait(3000) can time out while _fn is still
                # running a slow hardware call (run() is a blocking call with
                # no event loop, so quit() can't interrupt it). If the dialog
                # was closed and its C++ object already deleted by the time
                # this fires, isVisible() itself raises RuntimeError.
                try:
                    if self.isVisible() or not self.isHidden():
                        _cb(result)
                except RuntimeError:
                    logger.debug("Worker finished after dialog was closed/deleted — ignoring result")
                except Exception as exc:
                    logger.error(f"Worker done callback error: {exc}", exc_info=True)
            w.done.connect(_safe_done)
        if on_fail:
            def _safe_fail(msg, _cb=on_fail):
                try:
                    _cb(msg)
                except Exception:
                    pass
            w.failed.connect(_safe_fail)
        else:
            def _safe_default_fail(msg):
                try:
                    self._set_busy(False)
                    self._status_label.setText(f"⚠  Error: {msg}")
                except Exception:
                    pass
            w.failed.connect(_safe_default_fail)

        def _on_finished():
            try:
                self._worker = None
                if w in self._worker_pool:
                    self._worker_pool.remove(w)
            except Exception:
                pass
        w.finished.connect(_on_finished)

        self._worker = w
        self._worker_pool.append(w)   # hold strong reference until done
        w.start()

    # ── busy state ───────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool, message: str = ""):
        self._progress.setVisible(busy)
        self._detect_btn.setEnabled(not busy)
        self._apply_btn.setEnabled(not busy)
        self._swap_btn.setEnabled(not busy)
        self._manual_apply_btn.setEnabled(not busy)
        if message:
            self._status_label.setText(message)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._status_timer.stop()
        # Cancel running worker gracefully
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        # Clean up pool
        for w in list(self._worker_pool):
            if w.isRunning():
                w.quit()
                w.wait(1000)
        self._worker_pool.clear()
        super().closeEvent(event)
