# UI/UX Design Principles for Thermal Inspection Application

## Document Overview

This document outlines comprehensive UI/UX design principles and PyQt6-specific best practices for polishing the Thermal Inspection Fusion Tool GUI. These guidelines ensure a professional, usable, and visually consistent interface for industrial thermal imaging applications.

---

## Table of Contents

1. [General UI/UX Principles](#general-uiux-principles)
2. [PyQt6-Specific Best Practices](#pyqt6-specific-best-practices)
3. [Professional/Industrial Application Design](#professionalindustrial-application-design)
4. [Data Visualization for Thermal Imaging](#data-visualization-for-thermal-imaging)
5. [Color Theory for Technical Applications](#color-theory-for-technical-applications)
6. [Accessibility Guidelines](#accessibility-guidelines)
7. [Layout and Spacing](#layout-and-spacing)
8. [Typography and Readability](#typography-and-readability)
9. [Icons and Controls](#icons-and-controls)
10. [Error Handling and User Feedback](#error-handling-and-user-feedback)
11. [Implementation Checklist](#implementation-checklist)

---

## 1. General UI/UX Principles

### Nielsen's 10 Usability Heuristics

#### 1.1 Visibility of System Status
**Principle**: Always keep users informed about what's going on through appropriate feedback.

**Application to Thermal Inspection**:
- Show camera connection status with clear indicators (✅ Connected / ❌ Disconnected)
- Display real-time FPS counter
- Show processing status (acquiring frame, analyzing, rendering)
- Indicate when recording or capturing snapshots
- Display thermal camera temperature (FPA temp)

**PyQt Implementation**:
```python
# Status bar with real-time updates
self.status_label = QLabel("Ready")
self.fps_label = QLabel("FPS: 0.0")
self.camera_status = QLabel("⚫ Disconnected")

# Update regularly
def update_status(self, fps, thermal_connected, rgb_connected):
    self.fps_label.setText(f"FPS: {fps:.1f}")
    if thermal_connected and rgb_connected:
        self.camera_status.setText("🟢 Both Cameras Connected")
        self.camera_status.setStyleSheet("color: #0a0;")
    elif thermal_connected:
        self.camera_status.setText("🟡 Thermal Only")
        self.camera_status.setStyleSheet("color: #fa0;")
```

#### 1.2 Match Between System and Real World
**Principle**: Use familiar language and concepts from the user's domain.

**Application**:
- Use thermal imaging terminology (FFC, AGC, ROI, hot spot, thermal gradient)
- Match physical camera controls (exposure, gain, white balance)
- Use industry-standard thermal palettes (Ironbow, White Hot, etc.)
- Label axes and measurements with proper units (°C, °F, pixels)

#### 1.3 User Control and Freedom
**Principle**: Provide clear exit points and undo options.

**Application**:
- Allow ROI deletion with confirmation
- Undo/redo for ROI operations
- Easy mode switching (thermal only / RGB only / fusion)
- Keyboard shortcuts for quick actions (`Ctrl+Z` for undo, `Esc` to cancel)

**PyQt Implementation**:
```python
# Implement undo stack
self.undo_stack = QUndoStack()

# Add commands
class AddROICommand(QUndoCommand):
    def __init__(self, roi_manager, roi):
        self.roi_manager = roi_manager
        self.roi = roi

    def undo(self):
        self.roi_manager.remove_roi(self.roi.roi_id)

    def redo(self):
        self.roi_manager.add_roi(self.roi)

# Connect to shortcuts
QShortcut(QKeySequence.StandardKey.Undo, self, self.undo_stack.undo)
```

#### 1.4 Consistency and Standards
**Principle**: Follow platform and domain conventions.

**Application**:
- Consistent button placement (OK on right, Cancel on left in Windows)
- Standard icons (💾 for save, 📂 for open, 🔄 for refresh)
- Uniform color scheme across all panels
- Consistent spacing and alignment
- Same terminology throughout (don't switch between "thermal" and "IR")

#### 1.5 Error Prevention
**Principle**: Design to prevent problems before they occur.

**Application**:
- Disable controls that don't apply to current mode
- Validate numeric inputs with range constraints
- Confirm destructive actions (delete all ROIs)
- Prevent invalid camera configurations
- Show tooltips explaining what controls do

**PyQt Implementation**:
```python
# Constrained numeric input
self.temperature_threshold = QSpinBox()
self.temperature_threshold.setRange(-40, 500)  # Valid thermal range
self.temperature_threshold.setSuffix(" °C")

# Confirmation dialogs
def delete_all_rois(self):
    reply = QMessageBox.question(
        self,
        'Confirm Deletion',
        f'Delete all {len(self.rois)} ROIs? This cannot be undone.',
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
    )
    if reply == QMessageBox.StandardButton.Yes:
        self.roi_manager.clear_all()
```

#### 1.6 Recognition Rather Than Recall
**Principle**: Make objects, actions, and options visible.

**Application**:
- Show palette previews in dropdown (not just names)
- Display current fusion mode with visual indicator
- Show recent ROI configurations
- Keep control panels visible rather than buried in menus
- Use icons with labels (not just icons)

#### 1.7 Flexibility and Efficiency of Use
**Principle**: Support both novice and expert users.

**Application**:
- Keyboard shortcuts for experts (`F` for FFC, `R` for record, `S` for snapshot)
- Mouse controls for novices (clickable buttons)
- Preset configurations for common scenarios
- Quick access toolbar for frequent actions
- Right-click context menus

**PyQt Implementation**:
```python
# Keyboard shortcuts
QShortcut(QKeySequence('F'), self, self.trigger_ffc)
QShortcut(QKeySequence('R'), self, self.toggle_recording)
QShortcut(QKeySequence('S'), self, self.capture_snapshot)
QShortcut(QKeySequence('Ctrl+R'), self, self.add_rectangle_roi)

# Context menu
def contextMenuEvent(self, event):
    menu = QMenu(self)
    menu.addAction("Add Rectangle ROI", self.add_rectangle_roi)
    menu.addAction("Add Polygon ROI", self.add_polygon_roi)
    menu.addSeparator()
    menu.addAction("Delete ROI", self.delete_roi)
    menu.exec(event.globalPos())
```

#### 1.8 Aesthetic and Minimalist Design
**Principle**: Remove unnecessary elements that compete for attention.

**Application**:
- Clean, uncluttered interface
- White space around controls
- Group related functions together
- Hide advanced features in collapsible sections
- Focus on essential thermal analysis tools

#### 1.9 Help Users Recognize, Diagnose, and Recover from Errors
**Principle**: Express errors in plain language with constructive solutions.

**Application**:
```python
# Bad error message
QMessageBox.critical(self, "Error", "Failed to open camera")

# Good error message
QMessageBox.critical(
    self,
    "Camera Connection Failed",
    "Could not connect to thermal camera on device 0.\n\n"
    "Possible solutions:\n"
    "• Check USB connection\n"
    "• Verify camera is not in use by another application\n"
    "• Try restarting the camera\n\n"
    "Error details: Device not found (errno 19)"
)
```

#### 1.10 Help and Documentation
**Principle**: Provide searchable, task-oriented help.

**Application**:
- Tooltips on all controls
- "What's This?" help mode (`Shift+F1`)
- Embedded help panel
- Link to online documentation
- Quick start guide

**PyQt Implementation**:
```python
# Tooltips
self.ffc_button.setToolTip(
    "Flat Field Correction (FFC)\n"
    "Calibrates thermal sensor for accurate readings.\n"
    "Press F key or click this button.\n"
    "May take 1-2 seconds."
)

# Help action
help_action = QAction("Help", self)
help_action.setShortcut(QKeySequence.StandardKey.HelpContents)
help_action.triggered.connect(self.show_help)
```

---

### Gestalt Principles of Visual Perception

#### 1.11 Proximity
**Principle**: Group related items together.

**Application**:
- Group camera controls together
- Separate thermal analysis from fusion controls
- Keep ROI management tools in one panel
- Space unrelated groups apart

**PyQt Implementation**:
```python
# Use QGroupBox for related controls
camera_group = QGroupBox("Camera Settings")
camera_layout = QVBoxLayout()
camera_layout.addWidget(exposure_control)
camera_layout.addWidget(gain_control)
camera_layout.addWidget(white_balance)
camera_group.setLayout(camera_layout)

# Add spacing between groups
main_layout.addWidget(camera_group)
main_layout.addSpacing(16)  # Visual separation
main_layout.addWidget(thermal_group)
```

#### 1.12 Similarity
**Principle**: Similar elements are perceived as related.

**Application**:
- Use consistent button styles for primary actions
- Same icon style throughout (line icons or filled icons, not mixed)
- Uniform slider appearance
- Consistent color coding (green=active, red=inactive, blue=info)

#### 1.13 Continuity
**Principle**: Arrange elements in smooth lines or curves.

**Application**:
- Align controls vertically or horizontally (don't stagger)
- Use grid layouts for uniform spacing
- Keep labels aligned with their controls
- Maintain consistent margins

#### 1.14 Closure
**Principle**: Complete incomplete shapes mentally.

**Application**:
- Use borders or backgrounds to define sections
- Subtle shadows to create depth
- Visual hierarchy through spacing

---

### Visual Hierarchy

#### 1.15 Size and Scale
- **Large elements** = High importance (main display, critical alerts)
- **Medium elements** = Normal controls (buttons, sliders)
- **Small elements** = Secondary info (labels, status text)

**Application**:
```python
# Primary display (largest)
self.main_display = QLabel()
self.main_display.setMinimumSize(800, 600)

# Control buttons (medium)
self.capture_btn = QPushButton("Capture")
self.capture_btn.setFixedHeight(32)

# Status text (small)
self.status_text = QLabel("Ready")
self.status_text.setStyleSheet("font-size: 9pt; color: #666;")
```

#### 1.16 Color and Contrast
- **High contrast** = Important actions or warnings
- **Low contrast** = Disabled or secondary elements
- **Color coding** = Status indication (red=error, yellow=warning, green=ok)

#### 1.17 Position and Alignment
- **Top/Left** = Primary navigation
- **Center** = Main content/display
- **Right** = Controls and options
- **Bottom** = Status and secondary info

---

## 2. PyQt6-Specific Best Practices

### 2.1 Layout Management

**Principle**: Use layouts, never absolute positioning.

```python
# Good - Flexible, responsive layout
layout = QVBoxLayout()
layout.addWidget(title_label)
layout.addWidget(content)
layout.addStretch()  # Push content to top
self.setLayout(layout)

# Bad - Brittle, doesn't resize
title_label.move(10, 10)  # DON'T DO THIS
content.move(10, 50)
```

**Layout Types**:
- `QVBoxLayout` - Vertical stacking (most common for panels)
- `QHBoxLayout` - Horizontal arrangement (toolbars, button groups)
- `QGridLayout` - Rows and columns (forms, structured data)
- `QFormLayout` - Label-control pairs (settings dialogs)
- `QSplitter` - Resizable dividers (main app layout)

**Best Practices**:
```python
# Set margins consistently
layout.setContentsMargins(12, 12, 12, 12)  # Left, Top, Right, Bottom

# Set spacing between widgets
layout.setSpacing(8)

# Stretch factors for proportional sizing
main_layout = QHBoxLayout()
main_layout.addWidget(left_panel, 1)   # Takes 1 part
main_layout.addWidget(center_display, 3)  # Takes 3 parts (3x larger)
main_layout.addWidget(right_panel, 1)  # Takes 1 part

# Alignment within layouts
layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignRight)
```

### 2.2 Stylesheets (QSS)

**Principle**: Use stylesheets for consistent theming.

```python
# Application-wide theme
app = QApplication(sys.argv)
app.setStyleSheet("""
    QWidget {
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 10pt;
    }

    QGroupBox {
        font-weight: bold;
        border: 1px solid #ccc;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 8px;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }

    QPushButton {
        background-color: #0078d4;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        min-width: 80px;
    }

    QPushButton:hover {
        background-color: #106ebe;
    }

    QPushButton:pressed {
        background-color: #005a9e;
    }

    QPushButton:disabled {
        background-color: #ccc;
        color: #666;
    }

    QSlider::groove:horizontal {
        height: 6px;
        background: #ddd;
        border-radius: 3px;
    }

    QSlider::handle:horizontal {
        width: 16px;
        height: 16px;
        background: #0078d4;
        border-radius: 8px;
        margin: -5px 0;
    }

    QTabWidget::pane {
        border: 1px solid #ccc;
        border-radius: 4px;
    }

    QTabBar::tab {
        background: #f0f0f0;
        padding: 8px 16px;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
    }

    QTabBar::tab:selected {
        background: white;
        border-bottom: 2px solid #0078d4;
    }
""")
```

**Dark Theme Example**:
```python
DARK_THEME = """
    QWidget {
        background-color: #2b2b2b;
        color: #e0e0e0;
    }

    QGroupBox {
        border: 1px solid #444;
        color: #e0e0e0;
    }

    QPushButton {
        background-color: #0078d4;
        color: white;
    }

    QPushButton:hover {
        background-color: #1084d8;
    }

    QLineEdit, QSpinBox, QComboBox {
        background-color: #3a3a3a;
        border: 1px solid #555;
        color: #e0e0e0;
        padding: 4px;
    }
"""
```

### 2.3 Signal-Slot Connections

**Best Practices**:
```python
# Connect signals explicitly
self.slider.valueChanged.connect(self.on_slider_changed)

# Use lambda for parameters
self.button.clicked.connect(lambda: self.process(mode="fast"))

# Disconnect when needed
self.slider.valueChanged.disconnect()

# Block signals temporarily
self.slider.blockSignals(True)
self.slider.setValue(50)  # Won't trigger valueChanged
self.slider.blockSignals(False)
```

### 2.4 Thread Safety

**Principle**: Update GUI only from main thread.

```python
from PyQt6.QtCore import QThread, pyqtSignal

class ProcessingThread(QThread):
    progress_signal = pyqtSignal(int)
    result_signal = pyqtSignal(object)

    def run(self):
        for i in range(100):
            # Do work
            self.progress_signal.emit(i)

        result = self.compute_result()
        self.result_signal.emit(result)

# In main GUI class
self.thread = ProcessingThread()
self.thread.progress_signal.connect(self.update_progress)
self.thread.result_signal.connect(self.display_result)
self.thread.start()
```

### 2.5 Custom Widgets

**Create reusable components**:
```python
class ThermalDisplay(QWidget):
    """Custom widget for displaying thermal frames with overlays"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame = None
        self.rois = []
        self.setMinimumSize(640, 480)

    def set_frame(self, frame):
        self.frame = frame
        self.update()  # Trigger repaint

    def paintEvent(self, event):
        if self.frame is None:
            return

        painter = QPainter(self)
        painter.drawImage(0, 0, self.frame)

        # Draw ROIs
        painter.setPen(QPen(QColor(0, 255, 0), 2))
        for roi in self.rois:
            painter.drawRect(roi)
```

---

## 3. Professional/Industrial Application Design

### 3.1 Layout Patterns

#### Three-Panel Layout (Recommended for Thermal Inspection)
```
┌─────────────┬───────────────────────┬─────────────┐
│             │                       │             │
│    Left     │     Main Display      │    Right    │
│   Control   │     (Thermal/RGB/     │   Analysis  │
│    Panel    │      Fusion View)     │    Panel    │
│             │                       │             │
├─────────────┴───────────────────────┴─────────────┤
│                  Status Bar                        │
└────────────────────────────────────────────────────┘
```

**Implementation**:
```python
main_layout = QHBoxLayout()

# Left panel (300px)
left_panel = QWidget()
left_panel.setMaximumWidth(300)
left_panel_layout = QVBoxLayout()
# Add controls...
left_panel.setLayout(left_panel_layout)

# Center display (flexible)
display_widget = ThermalDisplay()

# Right panel (300px)
right_panel = QWidget()
right_panel.setMaximumWidth(300)
right_panel_layout = QVBoxLayout()
# Add analysis...
right_panel.setLayout(right_panel_layout)

main_layout.addWidget(left_panel, 0)
main_layout.addWidget(display_widget, 1)  # Takes remaining space
main_layout.addWidget(right_panel, 0)
```

### 3.2 Tab Organization

**Principle**: Group related functions in tabs.

```python
tab_widget = QTabWidget()
tab_widget.addTab(camera_settings_panel, "⚙️ Camera")
tab_widget.addTab(thermal_analysis_panel, "🌡️ Analysis")
tab_widget.addTab(roi_manager_panel, "🎯 ROIs")
tab_widget.addTab(recording_panel, "📹 Recording")
```

### 3.3 Toolbar Design

```python
toolbar = QToolBar("Main Toolbar")
toolbar.setIconSize(QSize(24, 24))
toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)

# Add actions
toolbar.addAction(QIcon("icons/camera.png"), "Connect", self.connect_camera)
toolbar.addAction(QIcon("icons/record.png"), "Record", self.toggle_record)
toolbar.addAction(QIcon("icons/snapshot.png"), "Snapshot", self.capture_snapshot)
toolbar.addSeparator()
toolbar.addAction(QIcon("icons/roi.png"), "Add ROI", self.add_roi)
```

### 3.4 Status Bar

```python
status_bar = QStatusBar()

# Permanent widgets (always visible)
fps_label = QLabel("FPS: 0.0")
status_bar.addPermanentWidget(fps_label)

camera_status = QLabel("⚫ Disconnected")
status_bar.addPermanentWidget(camera_status)

# Temporary messages
status_bar.showMessage("Frame captured successfully", 3000)  # 3 seconds
```

---

## 4. Data Visualization for Thermal Imaging

### 4.1 Thermal Palette Selection

**Guidelines**:
- **White Hot**: General purpose, highest contrast
- **Ironbow**: Circuit board inspection, wide dynamic range
- **Rainbow**: General analysis, easy to spot gradients
- **Medical (Viridis)**: Perceptually uniform, colorblind-friendly

**Implementation**:
```python
class PaletteSelector(QComboBox):
    def __init__(self):
        super().__init__()

        # Add palettes with visual previews
        for palette in PaletteType:
            icon = self.create_palette_preview(palette)
            self.addItem(icon, palette.name, palette)

    def create_palette_preview(self, palette):
        """Generate gradient preview icon"""
        pixmap = QPixmap(100, 16)
        painter = QPainter(pixmap)

        gradient = QLinearGradient(0, 0, 100, 0)
        colors = self.get_palette_colors(palette)
        for i, color in enumerate(colors):
            gradient.setColorAt(i / len(colors), QColor(*color))

        painter.fillRect(0, 0, 100, 16, gradient)
        painter.end()

        return QIcon(pixmap)
```

### 4.2 Temperature Scale Display

```python
class TemperatureScale(QWidget):
    """Vertical temperature scale with gradient and labels"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self.min_temp = 20.0
        self.max_temp = 100.0
        self.palette = PaletteType.IRONBOW

    def paintEvent(self, event):
        painter = QPainter(self)

        # Draw gradient bar
        gradient = QLinearGradient(0, 0, 0, self.height())
        colors = self.get_palette_colors()
        for i, color in enumerate(colors):
            gradient.setColorAt(i / len(colors), QColor(*color))

        painter.fillRect(10, 10, 20, self.height() - 20, gradient)

        # Draw temperature labels
        painter.setPen(QColor(0, 0, 0))
        font = QFont("Arial", 9)
        painter.setFont(font)

        for i in range(5):
            y = 10 + (self.height() - 20) * (i / 4)
            temp = self.max_temp - (self.max_temp - self.min_temp) * (i / 4)
            painter.drawText(35, y + 5, f"{temp:.1f}°C")
```

### 4.3 ROI Visualization

**Best Practices**:
```python
# Use distinct colors for different ROI types
ROI_COLORS = {
    'hot_spot': QColor(255, 0, 0, 180),      # Red, semi-transparent
    'cold_spot': QColor(0, 0, 255, 180),     # Blue
    'manual': QColor(0, 255, 0, 180),        # Green
    'gradient': QColor(255, 165, 0, 180)     # Orange
}

# Draw with anti-aliasing
painter.setRenderHint(QPainter.RenderHint.Antialiasing)

# Draw filled ROI with border
painter.setBrush(QBrush(ROI_COLORS[roi.type]))
painter.setPen(QPen(Qt.GlobalColor.white, 2))
painter.drawRect(roi.bounds)

# Add label
painter.setPen(QPen(Qt.GlobalColor.white))
painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
painter.drawText(roi.bounds.topLeft(), roi.label)
```

### 4.4 Temperature Graphs

```python
# Use matplotlib or pyqtgraph for real-time plots
from pyqtgraph import PlotWidget

class TemperatureTrendGraph(PlotWidget):
    def __init__(self):
        super().__init__()
        self.setLabel('left', 'Temperature', '°C')
        self.setLabel('bottom', 'Time', 's')
        self.setBackground('w')

        self.plot_line = self.plot(pen='r', width=2)
        self.data_x = []
        self.data_y = []

    def add_point(self, time, temperature):
        self.data_x.append(time)
        self.data_y.append(temperature)

        # Keep last 100 points
        if len(self.data_x) > 100:
            self.data_x.pop(0)
            self.data_y.pop(0)

        self.plot_line.setData(self.data_x, self.data_y)
```

---

## 5. Color Theory for Technical Applications

### 5.1 Color Palette for Industrial GUI

**Primary Colors**:
```python
PRIMARY = {
    'blue': '#0078d4',      # Main actions, links
    'green': '#107c10',     # Success, active status
    'red': '#d13438',       # Errors, warnings
    'orange': '#ff8c00',    # Attention, caution
    'gray': '#5a5a5a'       # Disabled, secondary
}

BACKGROUND = {
    'light': '#ffffff',
    'panel': '#f3f3f3',
    'dark': '#2b2b2b',
    'dark_panel': '#3a3a3a'
}

TEXT = {
    'primary': '#1a1a1a',
    'secondary': '#5a5a5a',
    'disabled': '#999999',
    'dark_primary': '#e0e0e0',
    'dark_secondary': '#a0a0a0'
}
```

### 5.2 Semantic Color Usage

```python
# Status colors
STATUS_COLORS = {
    'connected': '#0a0',
    'disconnected': '#666',
    'warning': '#fa0',
    'error': '#d00',
    'processing': '#00a'
}

# Apply to widgets
def set_status(label, status):
    label.setText(status['text'])
    label.setStyleSheet(f"color: {STATUS_COLORS[status['level']]};")
```

### 5.3 Contrast Ratios (WCAG Guidelines)

- **Normal text**: Minimum 4.5:1 contrast ratio
- **Large text (14pt+ bold)**: Minimum 3:1
- **Interactive elements**: Minimum 3:1

**Check contrast**:
```python
def check_contrast(fg_color, bg_color):
    """Calculate contrast ratio (WCAG 2.1)"""
    def luminance(color):
        r, g, b = color.red(), color.green(), color.blue()
        r, g, b = [x / 255.0 for x in (r, g, b)]
        r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
        g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
        b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    l1 = luminance(fg_color)
    l2 = luminance(bg_color)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
```

---

## 6. Accessibility Guidelines

### 6.1 Keyboard Navigation

**Requirements**:
- All interactive elements must be keyboard accessible
- Clear focus indicators
- Logical tab order
- Keyboard shortcuts documented

**Implementation**:
```python
# Set tab order explicitly
self.setTabOrder(self.name_input, self.email_input)
self.setTabOrder(self.email_input, self.submit_button)

# Focus indicators in stylesheet
QPushButton:focus {
    border: 2px solid #0078d4;
    outline: none;
}

# Access keys (Alt+Letter)
self.save_button.setText("&Save")  # Alt+S
self.cancel_button.setText("&Cancel")  # Alt+C
```

### 6.2 Screen Reader Support

```python
# Set accessible names
self.slider.setAccessibleName("Temperature Threshold")
self.slider.setAccessibleDescription(
    "Set the temperature threshold for hot spot detection. "
    "Range: 20 to 500 degrees Celsius"
)
```

### 6.3 Color Blindness Considerations

**Guidelines**:
- Don't rely solely on color to convey information
- Use patterns, icons, or labels in addition to color
- Test with colorblind simulators

**Example**:
```python
# Bad - color only
self.status_label.setStyleSheet("color: red;")

# Good - icon + color + text
self.status_label.setText("❌ Error: Camera disconnected")
self.status_label.setStyleSheet("color: red;")
```

---

## 7. Layout and Spacing

### 7.1 8-Point Grid System

**Principle**: Use multiples of 8 for all spacing and sizing.

```python
SPACING = {
    'xs': 4,    # Tight spacing (within groups)
    'sm': 8,    # Default spacing
    'md': 16,   # Between sections
    'lg': 24,   # Between major components
    'xl': 32    # Page margins
}

# Apply consistently
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(8)
```

### 7.2 Golden Ratio

**Principle**: Use 1.618:1 ratio for pleasing proportions.

```python
# Main display area vs control panel
main_display_width = 1000
control_panel_width = int(main_display_width / 1.618)  # ~618px
```

### 7.3 Alignment

```python
# Left-align labels, right-align values
form_layout = QFormLayout()
form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
form_layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft)

# Center-align in containers
layout.addWidget(widget, alignment=Qt.AlignmentFlag.AlignCenter)
```

---

## 8. Typography and Readability

### 8.1 Font Selection

**Recommended Fonts**:
- **Windows**: Segoe UI (system default)
- **macOS**: San Francisco
- **Linux**: Ubuntu, Roboto
- **Fallback**: Arial, sans-serif

```python
# Set application-wide font
app.setFont(QFont("Segoe UI", 10))

# Font hierarchy
FONTS = {
    'heading': QFont("Segoe UI", 14, QFont.Weight.Bold),
    'subheading': QFont("Segoe UI", 12, QFont.Weight.Bold),
    'body': QFont("Segoe UI", 10),
    'caption': QFont("Segoe UI", 9),
    'monospace': QFont("Consolas", 9)  # For numeric data
}
```

### 8.2 Font Sizes

```python
FONT_SIZES = {
    'title': 16,        # Main titles
    'heading': 14,      # Section headers
    'body': 10,         # Normal text
    'caption': 9,       # Secondary info
    'small': 8          # Fine print
}
```

### 8.3 Line Height and Spacing

```python
# Line spacing (1.4x font size is comfortable)
label = QLabel("Multi-line text\nwith proper spacing")
font = label.font()
metrics = QFontMetrics(font)
label.setFixedHeight(metrics.height() * 1.4 * 2)  # 2 lines
```

### 8.4 Text Formatting

**Guidelines**:
- Use **bold** for emphasis (sparingly)
- Use *italic* for technical terms (first use)
- Use monospace for numeric data
- Never use ALL CAPS for body text
- Never use underline (reserved for links)

---

## 9. Icons and Controls

### 9.1 Icon Guidelines

**Principles**:
- **Consistent style**: All line icons OR all filled icons
- **Appropriate size**: 16px (small), 24px (standard), 32px (large)
- **Clear at size**: Recognizable without labels
- **Meaningful**: Universal symbols where possible

**Recommended Icon Sets**:
- Material Design Icons (open source)
- Font Awesome (free version)
- Feather Icons (minimal, clean)

```python
# Load icons with fallback
def load_icon(name, fallback_text=""):
    icon_path = f"icons/{name}.png"
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    else:
        # Create text-based fallback
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, fallback_text)
        painter.end()
        return QIcon(pixmap)
```

### 9.2 Button Design

**Types**:
```python
# Primary button (main action)
primary_btn = QPushButton("Save")
primary_btn.setStyleSheet("""
    QPushButton {
        background-color: #0078d4;
        color: white;
        border: none;
        padding: 8px 16px;
        font-weight: bold;
    }
    QPushButton:hover {
        background-color: #106ebe;
    }
""")

# Secondary button
secondary_btn = QPushButton("Cancel")
secondary_btn.setStyleSheet("""
    QPushButton {
        background-color: transparent;
        color: #0078d4;
        border: 1px solid #0078d4;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background-color: #f0f0f0;
    }
""")

# Danger button (destructive action)
danger_btn = QPushButton("Delete")
danger_btn.setStyleSheet("""
    QPushButton {
        background-color: #d13438;
        color: white;
        border: none;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background-color: #a82729;
    }
""")
```

### 9.3 Input Controls

**Best Practices**:
```python
# Spinbox with clear units
temperature_input = QSpinBox()
temperature_input.setRange(-40, 500)
temperature_input.setSuffix(" °C")
temperature_input.setStepType(QSpinBox.StepType.AdaptiveDecimalStepType)

# Slider with value label
slider_container = QWidget()
slider_layout = QHBoxLayout(slider_container)

slider = QSlider(Qt.Orientation.Horizontal)
slider.setRange(0, 100)

value_label = QLabel("50")
value_label.setMinimumWidth(30)

slider.valueChanged.connect(lambda v: value_label.setText(str(v)))

slider_layout.addWidget(QLabel("Threshold:"))
slider_layout.addWidget(slider)
slider_layout.addWidget(value_label)

# Checkbox with descriptive label
checkbox = QCheckBox("Enable automatic hot spot detection")
checkbox.setToolTip("Automatically detect and mark regions above threshold")

# Combo box with categories
combo = QComboBox()
combo.addItem("--- Thermal Palettes ---")
combo.insertSeparator(1)
combo.addItem("White Hot")
combo.addItem("Ironbow")
combo.addItem("Rainbow")
```

---

## 10. Error Handling and User Feedback

### 10.1 Progress Indication

```python
# For known duration
progress_dialog = QProgressDialog("Processing frames...", "Cancel", 0, 100, self)
progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)

for i in range(100):
    if progress_dialog.wasCanceled():
        break
    # Do work
    progress_dialog.setValue(i)

progress_dialog.close()

# For unknown duration
progress_bar = QProgressBar()
progress_bar.setRange(0, 0)  # Indeterminate mode
progress_bar.setFormat("Processing...")

# In status bar
self.status_bar.addWidget(progress_bar)

# When done
self.status_bar.removeWidget(progress_bar)
```

### 10.2 Toast Notifications

```python
class ToastNotification(QWidget):
    def __init__(self, message, duration=3000, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QHBoxLayout(self)
        label = QLabel(message)
        label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
            color: white;
            padding: 12px 20px;
            border-radius: 4px;
            font-size: 11pt;
        """)
        layout.addWidget(label)

        # Auto-hide after duration
        QTimer.singleShot(duration, self.close)

    def show_at_bottom(self):
        parent = self.parent()
        if parent:
            x = (parent.width() - self.width()) // 2
            y = parent.height() - self.height() - 50
            self.move(parent.mapToGlobal(QPoint(x, y)))
        self.show()

# Usage
toast = ToastNotification("Snapshot saved successfully!", parent=self)
toast.show_at_bottom()
```

### 10.3 Error Messages

**Hierarchy**:
1. **Critical**: Modal dialog, blocks interaction
2. **Warning**: Message box, can be dismissed
3. **Info**: Status bar or toast, auto-dismiss

```python
# Critical error
QMessageBox.critical(
    self,
    "Fatal Error",
    "Failed to initialize camera hardware.\n\n"
    "The application will now close.",
    QMessageBox.StandardButton.Ok
)
sys.exit(1)

# Warning
result = QMessageBox.warning(
    self,
    "Unsaved Changes",
    "You have unsaved ROIs. Save before closing?",
    QMessageBox.StandardButton.Save |
    QMessageBox.StandardButton.Discard |
    QMessageBox.StandardButton.Cancel,
    QMessageBox.StandardButton.Save
)

# Info
self.statusBar().showMessage("Frame rate adjusted to 30 FPS", 3000)
```

### 10.4 Input Validation

```python
class TemperatureInput(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Enter temperature (°C)")

        # Validator
        validator = QDoubleValidator(-40.0, 500.0, 1)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.setValidator(validator)

        # Visual feedback
        self.textChanged.connect(self.validate_input)

    def validate_input(self, text):
        if self.hasAcceptableInput():
            self.setStyleSheet("border: 1px solid green;")
        else:
            self.setStyleSheet("border: 1px solid red;")
```

---

## 11. Implementation Checklist

### Phase 1: Foundation (Week 1)
- [ ] Establish 8-point grid system
- [ ] Define color palette (light and dark themes)
- [ ] Create typography scale
- [ ] Set up application-wide stylesheet
- [ ] Implement layout structure (3-panel design)

### Phase 2: Component Polish (Week 2)
- [ ] Standardize button styles (primary, secondary, danger)
- [ ] Create consistent input controls
- [ ] Design and implement custom thermal display widget
- [ ] Add temperature scale visualization
- [ ] Implement ROI visualization with distinct colors

### Phase 3: Feedback Systems (Week 3)
- [ ] Add toast notifications
- [ ] Implement progress indicators
- [ ] Standardize error messages
- [ ] Add input validation with visual feedback
- [ ] Create status bar with permanent widgets

### Phase 4: Accessibility (Week 4)
- [ ] Add keyboard shortcuts (document in help)
- [ ] Ensure all controls are keyboard accessible
- [ ] Add focus indicators
- [ ] Set accessible names and descriptions
- [ ] Test with screen reader

### Phase 5: Final Polish (Week 5)
- [ ] Refine spacing and alignment
- [ ] Add icons to all actions
- [ ] Create help system with tooltips
- [ ] Implement theme switching
- [ ] Conduct usability testing
- [ ] Fix issues identified in testing

---

## Quick Reference: PyQt Stylesheet Properties

### Common Widget Properties
```css
QWidget {
    background-color: color;
    color: text-color;
    border: width style color;
    border-radius: px;
    padding: top right bottom left;
    margin: top right bottom left;
    font-family: name;
    font-size: pt/px;
    font-weight: normal/bold;
}

QPushButton {
    min-width: px;
    min-height: px;
}

QPushButton:hover { }
QPushButton:pressed { }
QPushButton:disabled { }
QPushButton:focus { }

QLineEdit, QSpinBox, QComboBox {
    border: 1px solid color;
    padding: px;
    selection-background-color: color;
}

QSlider::groove:horizontal {
    height: px;
    background: color;
}

QSlider::handle:horizontal {
    width: px;
    height: px;
    background: color;
    border-radius: px;
    margin: -px 0;
}

QGroupBox {
    border: width style color;
    border-radius: px;
    margin-top: px;
    padding-top: px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: px;
    padding: 0 px;
}

QTabWidget::pane {
    border: width style color;
}

QTabBar::tab {
    padding: px;
}

QTabBar::tab:selected {
    background: color;
}
```

---

## Recommended Resources

### Books
- "The Design of Everyday Things" by Don Norman
- "Don't Make Me Think" by Steve Krug
- "Designing Interface" by Jenifer Tidwell

### Online Resources
- Material Design Guidelines: https://material.io/design
- Human Interface Guidelines (Apple): https://developer.apple.com/design/
- Qt Documentation: https://doc.qt.io/qt-6/
- WCAG 2.1 Guidelines: https://www.w3.org/WAI/WCAG21/quickref/

### Tools
- Qt Designer - Visual UI designer
- Qt Style Sheets Editor - Test stylesheets
- ColorOracle - Colorblind simulator
- Contrast Checker - WCAG contrast ratio tool

---

## Document Metadata

**Version**: 1.0
**Date**: 2025-11-25
**Author**: Claude (Anthropic)
**Status**: Complete - Ready for Implementation
**Applies To**: Thermal Inspection Fusion Tool v2.8+
