# Qt GUI Architecture - Jetson-Optimized Design

**Implementation Status**: ⚠️ PHASE 1 COMPLETE - Uses processEvents() (needs refactoring)
**See**: QT_GUI_REFACTORING_NEEDED.md for current limitations and improvement plan

## Rationale for Qt Transition

**OpenCV Limitations Confirmed**:
1. ✅ Button jitter: Canvas calculations perfect but GTK backend causes rendering jitter
2. ✅ Text rendering: Multi "????????" outside text boxes (encoding/scaling issues)
3. ✅ Theming ineffective: Minimal visual difference between light/dark
4. ✅ 60 FPS performance but poor visual quality

**Qt Benefits**:
- Native platform rendering (no GTK backend issues)
- Proper font rendering with Unicode support
- Professional theming with QSS (CSS-like styling)
- Hardware-accelerated OpenGL rendering
- Better touch support for future tablet deployment

## Performance Optimization for Jetson

### 1. Memory Management
```python
# Efficient frame buffer reuse
class VideoWidget(QLabel):
    def __init__(self):
        super().__init__()
        self._frame_buffer = None  # Reuse buffer
        self._qimage_buffer = None  # Reuse QImage

    def update_frame(self, frame: np.ndarray):
        # Reuse existing buffers to avoid allocation overhead
        if self._frame_buffer is None or self._frame_buffer.shape != frame.shape:
            self._frame_buffer = np.empty_like(frame)

        np.copyto(self._frame_buffer, frame)
        # Convert to QImage...
```

**Benefit**: Eliminates per-frame allocations, critical for Jetson memory bandwidth

### 2. Threading Architecture
```
Main Thread (Qt Event Loop)
├── UI Events (button clicks, etc.)
└── Frame Display (QLabel.setPixmap)

Background Thread (Video Processing)
├── Camera Capture
├── YOLO Detection (GPU)
├── Thermal Processing
└── Signal → Main Thread
```

**Benefit**: Keeps UI responsive, YOLO runs on GPU without blocking UI

### 3. Hardware Acceleration Options

**Option A: QLabel with QPixmap (Simple)**
- CPU-based rendering
- Works everywhere (fallback)
- ~30-60 FPS depending on resolution

**Option B: QOpenGLWidget (Jetson Optimized)**
- GPU-accelerated texture upload
- OpenGL ES 3.2 support on Jetson
- ~60 FPS even at 1080p

**Recommendation**: Start with QLabel (Option A), add OpenGL later if needed

### 4. Frame Rate Management
```python
class DriverApp(QMainWindow):
    def __init__(self):
        self.target_fps = 30  # Cap at 30 FPS for Jetson
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self.update_display)
        self.frame_timer.start(1000 // self.target_fps)  # 33ms
```

**Benefit**: Prevents Qt event loop from being overwhelmed on slower hardware

## Architecture Design

### File Structure
```
driver_gui_qt.py       # Qt GUI implementation (replaces driver_gui.py)
├── VideoWidget        # Video display (QLabel or QOpenGLWidget)
├── ControlPanel       # Button controls (QWidget with QPushButton)
├── InfoPanel          # Metrics overlay (QWidget)
└── DriverAppWindow    # Main window (QMainWindow)

main.py                # Minimal changes (swap GUI backend)
└── from driver_gui_qt import DriverAppWindow
```

### Widget Hierarchy
```
QMainWindow (DriverAppWindow)
├── QWidget (CentralWidget)
│   ├── QVBoxLayout
│   │   ├── VideoWidget (QLabel) - 90% height
│   │   └── ControlPanel (QWidget) - 10% height
│   │       ├── QHBoxLayout
│   │       │   ├── QPushButton (View Mode)
│   │       │   ├── QPushButton (YOLO Toggle)
│   │       │   ├── QPushButton (Audio)
│   │       │   └── QPushButton (Theme)
│   └── InfoPanel (Overlay) - Floating, semi-transparent
```

### Styling with QSS
```python
# Dark theme (professional)
DARK_THEME = """
QPushButton {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border: 2px solid #404040;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 14px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #3d3d3d;
    border: 2px solid #00aaff;
}

QPushButton:pressed {
    background-color: #1d1d1d;
}

QPushButton:checked {
    background-color: #00aaff;
    border: 2px solid #00ddff;
}
"""

# Light theme
LIGHT_THEME = """
QPushButton {
    background-color: #f0f0f0;
    color: #202020;
    border: 2px solid #c0c0c0;
    border-radius: 8px;
    padding: 10px 20px;
}
"""
```

**Benefit**: Clear visual distinction between themes, professional appearance

### Signal/Slot Design (Thread-Safe)
```python
class VideoThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)  # Signal emits frame
    fps_update = pyqtSignal(float)        # Signal emits FPS
    detection_result = pyqtSignal(list)   # Signal emits detections

    def run(self):
        while self.running:
            frame = self.capture_frame()
            self.frame_ready.emit(frame)  # Thread-safe emit

class DriverAppWindow(QMainWindow):
    def __init__(self):
        self.video_thread = VideoThread()
        self.video_thread.frame_ready.connect(self.update_video)  # Connect

    def update_video(self, frame: np.ndarray):
        # Runs in main thread (GUI thread) - safe to update UI
        self.video_widget.update_frame(frame)
```

**Benefit**: Thread-safe communication without locks, Qt handles synchronization

## Implementation Plan

### Phase 1: Minimal Qt GUI (1-2 hours)
**Goal**: Get video displaying in Qt window with basic controls

```python
# driver_gui_qt.py (Phase 1)
class VideoWidget(QLabel):
    def update_frame(self, frame: np.ndarray):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.setPixmap(pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

class ControlPanel(QWidget):
    def __init__(self):
        layout = QHBoxLayout()
        layout.addWidget(QPushButton("View Mode"))
        layout.addWidget(QPushButton("YOLO Toggle"))
        layout.addWidget(QPushButton("Theme"))
        self.setLayout(layout)

class DriverAppWindow(QMainWindow):
    def __init__(self):
        self.video_widget = VideoWidget()
        self.control_panel = ControlPanel()

        central = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.video_widget, stretch=9)
        layout.addWidget(self.control_panel, stretch=1)
        central.setLayout(layout)
        self.setCentralWidget(central)
```

**Deliverable**: Video displays, buttons visible (not functional yet)

### Phase 2: Wire Up Controls (1 hour)
**Goal**: Connect button clicks to application logic

```python
class ControlPanel(QWidget):
    view_mode_clicked = pyqtSignal()
    yolo_toggled = pyqtSignal(bool)
    theme_toggled = pyqtSignal()

    def __init__(self):
        self.yolo_btn = QPushButton("YOLO: OFF")
        self.yolo_btn.setCheckable(True)
        self.yolo_btn.toggled.connect(self.yolo_toggled.emit)
        # ... connect signals
```

**Deliverable**: All buttons functional

### Phase 3: Add Theming (30 min)
**Goal**: Professional light/dark themes

```python
class DriverAppWindow(QMainWindow):
    def apply_theme(self, theme_name: str):
        if theme_name == 'dark':
            self.setStyleSheet(DARK_THEME)
        else:
            self.setStyleSheet(LIGHT_THEME)
```

**Deliverable**: Beautiful, distinct themes

### Phase 4: Info Panel Overlay (1 hour)
**Goal**: FPS, detection count, connection status

```python
class InfoPanel(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        # Semi-transparent overlay
```

**Deliverable**: Complete feature parity with OpenCV GUI

## Performance Benchmarks (Expected)

### ThinkPad (x86-64, Integrated GPU)
- **OpenCV GUI**: 60 FPS, jittery buttons, poor theming
- **Qt GUI**: 60 FPS, smooth, professional

### Jetson Orin (ARM64, 1024 CUDA cores)
- **Target**: 30 FPS display, YOLO at 15-30 FPS
- **Memory**: <500MB additional overhead from Qt
- **GPU Load**: 40-60% (YOLO dominates, not Qt rendering)

## Fallback Strategy

If Qt performance is insufficient on Jetson:
1. Reduce display resolution (e.g., 720p instead of 1080p)
2. Cap frame rate at 20 FPS
3. Use QOpenGLWidget for hardware acceleration
4. Disable smooth scaling (Qt.FastTransformation)

## Migration Path

**Backward Compatibility**:
```python
# main.py
if args.use_opencv_gui:
    from driver_gui import DriverGUI
    gui = DriverGUI()
else:
    from driver_gui_qt import DriverAppWindow
    gui = DriverAppWindow()
```

**Benefit**: Can A/B test both GUIs, revert if issues

## Dependencies

```bash
# For PyQt5 (lighter, more compatible with Jetson)
pip3 install PyQt5

# OR for PySide6 (official Qt bindings, better licensing)
pip3 install PySide6
```

**Recommendation**: Start with PyQt5 (more examples/documentation), switch to PySide6 if licensing matters

---

**Next Steps**:
1. ✅ Fix NoneType detector error
2. ⏳ Implement Phase 1 (Minimal Qt GUI)
3. ⏳ Test on ThinkPad
4. ⏳ Implement Phases 2-4
5. ⏳ Test on Jetson (if available)
