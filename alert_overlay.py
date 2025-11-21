#!/usr/bin/env python3
"""
Alert Overlay Widget for ADAS-Compliant Visual Warnings
Implements multi-stage proximity alerts and critical text overlays
Following SAE J2400, ISO 15007, and NHTSA guidelines
"""
import math
import time
import logging
from typing import List, Optional
from collections import defaultdict

try:
    from PyQt5.QtWidgets import QWidget, QLabel
    from PyQt5.QtCore import Qt, QTimer, QRect
    from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QBrush
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

# from road_analyzer import Alert, AlertLevel  # Commented out - road_analyzer removed

# Stub classes for compatibility
class AlertLevel:
    """Stub AlertLevel class for compatibility"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class Alert:
    """Stub Alert class for compatibility"""
    def __init__(self, level=AlertLevel.INFO, message="", detection=None):
        self.level = level
        self.message = message
        self.detection = detection

from object_detector import Detection
from config import get_config

logger = logging.getLogger(__name__)


class AlertOverlayWidget(QWidget):
    """
    ADAS-compliant alert overlay widget
    Displays proximity zones and critical text alerts over video feed

    Design Principles (ADAS Best Practices):
    1. Peripheral placement (not center) per SAE J2400
    2. Multi-stage alerts based on threat level
    3. Text overlays for CRITICAL alerts only
    4. Pulsing visual cues for attention (without habituation)
    5. Color hierarchy: Red (critical) > Yellow (warning) > Blue (info)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Make transparent background
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # Pass mouse events through

        # Alert state
        self.alerts: List[Alert] = []
        self.detections: List[Detection] = []
        self.proximity_zones = {
            'left': [],
            'right': [],
            'center': []
        }

        # Video frame dimensions (for zone calculation)
        # Detection bboxes are in video coordinates, not widget coordinates
        self.frame_width = 640   # Default, will be updated
        self.frame_height = 512  # Default, will be updated

        # Pulse animation
        self.pulse_phase = 0.0
        self.last_pulse_update = time.time()

        # Alert persistence (prevent flickering)
        self.persistent_alerts = {}
        self.alert_persistence_seconds = 3.0

        # Proximity alert timeout (clear after no detections)
        self.last_detection_time = 0
        self.proximity_timeout_seconds = 2.0  # Clear after 2 seconds of no detections

        # Update timer for animations
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(50)  # 20 FPS for smooth pulsing

        # Color scheme (ADAS standard)
        self.colors = {
            'critical': QColor(255, 0, 0, 180),      # Red - Critical
            'warning': QColor(255, 170, 0, 150),     # Yellow - Warning
            'info': QColor(0, 170, 255, 120),        # Blue - Info
            'text': QColor(255, 255, 255, 255),      # White text
            'text_bg': QColor(0, 0, 0, 200),         # Black text background
        }

        # Load object importance settings
        config = get_config()
        self.object_importance = {}
        for obj_type in ['person', 'bicycle', 'motorcycle', 'dog', 'cat', 'car', 'truck', 'bus',
                         'traffic light', 'stop sign', 'bird', 'motion', 'horse', 'cow', 'sheep',
                         'elephant', 'bear', 'zebra', 'giraffe']:
            self.object_importance[obj_type] = config.get(f'object_importance.{obj_type}', 'medium')

        logger.info("AlertOverlayWidget initialized (ADAS-compliant)")

    def _is_critical_object(self, class_name: str) -> bool:
        """
        Check if an object is considered critical based on its importance level

        Args:
            class_name: Object class name (e.g., 'person', 'car')

        Returns:
            True if object importance is 'critical', False otherwise
        """
        importance = self.object_importance.get(class_name, 'medium')
        return importance == 'critical'

    def set_frame_dimensions(self, width: int, height: int):
        """
        Set video frame dimensions for accurate zone calculation

        CRITICAL: Detection bboxes are in video coordinates, not widget coordinates
        This method must be called with actual video frame dimensions

        Args:
            width: Video frame width (e.g., 640)
            height: Video frame height (e.g., 512)
        """
        self.frame_width = width
        self.frame_height = height
        logger.debug(f"Alert overlay frame dimensions set: {width}x{height}")

    def update_alerts(self, alerts: List[Alert], detections: List[Detection]):
        """
        Update alert data and trigger repaint

        Args:
            alerts: List of Alert objects from RoadAnalyzer
            detections: List of Detection objects for proximity zones
        """
        self.alerts = alerts
        self.detections = detections

        # Update last detection time if we have detections
        if len(detections) > 0:
            self.last_detection_time = time.time()

        # Check for timeout - clear proximity zones if no recent detections
        current_time = time.time()
        if current_time - self.last_detection_time > self.proximity_timeout_seconds:
            self.proximity_zones = {'left': [], 'right': [], 'center': []}
            self.detections = []  # Also clear detections to stop rendering
        else:
            # Update proximity zones (left/right/center based on x-position)
            self._update_proximity_zones()

        # Update persistent alerts
        self._update_persistent_alerts()

        # Trigger repaint
        self.update()

    def _update_proximity_zones(self):
        """
        Classify detections into left/right/center proximity zones
        Based on horizontal position in frame

        CRITICAL: Uses actual video frame dimensions, not widget dimensions
        Detection bboxes are in video coordinates (e.g., 640x512)
        Widget might be scaled (e.g., 1280x960)
        """
        if not self.detections:
            self.proximity_zones = {'left': [], 'right': [], 'center': []}
            return

        # Use actual video frame width, not widget width
        # Detection bboxes are in video coordinates
        frame_width = self.frame_width

        # Zone boundaries (thirds)
        left_boundary = frame_width / 3
        right_boundary = 2 * frame_width / 3

        zones = {'left': [], 'right': [], 'center': []}

        for det in self.detections:
            # Get center x of bounding box
            x1, y1, x2, y2 = det.bbox
            center_x = (x1 + x2) / 2

            if center_x < left_boundary:
                zones['left'].append(det)
                zone_name = 'LEFT'
            elif center_x > right_boundary:
                zones['right'].append(det)
                zone_name = 'RIGHT'
            else:
                zones['center'].append(det)
                zone_name = 'CENTER'

            logger.debug(f"Detection '{det.class_name}' at x={center_x:.0f} → {zone_name} zone (boundaries: <{left_boundary:.0f}, >{right_boundary:.0f}, frame_width={frame_width})")

        self.proximity_zones = zones

        # Summary logging
        if len(zones['left']) > 0 or len(zones['right']) > 0 or len(zones['center']) > 0:
            logger.info(f"Proximity zones: LEFT={len(zones['left'])}, CENTER={len(zones['center'])}, RIGHT={len(zones['right'])}")

    def _update_persistent_alerts(self):
        """
        Maintain persistent alerts to prevent flickering
        Alerts fade out over alert_persistence_seconds
        """
        current_time = time.time()

        # Add new alerts
        for alert in self.alerts:
            alert_key = f"{alert.level.name}_{alert.message}"
            self.persistent_alerts[alert_key] = {
                'alert': alert,
                'last_seen': current_time
            }

        # Remove old alerts
        expired = []
        for key, data in self.persistent_alerts.items():
            age = current_time - data['last_seen']
            if age > self.alert_persistence_seconds:
                expired.append(key)

        for key in expired:
            del self.persistent_alerts[key]

    def _update_animation(self):
        """Update pulse animation phase"""
        current_time = time.time()
        dt = current_time - self.last_pulse_update
        self.last_pulse_update = current_time

        # 2 Hz pulsing (complete cycle every 0.5 seconds)
        self.pulse_phase = (self.pulse_phase + dt * 2.0) % 1.0

        # Trigger repaint if we have active alerts
        if self.alerts or self.proximity_zones['left'] or self.proximity_zones['right']:
            self.update()

    def paintEvent(self, event):
        """
        Paint alert overlays
        Following ADAS best practices for visual hierarchy
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Draw proximity zone alerts (peripheral, per SAE J2400)
        self._draw_proximity_alerts(painter)

        # 2. Draw critical text alerts (center, for CRITICAL level only)
        # DISABLED: Distracting for driving, proximity alerts are sufficient
        # self._draw_critical_text_alerts(painter)

        painter.end()

    def _draw_proximity_alerts(self, painter: QPainter):
        """
        Draw pulsing proximity zone alerts on left/right sides
        Peripheral placement per SAE J2400 (not center dashboard)

        Center detections show alerts on BOTH sides (threat from both directions)

        Args:
            painter: QPainter instance
        """
        w = self.width()
        h = self.height()

        if w == 0 or h == 0:
            return

        # Calculate pulse intensity (sine wave 0.0 to 1.0)
        pulse_intensity = (math.sin(self.pulse_phase * 2 * math.pi) + 1.0) / 2.0

        alert_width = 50
        alert_margin = 10

        # Determine which sides should show alerts
        # Center detections trigger BOTH sides (bi-directional threat)
        show_left = len(self.proximity_zones['left']) > 0 or len(self.proximity_zones['center']) > 0
        show_right = len(self.proximity_zones['right']) > 0 or len(self.proximity_zones['center']) > 0

        # LEFT SIDE PROXIMITY ALERT
        if show_left:
            # Combine left and center detections for criticality check
            combined_left = self.proximity_zones['left'] + self.proximity_zones['center']
            # Determine alert level based on object importance configuration
            has_critical = any(self._is_critical_object(d.class_name) for d in combined_left)

            if has_critical:
                color = self.colors['critical']
                alpha = int(76 + (pulse_intensity * 127))  # Pulse 30-80%
            else:
                color = self.colors['warning']
                alpha = int(51 + (pulse_intensity * 76))   # Pulse 20-50%

            color.setAlpha(alpha)

            # Draw pulsing bar
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(alert_margin, alert_margin,
                           alert_width, h - 2 * alert_margin)

            # Draw icon and count
            painter.setPen(QPen(self.colors['text']))
            painter.setFont(QFont("Arial", 14, QFont.Bold))

            icon = "[!]"
            painter.drawText(QRect(alert_margin, h // 2 - 30, alert_width, 30),
                           Qt.AlignCenter, icon)

            count = str(len(combined_left))
            painter.drawText(QRect(alert_margin, h // 2 + 10, alert_width, 30),
                           Qt.AlignCenter, count)

        # RIGHT SIDE PROXIMITY ALERT
        if show_right:
            # Combine right and center detections for criticality check
            combined_right = self.proximity_zones['right'] + self.proximity_zones['center']
            # Determine alert level based on object importance configuration
            has_critical = any(self._is_critical_object(d.class_name) for d in combined_right)

            if has_critical:
                color = self.colors['critical']
                alpha = int(76 + (pulse_intensity * 127))
            else:
                color = self.colors['warning']
                alpha = int(51 + (pulse_intensity * 76))

            color.setAlpha(alpha)

            # Draw pulsing bar
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRect(w - alert_margin - alert_width, alert_margin,
                           alert_width, h - 2 * alert_margin)

            # Draw icon and count
            painter.setPen(QPen(self.colors['text']))
            painter.setFont(QFont("Arial", 14, QFont.Bold))

            icon = "[!]"
            painter.drawText(QRect(w - alert_margin - alert_width, h // 2 - 30,
                                  alert_width, 30),
                           Qt.AlignCenter, icon)

            count = str(len(combined_right))
            painter.drawText(QRect(w - alert_margin - alert_width, h // 2 + 10,
                                  alert_width, 30),
                           Qt.AlignCenter, count)

    def _draw_critical_text_alerts(self, painter: QPainter):
        """
        Draw text overlays for CRITICAL alerts only
        Center-top placement for maximum visibility
        Per ADAS guidelines: text alerts reserved for highest priority

        Args:
            painter: QPainter instance
        """
        # Only show CRITICAL level alerts as text
        critical_alerts = [data['alert'] for data in self.persistent_alerts.values()
                          if data['alert'].level == AlertLevel.CRITICAL]

        if not critical_alerts:
            return

        w = self.width()

        # Calculate pulse intensity for animation (same as proximity alerts)
        pulse_intensity = (math.sin(self.pulse_phase * 2 * math.pi) + 1.0) / 2.0

        # Draw at top-center (non-intrusive but visible)
        y_offset = 60

        for i, alert in enumerate(critical_alerts[:3]):  # Max 3 critical alerts
            # Background box
            text = f"[!] {alert.message}"

            painter.setFont(QFont("Arial", 16, QFont.Bold))
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(text)
            text_height = fm.height()

            box_width = text_width + 40
            box_height = text_height + 20
            box_x = (w - box_width) // 2
            box_y = y_offset + (i * (box_height + 10))

            # Pulsing background for critical alerts
            pulse_alpha = int(200 + (pulse_intensity * 55))  # 200-255
            bg_color = QColor(self.colors['critical'])
            bg_color.setAlpha(pulse_alpha)

            painter.setBrush(QBrush(bg_color))
            painter.setPen(QPen(Qt.white, 2))
            painter.drawRoundedRect(box_x, box_y, box_width, box_height, 10, 10)

            # Text
            painter.setPen(QPen(self.colors['text']))
            painter.drawText(QRect(box_x, box_y, box_width, box_height),
                           Qt.AlignCenter, text)

    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts = []
        self.detections = []
        self.proximity_zones = {'left': [], 'right': [], 'center': []}
        self.persistent_alerts = {}
        self.update()
