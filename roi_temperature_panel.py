from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QGroupBox, QPushButton, QSplitter
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
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.roi_data = {}  # roi_id -> stats dict
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
        header = QLabel("📍 Per-ROI Temperature Analysis")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)
        
        # === ROI List ===
        list_group = QGroupBox("Active ROIs")
        list_layout = QVBoxLayout(list_group)
        
        self.roi_list = QListWidget()
        self.roi_list.setAlternatingRowColors(True)
        list_layout.addWidget(self.roi_list)
        
        layout.addWidget(list_group)
        
        # === Statistics Display ===
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
        # Update ROI list
        self.roi_list.clear()
        
        if not self.roi_data:
            self.stats_label.setText("No ROI data available")
            self.export_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            return
        
        # Enable controls
        self.export_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        
        # Populate list with summary
        for roi_id, stats in self.roi_data.items():
            roi_name = stats.get('roi_name', roi_id)
            temp_avg = stats.get('temp_avg')
            
            if temp_avg is not None:
                # Color code by temperature
                temp_color = self._get_temperature_color(temp_avg)
                item_text = f"{roi_name}: {temp_avg:.1f}°C"
                
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, roi_id)
                item.setForeground(temp_color)
                self.roi_list.addItem(item)
        
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
