from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QGroupBox, QPushButton, QSplitter, QComboBox,
    QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
import logging

logger = logging.getLogger(__name__)

class ROITemperaturePanel(QWidget):
    """
    Panel to display per-ROI temperature statistics.
    Shows min/max/avg/std temperature, pixel count, and emissivity for each ROI.
    """
    
    # Signals
    export_data_requested = pyqtSignal()
    clear_history_requested = pyqtSignal(str)  # roi_id
    
    # ROI Management signals
    roi_selected = pyqtSignal(str)  # Emits selected ROI ID
    roi_deleted = pyqtSignal(str)  # Emits deleted ROI ID
    roi_palette_changed = pyqtSignal(str, str)  # Emits (ROI ID, palette name)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.roi_data = {}  # roi_id -> stats dict
        self.current_rois = []  # Store ROI list for management
        self.selected_roi_index = -1  # Track selected ROI
        self._init_ui()
        
        # Optional: Auto-refresh timer (if needed)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_display)
        # Don't auto-start, data will be pushed via update_roi_data()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # === Header ===
        header = QLabel("📐 ROI Manager")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)
        
        # === ROI Management Section ===
        management_group = QGroupBox("ROI Management")
        management_layout = QVBoxLayout(management_group)
        
        # ROI List
        self.roi_list = QListWidget()
        self.roi_list.setAlternatingRowColors(True)
        self.roi_list.setMaximumHeight(150)
        self.roi_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.roi_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        font = QFont()
        font.setPointSize(10)
        self.roi_list.setFont(font)
        self.roi_list.currentRowChanged.connect(self._on_roi_selected)
        management_layout.addWidget(self.roi_list)
        
        # ROI Actions (Delete buttons)
        roi_actions_layout = QHBoxLayout()
        roi_actions_layout.setSpacing(10)
        
        self.roi_delete_btn = QPushButton("🗑 Delete Selected")
        self.roi_delete_btn.setToolTip("Delete selected ROIs")
        self.roi_delete_btn.clicked.connect(self._on_delete_rois_clicked)
        roi_actions_layout.addWidget(self.roi_delete_btn)
        
        self.roi_delete_all_btn = QPushButton("🗑 Delete All")
        self.roi_delete_all_btn.setToolTip("Delete all ROIs")
        self.roi_delete_all_btn.clicked.connect(self._on_delete_all_rois_clicked)
        roi_actions_layout.addWidget(self.roi_delete_all_btn)
        
        management_layout.addLayout(roi_actions_layout)
        
        # ROI palette selector (compact horizontal layout)
        roi_palette_layout = QHBoxLayout()
        roi_palette_layout.setSpacing(8)
        roi_label = QLabel("Palette:")
        font = QFont()
        font.setPointSize(10)
        roi_label.setFont(font)
        roi_palette_layout.addWidget(roi_label)

        self.roi_palette_combo = QComboBox()
        self.roi_palette_combo.setMinimumHeight(32)
        self.roi_palette_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        # Populate with categorized palettes
        self._populate_palette_combo(self.roi_palette_combo)
        # Connect ROI palette signal
        self.roi_palette_combo.currentTextChanged.connect(self._on_roi_palette_combo_changed)
        roi_palette_layout.addWidget(self.roi_palette_combo, 1)
        management_layout.addLayout(roi_palette_layout)
        
        layout.addWidget(management_group)
        
        # === Temperature Statistics Section ===
        stats_group = QGroupBox("Temperature Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_label = QLabel("No ROI data available")
        self.stats_label.setWordWrap(True)
        font = QFont("Consolas", 9)
        self.stats_label.setFont(font)
        stats_layout.addWidget(self.stats_label)
        
        layout.addWidget(stats_group)
        
        # === Controls ===
        controls_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export Data")
        self.export_btn.clicked.connect(self.export_data_requested.emit)
        self.export_btn.setEnabled(False)
        controls_layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.clicked.connect(lambda: self.clear_history_requested.emit("all"))
        self.clear_btn.setEnabled(False)
        controls_layout.addWidget(self.clear_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        layout.addStretch()
    
    def _populate_palette_combo(self, combo: QComboBox):
        """Populate a combo box with categorized palettes."""
        from palette_manager import PaletteType
        
        palette_categories = [
            ("GRAYSCALE", [
                PaletteType.WHITE_HOT, PaletteType.BLACK_HOT,
                PaletteType.GRAY, PaletteType.SEPIA
            ]),
            ("IRON/FIRE", [
                PaletteType.IRONBOW, PaletteType.LAVA, PaletteType.GRADEDFIRE,
                PaletteType.HOTTEST, PaletteType.AMBER, PaletteType.INFERNO
            ]),
            ("RAINBOW", [
                PaletteType.RAINBOW, PaletteType.RAINBOW_HC, PaletteType.RAINBOW_REVERSED,
                PaletteType.SPECTRAL, PaletteType.COOL_HOT
            ]),
            ("COLD/ARCTIC", [
                PaletteType.ARCTIC, PaletteType.ICE,
                PaletteType.WINTER, PaletteType.OCEAN
            ]),
            ("SCIENTIFIC", [
                PaletteType.VIRIDIS, PaletteType.PLASMA, PaletteType.MAGMA,
                PaletteType.CIVIDIS, PaletteType.TURBO
            ]),
            ("DIVERGING", [
                PaletteType.BLUE_RED, PaletteType.COOL_WARM, PaletteType.PURPLE_ORANGE,
                PaletteType.GREEN_RED, PaletteType.BLUE_YELLOW, PaletteType.PINK_GREEN
            ]),
            ("SEQUENTIAL", [
                PaletteType.GLOBOW, PaletteType.MEDICAL, PaletteType.THERMAL,
                PaletteType.HELIX, PaletteType.CUBEHELIX, PaletteType.TWILIGHT, PaletteType.DUSK
            ]),
            ("SPECIALIZED", [
                PaletteType.FUSION, PaletteType.PRISM, PaletteType.ALARM,
                PaletteType.LAPLACIAN, PaletteType.ISOTHERM, PaletteType.VELOCITY,
                PaletteType.TERRAIN, PaletteType.DEPTH
            ])
        ]

        # Populate combo box with categorized palettes
        for category_name, palettes in palette_categories:
            # Add category header (bold, disabled)
            combo.addItem(f"─── {category_name} ───")
            idx = combo.count() - 1
            item = combo.model().item(idx)
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            item.setEnabled(False)

            # Add palette items (indented)
            for palette in palettes:
                combo.addItem(f"  {palette.value}")
    
    def update_rois(self, rois):
        """Update ROI list for management."""
        from roi_manager import ROI
        
        # Store ROI list
        current_ids = [r.roi_id for r in self.current_rois]
        new_ids = [r.roi_id for r in rois]
        
        self.current_rois = rois
        
        # Only rebuild list if ROIs changed
        if current_ids != new_ids:
            # Preserve selection
            selected_id = None
            if self.selected_roi_index >= 0 and self.selected_roi_index < len(current_ids):
                selected_id = current_ids[self.selected_roi_index]
            
            logger.debug(f"Rebuilding ROI list (was {len(current_ids)}, now {len(rois)})")
            
            # Update ROI List Widget
            self.roi_list.blockSignals(True)  # Block signals during rebuild
            self.roi_list.clear()
            for roi in rois:
                # Main label with ROI name and type
                label = f"{roi.label} ({roi.roi_type.value})"
                if roi.custom_palette:
                    label += " 🎨"  # Visual indicator
                    # Add palette name in small text below
                    label += f"\n  {roi.custom_palette}"
                    
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, roi.roi_id)
                self.roi_list.addItem(item)
            
            # Restore selection if possible
            if selected_id:
                for i in range(self.roi_list.count()):
                    if self.roi_list.item(i).data(Qt.ItemDataRole.UserRole) == selected_id:
                        self.roi_list.setCurrentRow(i)
                        self.selected_roi_index = i
                        break
            else:
                self.selected_roi_index = -1
                
            self.roi_list.blockSignals(False)  # Unblock
    
    def _on_roi_selected(self, row: int):
        """Handle ROI selection in list."""
        selected_items = self.roi_list.selectedItems()
        if len(selected_items) == 1:
            item = selected_items[0]
            roi_id = item.data(Qt.ItemDataRole.UserRole)
            logger.debug(f"ROI Manager: ROI selected: {roi_id}")
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
            # Create a copy of IDs to avoid modification during iteration
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
    
    def update_roi_data(self, roi_data: dict):
        """
        Update display with new ROI temperature data.
        
        Args:
            roi_data: Dictionary mapping roi_id -> stats dict
                     from ROIRadiometricAnalyzer.analyze_all_rois()
        """
        # Allow empty dict to clear the display
        if roi_data is None:
            return
            
        # logger.debug(f"ROITemperaturePanel received data for {len(roi_data)} ROIs")
        self.roi_data = roi_data
        self._refresh_display()
    
    def _refresh_display(self):
        """Refresh the GUI with current data."""
        # Note: ROI list is now managed by update_rois(), not here
        # We just update statistics
        
        if not self.roi_data:
            self.stats_label.setText("No ROI data available")
            self.export_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            return
        
        # Enable controls
        self.export_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        # Update detailed stats
        self._update_stats_display()
    
    def _get_temperature_color(self, temp: float) -> QColor:
        """Color code temperature value."""
        if temp < 10:
            return QColor(100, 150, 255)  # Cold - Blue
        elif temp < 30:
            return QColor(100, 200, 100)  # Normal - Green
        elif temp < 50:
            return QColor(255, 200, 0)    # Warm - Yellow/Orange
        else:
            return QColor(255, 100, 100)  # Hot - Red
    
    def _update_stats_display(self):
        """Update the detailed statistics text."""
        if not self.roi_data:
            return
        
        # Build detailed text
        lines = []
        lines.append(f"Total ROIs: {len(self.roi_data)}\n")
        
        for roi_id, stats in self.roi_data.items():
            roi_name = stats.get('roi_name', roi_id)
            lines.append(f"\n{roi_name}:")
            lines.append(f"  ID: {roi_id}")
            
            temp_avg = stats.get('temp_avg')
            temp_min = stats.get('temp_min')
            temp_max = stats.get('temp_max')
            temp_std = stats.get('temp_std')
            
            if temp_avg is not None:
                lines.append(f"  Avg: {temp_avg:.2f}°C")
                lines.append(f"  Min: {temp_min:.2f}°C @ {stats.get('min_location', 'N/A')}")
                lines.append(f"  Max: {temp_max:.2f}°C @ {stats.get('max_location', 'N/A')}")
                lines.append(f"  Std: {temp_std:.2f}°C")
            else:
                lines.append("  No temperature data")
            
            pixel_count = stats.get('pixel_count', 0)
            lines.append(f"  Pixels: {pixel_count}")
            
            emissivity = stats.get('emissivity', 'global')
            if isinstance(emissivity, float):
                lines.append(f"  Emissivity: {emissivity:.3f}")
            else:
                lines.append(f"  Emissivity: {emissivity}")
        
        self.stats_label.setText('\n'.join(lines))
