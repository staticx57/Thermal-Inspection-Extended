"""
ROI Manager panel: a live table of every ROI's temperatures (average / min / max / peak-hold), trend, area and alert
state, with the management actions (rename, lock, show/hide, duplicate, delete, per-ROI palette, threshold alerts), a
history graph, ROI-vs-ROI comparison, ROI-set save/load and CSV/JSON export.

All numbers come from processing.roi_tracking.ROITracker (pure Python, unit-aware); this widget only displays them and
emits signals - the main window applies the actions to the ROIController.
"""
import logging
from dataclasses import asdict
from types import SimpleNamespace
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QMenu, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QApplication,
)

from thermal_inspection.gui.widgets.palette_combo import PaletteComboBox
from thermal_inspection.processing.roi_tracking import METRIC_LABELS, ROIAlert, ROITracker, export_rows

logger = logging.getLogger(__name__)

COLUMNS = ["Name", "Avg", "Min", "Max", "Peak", "Trend", "Area", "Alert"]
COL_NAME, COL_AVG, COL_MIN, COL_MAX, COL_PEAK, COL_TREND, COL_AREA, COL_ALERT = range(len(COLUMNS))
TREND_GLYPH = {"rising": ("▲", "#e07030"), "falling": ("▼", "#4a90d9"), "stable": ("–", "#888888")}
ALERT_TINT = QColor(255, 90, 90, 70)
# manual ROIs all share one default colour, which would make their graph curves indistinguishable: colour by position
GRAPH_COLORS = [(255, 170, 0), (0, 200, 255), (120, 255, 120), (255, 90, 200), (200, 160, 255), (255, 255, 90),
                (90, 160, 255), (255, 120, 90)]


def format_reading(value: Optional[float], unit: str) -> str:
    """'42.5 °F' (an estimate - the 8-bit AGC estimator - gets a '~' prefix). '-' when unknown."""
    if value is None:
        return "-"
    est = "(est)" in (unit or "")
    clean = (unit or "").replace("(est)", "").strip()
    return f"{'~' if est else ''}{value:.1f} {clean}".rstrip()


def format_delta_reading(value: float, unit: str) -> str:
    clean = (unit or "").replace("(est)", "").strip()
    return f"{value:+.1f} {clean}".rstrip()


class ROIAlertDialog(QDialog):
    """Set, change or remove a threshold alert on one or more ROIs."""

    def __init__(self, current: Optional[ROIAlert], unit: str = "°C", parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROI Alert")
        self.remove_requested = False
        form = QFormLayout()
        self.metric = QComboBox()
        for key, label in METRIC_LABELS.items():
            self.metric.addItem(label, key)
        self.kind = QComboBox()
        self.kind.addItem("rises above", "above")
        self.kind.addItem("falls below", "below")
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(-1000.0, 100000.0)
        self.threshold.setDecimals(1)
        self.threshold.setSuffix(f" {unit.replace('(est)', '').strip()}")
        self.sound = QCheckBox("Beep when it triggers")
        self.enabled = QCheckBox("Alert enabled")
        self.enabled.setChecked(True)
        self.sound.setChecked(True)
        form.addRow("Alert when the", self.metric)
        form.addRow("", self.kind)
        form.addRow("Threshold", self.threshold)
        form.addRow("", self.sound)
        form.addRow("", self.enabled)
        self._unit = unit
        if current is not None:
            self.metric.setCurrentIndex(max(0, self.metric.findData(current.metric)))
            self.kind.setCurrentIndex(max(0, self.kind.findData(current.type)))
            self.threshold.setValue(current.threshold)
            self.sound.setChecked(current.sound_enabled)
            self.enabled.setChecked(current.enabled)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        remove = QPushButton("Remove alert")
        remove.setEnabled(current is not None)
        remove.clicked.connect(self._on_remove)
        row = QHBoxLayout()
        row.addWidget(remove)
        row.addStretch(1)
        row.addWidget(buttons)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(row)

    def _on_remove(self):
        self.remove_requested = True
        self.accept()

    def result_alert(self) -> Optional[ROIAlert]:
        if self.remove_requested:
            return None
        return ROIAlert(threshold=self.threshold.value(), metric=self.metric.currentData(),
                        type=self.kind.currentData(), unit=self._unit, enabled=self.enabled.isChecked(),
                        sound_enabled=self.sound.isChecked())


class ROITemperaturePanel(QWidget):
    """ROI Manager: live per-ROI temperature table plus management, alerts, history and export."""

    # kept signals
    export_data_requested = pyqtSignal()
    clear_history_requested = pyqtSignal(str)       # roi_id, or "all"
    roi_selected = pyqtSignal(str)
    roi_deleted = pyqtSignal(str)
    roi_palette_changed = pyqtSignal(str, str)
    # new
    roi_renamed = pyqtSignal(str, str)              # roi_id, new label
    roi_lock_changed = pyqtSignal(str, bool)
    roi_visibility_changed = pyqtSignal(str, bool)
    roi_duplicate_requested = pyqtSignal(str)
    roi_alert_triggered = pyqtSignal(str, str)      # roi_id, human text
    save_set_requested = pyqtSignal()
    load_set_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.roi_data: Dict[str, dict] = {}
        self.current_rois: List = []
        self.selected_roi_index = -1
        self.tracker = ROITracker()
        self._signature = None
        self._graph = None
        self._init_ui()

    # ------------------------------------------------------------------ UI

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("📐 ROI Manager")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        self.stats_label = QLabel("No ROI data available")      # one-line summary
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        # --- table
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)      # themes don't style the alternate colour: it came out white in dark
        self.table.setMinimumHeight(190)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c in (COL_AVG, COL_MIN, COL_MAX, COL_PEAK, COL_TREND, COL_AREA, COL_ALERT):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self._on_rename())
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

        # --- actions
        actions = QGroupBox("Selected ROIs")
        act_lay = QVBoxLayout(actions)
        # three buttons per row: themes give every button a uniform minimum width, so four would overflow the 630 px tab
        row1, row2, row3 = QHBoxLayout(), QHBoxLayout(), QHBoxLayout()
        self.rename_btn = QPushButton("Rename")
        self.lock_btn = QPushButton("Lock")
        self.visible_btn = QPushButton("Hide")
        self.duplicate_btn = QPushButton("Duplicate")
        self.alert_btn = QPushButton("Alert…")
        self.roi_delete_btn = QPushButton("🗑 Delete")
        self.roi_delete_all_btn = QPushButton("🗑 Delete All")
        self.rename_btn.clicked.connect(self._on_rename)
        self.lock_btn.clicked.connect(self._on_toggle_lock)
        self.visible_btn.clicked.connect(self._on_toggle_visible)
        self.duplicate_btn.clicked.connect(self._on_duplicate)
        self.alert_btn.clicked.connect(self._on_set_alert)
        self.roi_delete_btn.clicked.connect(self._on_delete_rois_clicked)
        self.roi_delete_all_btn.clicked.connect(self._on_delete_all_rois_clicked)
        for b in (self.rename_btn, self.lock_btn, self.visible_btn):
            row1.addWidget(b)
        for b in (self.duplicate_btn, self.alert_btn, self.roi_delete_btn):
            row2.addWidget(b)
        row3.addWidget(self.roi_delete_all_btn)
        row3.addStretch(1)
        act_lay.addLayout(row1)
        act_lay.addLayout(row2)
        act_lay.addLayout(row3)

        pal_row = QHBoxLayout()
        pal_row.addWidget(QLabel("Palette:"))
        self.roi_palette_combo = PaletteComboBox()
        self.roi_palette_combo.setMinimumHeight(32)
        self.roi_palette_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.roi_palette_combo.paletteValueChanged.connect(self._on_roi_palette_combo_changed)
        pal_row.addWidget(self.roi_palette_combo, 1)
        act_lay.addLayout(pal_row)
        layout.addWidget(actions)

        self.compare_label = QLabel("")
        self.compare_label.setWordWrap(True)
        layout.addWidget(self.compare_label)

        # --- history graph
        graph_row = QHBoxLayout()
        self.graph_check = QCheckBox("History graph")
        self.graph_check.toggled.connect(self._on_graph_toggled)
        self.graph_metric = QComboBox()
        for key, label in (("avg", "Average"), ("max", "Hottest pixel"), ("min", "Coldest pixel")):
            self.graph_metric.addItem(label, key)
        self.graph_metric.currentIndexChanged.connect(lambda *_: self._update_graph())
        graph_row.addWidget(self.graph_check)
        graph_row.addWidget(self.graph_metric)
        graph_row.addStretch(1)
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.setToolTip("Forget the recorded history and peak-hold values (alerts keep their settings)")
        self.clear_btn.clicked.connect(lambda: self.clear_history_requested.emit("all"))
        self.clear_btn.setEnabled(False)
        graph_row.addWidget(self.clear_btn)
        layout.addLayout(graph_row)
        self.graph_host = QVBoxLayout()
        layout.addLayout(self.graph_host)

        # --- footer
        footer = QHBoxLayout()
        self.save_set_btn = QPushButton("Save ROI Set…")
        self.load_set_btn = QPushButton("Load ROI Set…")
        self.export_btn = QPushButton("Export…")
        self.save_set_btn.clicked.connect(self.save_set_requested.emit)
        self.load_set_btn.clicked.connect(self.load_set_requested.emit)
        self.export_btn.clicked.connect(self.export_data_requested.emit)
        self.export_btn.setEnabled(False)
        for b in (self.save_set_btn, self.load_set_btn, self.export_btn):
            footer.addWidget(b)
        layout.addLayout(footer)
        layout.addStretch(1)
        self._update_buttons()

    # ------------------------------------------------------------------ ROI list

    @staticmethod
    def _roi_signature(rois):
        return [(r.roi_id, r.label, bool(r.locked), bool(r.active), r.custom_palette) for r in rois]

    def update_rois(self, rois):
        """Every ROI including hidden ones (the manager lists them so they can be shown again)."""
        self.current_rois = list(rois)
        for roi in self.current_rois:                               # alerts saved with an ROI set come back
            if self.tracker.alert(roi.roi_id) is None:
                saved = (roi.metadata or {}).get("alert")
                if saved:
                    try:
                        self.tracker.set_alert(roi.roi_id, ROIAlert(**saved))
                    except TypeError:
                        logger.debug(f"Ignoring unreadable saved alert on {roi.roi_id}")
        self.tracker.prune(r.roi_id for r in self.current_rois)
        sig = self._roi_signature(self.current_rois)
        if sig != self._signature:                  # called every frame: only redraw when the list really changed
            self._signature = sig
            self._rebuild_table()
            self._refresh_values()

    def selected_ids(self) -> List[str]:
        rows = sorted({i.row() for i in self.table.selectedItems()})
        out = []
        for r in rows:
            item = self.table.item(r, COL_NAME)
            if item is not None:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return out

    def _roi(self, roi_id):
        return next((r for r in self.current_rois if r.roi_id == roi_id), None)

    def _rebuild_table(self):
        keep = set(self.selected_ids())
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.current_rois))
        for row, roi in enumerate(self.current_rois):
            name = QTableWidgetItem()
            name.setData(Qt.ItemDataRole.UserRole, roi.roi_id)
            self.table.setItem(row, COL_NAME, name)
            for c in range(1, len(COLUMNS)):
                self.table.setItem(row, c, QTableWidgetItem(""))
            if roi.roi_id in keep:
                self.table.selectRow(row)
        self.table.blockSignals(False)
        self._update_buttons()

    def _refresh_values(self):
        hottest = self.tracker.hottest(among=[i for i in self.roi_data if (self._roi(i) is not None and self._roi(i).active)])
        for row, roi in enumerate(self.current_rois):
            if row >= self.table.rowCount():
                break
            rec = self.tracker.records.get(roi.roi_id)
            unit = rec.unit if rec else ""
            last = rec.history[-1] if rec and rec.history else None
            alert = rec.alert if rec else None
            hidden = not roi.active
            fresh = roi.roi_id in self.roi_data and not hidden     # measured in the latest stats push
            name = ("🔒 " if roi.locked else "") + (roi.label or roi.roi_id) + (" 🎨" if roi.custom_palette else "")
            if hidden:
                name += "  (hidden)"
            cells = {
                COL_NAME: name,
                COL_AVG: format_reading(last[1], unit) if last and fresh else "-",
                COL_MIN: format_reading(last[2], unit) if last and fresh else "-",
                COL_MAX: format_reading(last[3], unit) if last and fresh else "-",
                COL_PEAK: format_reading(rec.peak_max, unit) if rec and rec.peak_max is not None else "-",
                COL_AREA: self._area_text(rec),
                COL_ALERT: ("⚠ " if alert and alert.triggered else ("● " if alert else "")) + (alert.describe() if alert else ""),
            }
            trend = self.tracker.trend(roi.roi_id) if rec else "stable"
            glyph, colour = TREND_GLYPH[trend]
            cells[COL_TREND] = glyph if last and fresh else ""
            for col, text in cells.items():
                item = self.table.item(row, col)
                if item is None:
                    continue
                if item.text() != text:
                    item.setText(text)
                item.setForeground(QBrush(QColor(colour) if col == COL_TREND else
                                          (QColor("#888888") if hidden else QColor())))
                f = item.font()
                f.setItalic(hidden)
                f.setBold(col == COL_MAX and roi.roi_id == hottest and fresh)
                item.setFont(f)
                item.setBackground(QBrush(ALERT_TINT) if (alert and alert.triggered) else QBrush())
        self._update_summary(hottest)
        has_data = bool(self.tracker.records and any(r.history for r in self.tracker.records.values()))
        self.export_btn.setEnabled(bool(self.current_rois))
        self.clear_btn.setEnabled(has_data)
        self._update_compare()
        self._update_graph()

    @staticmethod
    def _area_text(rec) -> str:
        if not rec:
            return ""
        px, frame = rec.latest.get("pixel_count"), rec.latest.get("frame_pixels")
        if not px:
            return ""
        return f"{px:,} px" + (f" ({100.0 * px / frame:.1f}%)" if frame else "")

    def _update_summary(self, hottest):
        if not self.roi_data:
            self.stats_label.setText("No ROI data available")
            return
        n = sum(1 for r in self.current_rois if r.roi_id in self.roi_data)
        text = f"{n} ROI{'s' if n != 1 else ''} measured"
        if hottest:
            roi, rec = self._roi(hottest), self.tracker.records[hottest]
            text += f" - hottest: {(roi.label or roi.roi_id) if roi else hottest} at {format_reading(rec.history[-1][3], rec.unit)}"
        alerts = sum(1 for r in self.tracker.records.values() if r.alert and r.alert.triggered)
        if alerts:
            text += f" - ⚠ {alerts} alert{'s' if alerts != 1 else ''} firing"
        self.stats_label.setText(text)

    # ------------------------------------------------------------------ data in

    def update_roi_data(self, roi_data: dict):
        """Per-ROI statistics push ({roi_id: {'temp_avg', 'temp_min', 'temp_max', 'unit', 'pixel_count', ...}})."""
        if roi_data is None:
            return
        self.roi_data = roi_data
        newly = self.tracker.update(roi_data)
        for roi_id in newly:
            alert = self.tracker.alert(roi_id)
            roi = self._roi(roi_id)
            self.roi_alert_triggered.emit(roi_id, f"ROI alert: {(roi.label if roi else roi_id) or roi_id} - {alert.describe()}")
            if alert.sound_enabled:
                QApplication.beep()
        self._refresh_values()

    def clear_roi_history(self, roi_id: Optional[str] = None):
        """Clear history/peaks for one ROI (None or 'all' = every ROI)."""
        self.tracker.clear_history(None if roi_id in (None, "all") else roi_id)
        self._refresh_values()

    def export_data(self, filepath: str):
        """Write every ROI's current readings, peaks, area and alert state to CSV or JSON (by extension)."""
        export_rows(filepath, self.tracker.rows(self.current_rois))

    # ------------------------------------------------------------------ selection / buttons

    def _on_selection_changed(self):
        ids = self.selected_ids()
        self.selected_roi_index = self.table.currentRow()
        if len(ids) == 1:
            self.roi_selected.emit(ids[0])
            roi = self._roi(ids[0])
            if roi and roi.custom_palette:
                idx = self.roi_palette_combo.findValue(roi.custom_palette)
                if idx >= 0:
                    self.roi_palette_combo.blockSignals(True)
                    self.roi_palette_combo.setCurrentIndex(idx)
                    self.roi_palette_combo.blockSignals(False)
        self._update_buttons()
        self._update_compare()
        self._update_graph()

    def _update_buttons(self):
        ids = self.selected_ids()
        rois = [r for r in (self._roi(i) for i in ids) if r]
        some = bool(rois)
        self.rename_btn.setEnabled(len(rois) == 1)
        self.duplicate_btn.setEnabled(some)
        self.alert_btn.setEnabled(some)
        self.roi_delete_btn.setEnabled(some)
        self.lock_btn.setEnabled(some)
        self.visible_btn.setEnabled(some)
        self.lock_btn.setText("Unlock" if some and all(r.locked for r in rois) else "Lock")
        self.visible_btn.setText("Show" if some and all(not r.active for r in rois) else "Hide")
        self.roi_delete_all_btn.setEnabled(bool(self.current_rois))

    def _update_compare(self):
        ids = self.selected_ids()
        if len(ids) != 2:
            self.compare_label.setText("")
            return
        diff = self.tracker.compare(ids[0], ids[1])
        a, b = self._roi(ids[0]), self._roi(ids[1])
        if diff is None or not a or not b:
            self.compare_label.setText("")
            return
        u = diff["unit"]
        self.compare_label.setText(
            f"{b.label or b.roi_id} − {a.label or a.roi_id}:  avg {format_delta_reading(diff['avg'], u)}   "
            f"max {format_delta_reading(diff['max'], u)}   min {format_delta_reading(diff['min'], u)}")

    # ------------------------------------------------------------------ actions

    def _on_rename(self):
        ids = self.selected_ids()
        if len(ids) != 1:
            return
        roi = self._roi(ids[0])
        if roi is None:
            return
        if roi.locked:
            QMessageBox.information(self, "Rename ROI", "This ROI is locked. Unlock it to rename it.")
            return
        text, ok = QInputDialog.getText(self, "Rename ROI", "Name:", text=roi.label or roi.roi_id)
        if ok and text.strip():
            self.roi_renamed.emit(roi.roi_id, text.strip())

    def _on_toggle_lock(self):
        rois = [r for r in (self._roi(i) for i in self.selected_ids()) if r]
        lock = not all(r.locked for r in rois)
        for r in rois:
            self.roi_lock_changed.emit(r.roi_id, lock)

    def _on_toggle_visible(self):
        rois = [r for r in (self._roi(i) for i in self.selected_ids()) if r]
        show = all(not r.active for r in rois)
        for r in rois:
            self.roi_visibility_changed.emit(r.roi_id, show)

    def _on_duplicate(self):
        for roi_id in self.selected_ids():
            self.roi_duplicate_requested.emit(roi_id)

    def _alert_unit(self, roi_ids) -> str:
        for i in roi_ids:
            rec = self.tracker.records.get(i)
            if rec and rec.unit:
                return rec.unit
        return "°C"

    def _on_set_alert(self):
        ids = self.selected_ids()
        if not ids:
            return
        unit = self._alert_unit(ids)
        dlg = ROIAlertDialog(self.tracker.alert(ids[0]) if len(ids) == 1 else None, unit, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self.apply_alert(ids, dlg.result_alert())

    def apply_alert(self, roi_ids, alert: Optional[ROIAlert]):
        """Set (or, with None, remove) the same alert on several ROIs; stored on the ROI so it survives a saved set."""
        for roi_id in roi_ids:
            copy = None if alert is None else ROIAlert(**{k: v for k, v in asdict(alert).items()
                                                          if k not in ("triggered", "trigger_count", "last_trigger_time")})
            self.tracker.set_alert(roi_id, copy)
            roi = self._roi(roi_id)
            if roi is not None:
                meta = dict(roi.metadata or {})
                if copy is None:
                    meta.pop("alert", None)
                else:
                    meta["alert"] = {k: v for k, v in asdict(copy).items()
                                     if k not in ("triggered", "trigger_count", "last_trigger_time")}
                roi.metadata = meta
        self._refresh_values()

    def _confirm_delete(self, rois, title: str) -> bool:
        locked = [r for r in rois if r.locked]
        deletable = [r for r in rois if not r.locked]
        if not deletable:
            QMessageBox.information(self, title, "All of these ROIs are locked. Unlock them to delete them.")
            return False
        note = f"\n\n{len(locked)} locked ROI(s) will be kept." if locked else ""
        return QMessageBox.question(
            self, title, f"Delete {len(deletable)} ROI(s)?{note}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def _on_delete_rois_clicked(self):
        rois = [r for r in (self._roi(i) for i in self.selected_ids()) if r]
        if rois and self._confirm_delete(rois, "Delete ROIs"):
            for r in rois:
                if not r.locked:
                    self.roi_deleted.emit(r.roi_id)

    def _on_delete_all_rois_clicked(self):
        if self.current_rois and self._confirm_delete(list(self.current_rois), "Delete All ROIs"):
            for r in list(self.current_rois):
                if not r.locked:
                    self.roi_deleted.emit(r.roi_id)

    def _on_roi_palette_combo_changed(self, palette_name: str):
        clean = palette_name.strip().lstrip("─ ")
        if clean and not clean.startswith("───"):
            for roi_id in self.selected_ids():
                self.roi_palette_changed.emit(roi_id, clean)

    def _show_context_menu(self, pos):
        if not self.selected_ids():
            return
        menu = QMenu(self)
        for text, fn, enabled in (
            ("Rename…", self._on_rename, self.rename_btn.isEnabled()),
            (self.lock_btn.text(), self._on_toggle_lock, True),
            (self.visible_btn.text(), self._on_toggle_visible, True),
            ("Duplicate", self._on_duplicate, True),
            ("Set alert…", self._on_set_alert, True),
            ("Delete", self._on_delete_rois_clicked, True),
        ):
            act = menu.addAction(text)
            act.setEnabled(enabled)
            act.triggered.connect(fn)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    # ------------------------------------------------------------------ history graph

    def _on_graph_toggled(self, on: bool):
        if on and self._graph is None:
            from thermal_inspection.gui.panels.spot_meter_panel import TemperatureHistoryGraph
            self._graph = TemperatureHistoryGraph()
            self._graph.setMinimumHeight(190)
            self.graph_host.addWidget(self._graph)
        if self._graph is not None:
            self._graph.setVisible(on)
        self._update_graph()

    def _update_graph(self):
        if self._graph is None or not self.graph_check.isChecked():
            return
        metric = self.graph_metric.currentData()
        ids = self.selected_ids() or [r.roi_id for r in self.current_rois if r.roi_id in self.tracker.records][:4]
        shown = []
        for roi_id in ids:
            roi, rec = self._roi(roi_id), self.tracker.records.get(roi_id)
            series = self.tracker.series(roi_id, metric)
            if not roi or not rec or not series:
                continue
            shown.append(SimpleNamespace(id=roi_id, label=roi.label or roi_id, unit=rec.unit,
                                         history=series, color=GRAPH_COLORS[len(shown) % len(GRAPH_COLORS)]))
        self._graph.update_data(shown)
