"""
Thermal Analysis Panel for temperature statistics, hot/cold spots, and trends.
"""

import logging
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QListWidget, QListWidgetItem,
    QScrollArea, QTabWidget, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPalette

from thermal_inspection.processing.palette_manager import PaletteType
from thermal_inspection.gui.widgets.palette_combo import PaletteComboBox
from thermal_inspection.gui.widgets.paged_tabwidget import PagedTabWidget
from thermal_inspection.processing.roi_manager import ROI
from thermal_inspection.processing.thermal_analyzer import (
    ThermalStatistics, HotSpot, ColdSpot, ThermalAnomaly, TemperatureTrend, ANOMALY_TYPE_LABELS
)
from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPanel
from thermal_inspection.gui.panels.grid_overlay_panel import GridOverlayPanel

logger = logging.getLogger(__name__)


class ThermalAnalysisPanel(QWidget):
    """
    Right sidebar panel for thermal analysis display.
    Shows temperature statistics, hot/cold spots, trends, and anomalies.
    """

    # Signals
    baseline_toggled = pyqtSignal(bool)
    palette_changed = pyqtSignal(str)  # Emits palette name
    overlay_info_toggled = pyqtSignal(bool)
    show_hot_spots_toggled = pyqtSignal(bool)
    show_cold_spots_toggled = pyqtSignal(bool)
    show_anomalies_toggled = pyqtSignal(bool)

    # Spot Meter Signals
    spot_meter_toggled = pyqtSignal(bool)
    clear_spots_clicked = pyqtSignal()
    spot_preset_requested = pyqtSignal(str)  # Emits preset name (e.g., "Grid 3x3")

    def __init__(self, parent=None):
        super().__init__(parent)
        # Removed fixed width - use parent tab width dynamically
        self.current_rois = []  # Store ROI list
        self.selected_roi_index = -1  # Track selected ROI

        # Main layout with tabs
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget
        self.analysis_tabs = PagedTabWidget()
        main_layout.addWidget(self.analysis_tabs)

        # Helper function to create section headers
        def create_section_header(text):
            header = QLabel(text)
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            header.setFont(font)
            return header

        # Helper function to create separators
        def create_separator():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            palette = line.palette()
            palette.setColor(QPalette.ColorRole.WindowText, palette.color(QPalette.ColorRole.Mid))
            line.setPalette(palette)
            return line

        # ===================================================================
        # GENERAL TAB
        # ===================================================================
        general_tab = QWidget()
        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        general_scroll.setFrameShape(QFrame.Shape.NoFrame)

        general_content = QWidget()
        self.general_layout = QVBoxLayout(general_content)
        self.general_layout.setSpacing(8)  # Reduced from 12
        self.general_layout.setContentsMargins(6, 6, 6, 6)  # Reduced from 8

        # === Global Palette ===
        self.general_layout.addWidget(create_section_header("🎨 Global Palette"))

        self.palette_combo = PaletteComboBox()
        self.palette_combo.setMinimumHeight(32)
        self.palette_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.palette_combo.paletteValueChanged.connect(self.palette_changed.emit)
        self.general_layout.addWidget(self.palette_combo)

        self.general_layout.addWidget(create_separator())

        # === Overlay Display ===
        self.general_layout.addWidget(create_section_header("👁 Overlay Display"))

        # Individual checkboxes for each detection type
        self.show_hot_spots_checkbox = QCheckBox("Show Hot Spots")
        self.show_hot_spots_checkbox.setChecked(False)  # Disabled by default
        self.show_hot_spots_checkbox.setToolTip("Show/hide hot spot markers on video")
        self.show_hot_spots_checkbox.setMinimumHeight(28)
        self.general_layout.addWidget(self.show_hot_spots_checkbox)

        self.show_cold_spots_checkbox = QCheckBox("Show Cold Spots")
        self.show_cold_spots_checkbox.setChecked(False)  # Disabled by default
        self.show_cold_spots_checkbox.setToolTip("Show/hide cold spot markers on video")
        self.show_cold_spots_checkbox.setMinimumHeight(28)
        self.general_layout.addWidget(self.show_cold_spots_checkbox)

        self.show_anomalies_checkbox = QCheckBox("Show Anomalies")
        self.show_anomalies_checkbox.setChecked(False)  # Disabled by default
        self.show_anomalies_checkbox.setToolTip("Show/hide thermal anomaly markers on video")
        self.show_anomalies_checkbox.setMinimumHeight(28)
        self.general_layout.addWidget(self.show_anomalies_checkbox)

        self.general_layout.addWidget(create_separator())

        # === Detection Results ===
        self.general_layout.addWidget(create_section_header("🎯 Detection Results"))

        self.detection_label = QLabel("No detections")
        self.detection_label.setWordWrap(True)
        font = QFont("Consolas", 10)
        self.detection_label.setFont(font)
        self.general_layout.addWidget(self.detection_label)

        self.general_layout.addWidget(create_separator())


        # === Hot Spots ===
        self.general_layout.addWidget(create_section_header("🔥 Hot Spots"))

        self.hotspot_list = QListWidget()
        self.hotspot_list.setMaximumHeight(90)  # Increased to show more items
        self.hotspot_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont()
        font.setPointSize(10)
        self.hotspot_list.setFont(font)
        self.general_layout.addWidget(self.hotspot_list)

        self.general_layout.addWidget(create_separator())

        # === Cold Spots ===
        self.general_layout.addWidget(create_section_header("❄️ Cold Spots"))

        self.coldspot_list = QListWidget()
        self.coldspot_list.setMaximumHeight(90)  # Increased to show more items
        self.coldspot_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont()
        font.setPointSize(10)
        self.coldspot_list.setFont(font)
        self.general_layout.addWidget(self.coldspot_list)

        self.general_layout.addWidget(create_separator())

        # === Thermal Anomalies ===
        self.general_layout.addWidget(create_section_header("⚠️ Thermal Anomalies"))

        self.anomaly_list = QListWidget()
        self.anomaly_list.setMaximumHeight(90)  # Increased to show more items
        self.anomaly_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        font = QFont()
        font.setPointSize(10)
        self.anomaly_list.setFont(font)
        self.general_layout.addWidget(self.anomaly_list)

        self.general_layout.addWidget(create_separator())

        # === ROI Summary ===
        self.general_layout.addWidget(create_section_header("📍 ROI Summary"))

        self.roi_summary_label = QLabel("No active ROIs")
        self.roi_summary_label.setWordWrap(True)
        font = QFont("Consolas", 10)
        self.roi_summary_label.setFont(font)
        self.general_layout.addWidget(self.roi_summary_label)

        self.general_layout.addWidget(create_separator())

        # === Temperature Statistics ===
        self.general_layout.addWidget(create_section_header("📊 Temperature Statistics"))

        from PyQt6.QtWidgets import QSizePolicy
        self.stats_label = QLabel("No data")
        self.stats_label.setWordWrap(True)
        self.stats_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        font = QFont("Consolas", 10)
        self.stats_label.setFont(font)
        self.stats_label.setStyleSheet("padding: 8px;")
        self.general_layout.addWidget(self.stats_label)

        # Baseline control
        self.baseline_btn = QPushButton("🔒 Lock Baseline")
        self.baseline_btn.setCheckable(True)
        self.baseline_btn.setToolTip("Lock current mean temperature as baseline for relative measurements")
        self.baseline_btn.setMinimumHeight(32)
        self.general_layout.addWidget(self.baseline_btn)

        self.general_layout.addWidget(create_separator())

        # === Temperature Trend ===
        self.general_layout.addWidget(create_section_header("📈 Temperature Trend"))

        self.trend_label = QLabel("No trend data")
        self.trend_label.setWordWrap(True)
        self.trend_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        font = QFont("Consolas", 10)
        self.trend_label.setFont(font)
        self.trend_label.setStyleSheet("padding: 8px;")
        self.general_layout.addWidget(self.trend_label)

        self.general_layout.addWidget(create_separator())

        # === Temperature Histogram ===
        self.general_layout.addWidget(create_section_header("📊 Temperature Histogram"))

        try:
            from thermal_inspection.gui.widgets import TemperatureHistogramWidget
            self.histogram_widget = TemperatureHistogramWidget()
            self.histogram_widget.setMinimumHeight(150)
            self.histogram_widget.setMaximumHeight(200)
            self.general_layout.addWidget(self.histogram_widget)
            logger.info("Temperature histogram widget added")
        except ImportError as e:
            logger.warning(f"Could not import TemperatureHistogramWidget: {e}")
            self.histogram_widget = None
            no_histogram_label = QLabel("Histogram unavailable\n(pyqtgraph not installed)")
            no_histogram_label.setStyleSheet("padding: 8px; color: #888;")
            self.general_layout.addWidget(no_histogram_label)

        self.general_layout.addStretch()

        general_scroll.setWidget(general_content)
        general_tab_layout = QVBoxLayout(general_tab)
        general_tab_layout.setContentsMargins(0, 0, 0, 0)
        general_tab_layout.addWidget(general_scroll)

        self.analysis_tabs.addTab(general_tab, "General")

        # ===================================================================
        # SPOT METERS TAB (New in Phase 6)
        # ===================================================================
        spot_tab = QWidget()
        spot_layout = QVBoxLayout(spot_tab)
        spot_layout.setContentsMargins(6, 6, 6, 6)
        spot_layout.setSpacing(8)

        spot_layout.addWidget(create_section_header("🎯 Spot Meter Controls"))

        # Add Spot Meter button (toggle mode)
        spot_mode_layout = QHBoxLayout()
        self.spot_meter_btn = QPushButton("✚ Add Spot Meter")
        self.spot_meter_btn.setCheckable(True)
        self.spot_meter_btn.setToolTip("Click on video to add temperature measurement points")
        self.spot_meter_btn.setMinimumHeight(32)
        spot_mode_layout.addWidget(self.spot_meter_btn)
        spot_layout.addLayout(spot_mode_layout)

        spot_layout.addWidget(create_separator())

        self.spot_meter_panel = SpotMeterPanel()
        spot_layout.addWidget(self.spot_meter_panel)

        self.analysis_tabs.addTab(spot_tab, "Spot Meters")

        # ===================================================================
        # OVERLAYS TAB (Phase 1 - Feature 4)
        # ===================================================================
        overlays_tab = QWidget()
        overlays_layout = QVBoxLayout(overlays_tab)
        overlays_layout.setContentsMargins(6, 6, 6, 6)
        overlays_layout.setSpacing(8)

        overlays_layout.addWidget(create_section_header("📐 Grid Overlay"))

        # Add Grid Overlay Panel
        self.grid_overlay_panel = GridOverlayPanel()
        overlays_layout.addWidget(self.grid_overlay_panel)

        overlays_layout.addStretch()

        self.analysis_tabs.addTab(overlays_tab, "Overlays")

        # Connect signals
        self.baseline_btn.toggled.connect(self.baseline_toggled.emit)
        self.spot_meter_btn.toggled.connect(self._on_spot_meter_toggled)

        # Connect SpotMeterPanel signals
        self.spot_meter_panel.clear_all_requested.connect(self._on_clear_spots_clicked)
        # Note: preset_requested is connected in InspectionAppWindow._connect_signals

        # Connect individual detection type checkboxes via signals
        self.show_hot_spots_checkbox.toggled.connect(self.show_hot_spots_toggled.emit)
        self.show_cold_spots_checkbox.toggled.connect(self.show_cold_spots_toggled.emit)
        self.show_anomalies_checkbox.toggled.connect(self.show_anomalies_toggled.emit)

    def _on_global_palette_changed(self, palette_name: str):
        """Handle global palette change."""
        # Remove category header prefix and indentation if present
        clean_name = palette_name.strip().lstrip("─ ")
        if clean_name and not clean_name.startswith("───"):
            self.palette_changed.emit(clean_name)

    def _on_roi_selected(self, row: int):
        """Handle ROI selection in list."""
        # This is triggered by single click, but might be part of multi-select
        # We'll just update the palette combo based on the current item if only one is selected
        selected_items = self.roi_list.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            roi_id = item.data(Qt.ItemDataRole.UserRole)
            logger.debug(f"Panel internal selection: {roi_id}")
            self.roi_selected.emit(roi_id)

            # Update palette combo
            if 0 <= row < len(self.current_rois):
                 roi = next((r for r in self.current_rois if r.roi_id == roi_id), None)
                 if roi and roi.custom_palette:
                    target_palette = roi.custom_palette
                    found_index = -1

                    # Robust search for palette
                    for i in range(self.roi_palette_combo.count()):
                        item_text = self.roi_palette_combo.itemText(i)
                        if "───" in item_text:
                            continue
                        # Clean item text to match stored palette name
                        clean_text = item_text.strip().lstrip("─ ")
                        if clean_text.lower() == target_palette.lower():
                            found_index = i
                            break

                    if found_index >= 0:
                        self.roi_palette_combo.blockSignals(True)
                        self.roi_palette_combo.setCurrentIndex(found_index)
                        self.roi_palette_combo.blockSignals(False)
                        logger.debug(f"Synced combo to ROI palette: {target_palette}")
                    else:
                         logger.warning(f"Could not find palette '{target_palette}' in combo box")

    def _on_delete_rois_clicked(self):
        """Handle delete selected ROIs button."""
        selected_items = self.roi_list.selectedItems()
        if not selected_items:
            return

        count = len(selected_items)
        confirm = QMessageBox.question(
            self,
            "Delete ROIs",
            f"Are you sure you want to delete {count} ROI(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            ids_to_delete = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
            for roi_id in ids_to_delete:
                if roi_id:
                    self.roi_deleted.emit(roi_id)

    def _on_delete_all_rois_clicked(self):
        """Handle delete all ROIs button."""
        if self.roi_list.count() == 0:
            return

        confirm = QMessageBox.question(
            self,
            "Delete All ROIs",
            "Are you sure you want to delete ALL ROIs?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            # Create a copy of IDs to avoid modification during iteration issues if immediate updates happen
            ids_to_delete = []
            for i in range(self.roi_list.count()):
                item = self.roi_list.item(i)
                ids_to_delete.append(item.data(Qt.ItemDataRole.UserRole))

            for roi_id in ids_to_delete:
                if roi_id:
                    self.roi_deleted.emit(roi_id)

    def _on_roi_palette_combo_changed(self, palette_name: str):
        """Handle ROI palette change."""
        # Remove category header prefix and indentation if present
        clean_name = palette_name.strip().lstrip("─ ")
        if clean_name and not clean_name.startswith("───"):
            # Apply to all selected ROIs
            selected_items = self.roi_list.selectedItems()
            if selected_items:
                for item in selected_items:
                    roi_id = item.data(Qt.ItemDataRole.UserRole)
                    if roi_id:
                        self.roi_palette_changed.emit(roi_id, clean_name)
                        logger.info(f"Setting ROI {roi_id} palette to {clean_name}")

    def select_roi(self, roi_id: str):
        """Select ROI in list by ID."""
        logger.debug(f"Panel selecting ROI: {roi_id}")
        found = False
        for i in range(self.roi_list.count()):
            item = self.roi_list.item(i)
            item_id = item.data(Qt.ItemDataRole.UserRole)
            if item_id == roi_id:
                logger.debug(f"ROI {roi_id} found at index {i}, selecting...")
                self.roi_list.setCurrentRow(i)
                found = True
                break

        if not found:
            logger.warning(f"ROI {roi_id} not found in ROI list (count: {self.roi_list.count()})")



    # Handlers for detection toggles are now signals emitted directly
    # _on_show_hot_spots_toggled, _on_show_cold_spots_toggled, _on_show_anomalies_toggled
    # are removed in favor of direct signal emission to parent InspectionAppWindow

    # Direct signal emission handlers
    def _on_spot_meter_toggled(self, checked: bool):
        """Handle spot meter toggle button."""
        logger.info(f"ThermalAnalysisPanel: Spot meter toggled to {checked}, emitting signal")
        self.spot_meter_toggled.emit(checked)

    def _on_clear_spots_clicked(self):
        """Handle clear spots button click from SpotMeterPanel."""
        logger.info("ThermalAnalysisPanel: Clear spots clicked, emitting signal")
        self.spot_meter_panel.clear()  # Clear the panel's internal state
        self.clear_spots_clicked.emit()

    def update_detection_results(self, motion_count: int, edge_count: int, anomaly_count: int):
        """Update detection results display."""
        text = (
            f"Motion Events: {motion_count}\n"
            f"Edge Clusters: {edge_count}\n"
            f"Anomalies:     {anomaly_count}"
        )
        self.detection_label.setText(text)

    def update_rois(self, rois: List[ROI]):
        """Update ROI summary display in General tab."""
        count = len(rois)

        if count == 0:
            self.roi_summary_label.setText("No active ROIs")
            return

        # Calculate ROI type breakdown
        types = {}
        for roi in rois:
            t = roi.roi_type.value
            types[t] = types.get(t, 0) + 1

        summary = f"Total ROIs: {count}\n"
        for t, c in types.items():
            summary += f"• {t}: {c}\n"

        self.roi_summary_label.setText(summary)



    def update_statistics(self, stats: Optional[ThermalStatistics]):
        """Update temperature statistics display."""
        if stats is None:
            self.stats_label.setText("No data")
            self.stats_label.setToolTip("")
            return

        unit = stats.unit
        text = (
            f"Min:  {stats.min_temp:.1f}{unit}\n"
            f"Max:  {stats.max_temp:.1f}{unit}\n"
            f"Mean: {stats.mean_temp:.1f}{unit}\n"
            f"Std:  {stats.std_temp:.1f}{unit}"
        )

        # Create detailed tooltip
        tooltip = (
            f"Temperature Statistics:\n"
            f"Minimum: {stats.min_temp:.2f}{unit}\n"
            f"Maximum: {stats.max_temp:.2f}{unit}\n"
            f"Mean (Average): {stats.mean_temp:.2f}{unit}\n"
            f"Standard Deviation: {stats.std_temp:.2f}{unit}"
        )

        if stats.relative_mean is not None:
            text += f"\n\nΔ Mean: {stats.relative_mean:+.1f}{unit}"
            tooltip += f"\nRelative to Baseline: {stats.relative_mean:+.2f}{unit}"

        self.stats_label.setText(text)
        self.stats_label.setToolTip(tooltip)

    def update_hot_spots(self, hot_spots: List[HotSpot]):
        """Update hot spot list."""
        self.hotspot_list.clear()
        for i, hs in enumerate(hot_spots):
            text = f"#{i}: {hs.max_temp:.1f}{hs.unit} at ({hs.centroid[0]:.0f}, {hs.centroid[1]:.0f})"
            item = QListWidgetItem(text)
            # Add tooltip with full information
            tooltip = f"Hot Spot #{i}\nTemperature: {hs.max_temp:.2f}{hs.unit}\nLocation: ({hs.centroid[0]:.1f}, {hs.centroid[1]:.1f})\nArea: {hs.area} pixels"
            item.setToolTip(tooltip)
            self.hotspot_list.addItem(item)

    def update_cold_spots(self, cold_spots: List[ColdSpot]):
        """Update cold spot list."""
        self.coldspot_list.clear()
        for i, cs in enumerate(cold_spots):
            text = f"#{i}: {cs.min_temp:.1f}{cs.unit} at ({cs.centroid[0]:.0f}, {cs.centroid[1]:.0f})"
            item = QListWidgetItem(text)
            # Add tooltip with full information
            tooltip = f"Cold Spot #{i}\nTemperature: {cs.min_temp:.2f}{cs.unit}\nLocation: ({cs.centroid[0]:.1f}, {cs.centroid[1]:.1f})\nArea: {cs.area} pixels"
            item.setToolTip(tooltip)
            self.coldspot_list.addItem(item)

    def update_anomalies(self, anomalies: List[ThermalAnomaly]):
        """Update anomaly list."""
        self.anomaly_list.clear()
        for i, anom in enumerate(anomalies, 1):
            friendly_type = ANOMALY_TYPE_LABELS.get(anom.anomaly_type, anom.anomaly_type.value)
            text = f"#{i}: {friendly_type} - {anom.description}"
            item = QListWidgetItem(text)
            # Add tooltip with full information
            tooltip = f"Anomaly #{i}\nType: {friendly_type}\nDescription: {anom.description}\nSeverity: {anom.severity}\nLocation: ({anom.location[0]:.1f}, {anom.location[1]:.1f})"
            item.setToolTip(tooltip)
            self.anomaly_list.addItem(item)

    def update_trend(self, trend: Optional[TemperatureTrend]):
        """Update temperature trend display."""
        if trend is None or trend.data_points == 0:
            self.trend_label.setText("No trend data")
            self.trend_label.setToolTip("")
            return

        text = (
            f"Direction: {trend.trend_direction}\n"
            f"Rate: {trend.rate_of_change:.3f}°C/s\n"
            f"Predicted: {trend.predicted_temp:.1f}°C\n"
            f"Data points: {trend.data_points}"
        )

        # Create detailed tooltip
        tooltip = (
            f"Temperature Trend Analysis:\n"
            f"Trend Direction: {trend.trend_direction}\n"
            f"Rate of Change: {trend.rate_of_change:.4f}°C/second\n"
            f"Predicted Temperature: {trend.predicted_temp:.2f}°C\n"
            f"Based on {trend.data_points} data points"
        )

        self.trend_label.setText(text)
        self.trend_label.setToolTip(tooltip)

    def update_histogram(self, temp_array):
        """Update histogram widget with temperature data.

        Args:
            temp_array: 2D numpy array of temperature values, or flattened 1D array
        """
        if self.histogram_widget is not None and temp_array is not None:
            import numpy as np
            # Flatten if 2D - ravel(), not flatten(): a view when the array is
            # already contiguous (the common case here) instead of an
            # unconditional copy of the full ~327K-element frame, right before
            # 97% of it gets thrown away by the downsampling below anyway.
            if len(temp_array.shape) > 1:
                temp_array = temp_array.ravel()

            # Downsample for performance - histogram only needs ~10K samples for accuracy.
            # np.random.choice(..., replace=False) on ~327K elements runs every
            # frame on the main thread (this is called straight from the render
            # loop) - sampling without replacement is effectively a partial
            # shuffle, measured as a real per-frame cost. A thermal frame has no
            # periodic structure that would bias a temperature histogram's shape
            # under a fixed stride, so a strided sample (just an array view, no
            # RNG work at all) gives visually equivalent results for free.
            max_samples = 10000
            if len(temp_array) > max_samples:
                stride = len(temp_array) // max_samples
                temp_array = temp_array[::stride]

            self.histogram_widget.update_histogram(temp_array)

    def set_histogram_palette_lut(self, lut):
        """Set the palette LUT for histogram bar coloring.

        Args:
            lut: 256x3 numpy array of RGB colors
        """
        if self.histogram_widget is not None:
            self.histogram_widget.set_palette_lut(lut)

    def set_histogram_temperature_unit(self, unit: str):
        """Set the temperature unit for histogram display.

        Args:
            unit: 'C', 'F', 'K', or 'RAW'
        """
        if self.histogram_widget is not None:
            self.histogram_widget.set_temperature_unit(unit)
