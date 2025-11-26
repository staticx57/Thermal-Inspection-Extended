# Spinnaker/Firefly Camera Integration Plan

Full integration of FLIR Firefly global shutter camera capabilities into the Thermal Inspection application.

## Executive Summary

This document outlines the integration of advanced FLIR Firefly camera features via the Spinnaker SDK (PySpin), transforming the application's RGB camera capabilities from basic UVC webcam functionality to professional machine vision grade imaging. The Firefly camera provides global shutter technology, precise exposure control, and advanced trigger modes essential for high-quality thermal fusion and inspection workflows.

---

## Firefly Camera Capabilities

### Hardware Advantages

**Global Shutter Technology**
- ✅ **Zero motion blur** even during fast movement
- ✅ **Precise frame timing** for multi-camera synchronization
- ✅ **Distortion-free** geometry for accurate thermal fusion
- ✅ **Superior for moving subjects** (automotive, robotics)

**Sony IMX Sensors**
- High quantum efficiency
- Low noise characteristics
- Excellent dynamic range
- Color accuracy

### Current vs. Enhanced Capabilities

| Feature | Current (UVC Webcam) | Enhanced (Firefly) |
|---------|---------------------|-------------------|
| **Shutter Type** | Rolling (motion blur) | Global (no blur) ✨ |
| **Exposure Control** | Basic auto | Precise manual + auto |
| **Gain Control** | Limited | Full range 0-18 dB |
| **Trigger Modes** | None | Software + Hardware |
| **White Balance** | Basic auto | Advanced + manual |
| **ROI** | Software only | Hardware accelerated |
| **Frame Sync** | Unreliable | Precise triggering |
| **Bit Depth** | 8-bit | 8/10/12-bit capable |

---

## PySpin SDK Feature Overview

### 1. Exposure Control

**Modes:**
- `Off` - Manual exposure time
- `Once` - Single automatic adjustment
- `Continuous` - Continuous auto exposure (default)

**Parameters:**
- `ExposureTime` (µs) - Direct exposure control
- `ExposureAuto` - Auto mode selection
- `AutoExposureTargetValue` - Target brightness (0-255)
- `AutoExposureLightingMode` - Normal/Backlight/Frontlight

**Use Cases:**
- **Thermal Fusion:** Fixed exposure prevents brightness flickering between frames
- **Outdoor Inspection:** Backlight compensation for strong sun
- **Fast Motion:** Short exposure (100-500µs) freezes movement

### 2. Gain Control

**Modes:**
- `Off` - Manual gain
- `Once` - Single auto adjustment  
- `Continuous` - Continuous auto gain

**Parameters:**
- `Gain` (dB) - 0 to ~18 dB typical range
- `GainAuto` - Auto mode selection
- `AutoGainLowerLimit` / `AutoGainUpperLimit` - Constrain auto range

**Use Cases:**
- **Low Light:** Increase gain for dark environments
- **Bright Scenes:** Reduce gain to prevent overexposure
- **Thermal Overlay:** Match RGB brightness to thermal intensity range

### 3. White Balance

**Modes:**
- `Off` - Manual white balance ratios
- `Once` - Single calibration (on white surface)
- `Continuous` - Continuous auto white balance

**Parameters:**
- `BalanceWhiteAuto` - Auto mode selection
- `BalanceRatioSelector` - Red/Blue channel selection
- `BalanceRatio` - Individual channel multiplier

**Use Cases:**
- **Indoor Fluorescent:** Correct green tint
- **Incandescent Lighting:** Reduce warm orange cast
- **Outdoor Daylight:** True color reproduction
- **Thermal Visualization:** Neutral colors for fusion overlay

### 4. Trigger Modes

**Software Trigger:**
```python
# Enable trigger mode
trigger_mode = 'On'
trigger_source = 'Software'

# Later: fire trigger
execute_software_trigger()
```

**Hardware Trigger:**
```python
# Trigger on GPIO line
trigger_source = 'Line0'  # Physical GPIO pin
trigger_activation = 'RisingEdge'  # or FallingEdge, LevelHigh, LevelLow
```

**Trigger Selectors:**
- `FrameStart` - Trigger individual frames
- `AcquisitionStart` - Trigger acquisition sequence

**Use Cases:**
- **Multi-Camera Sync:** Synchronized RGB + Thermal capture
- **Strobe Lighting:** Trigger camera with flash pulse
- **External Events:** Capture on limit switch/sensor trigger
- **Periodic Capture:** Software trigger at precise intervals

### 5. Region of Interest (ROI)

**Hardware ROI:**
- `Width` / `Height` - Sensor readout region
- `OffsetX` / `OffsetY` - ROI position on sensor
- **Benefits:** Increased frame rate, reduced bandwidth

**Use Cases:**
- **Zoom Imaging:** Readout only center portion at higher FPS
- **Defect Inspection:** Focus on board area of interest
- **Thermal Alignment:** Match RGB ROI to thermal sensor FOV

### 6. Image Format & Bit Depth

**Pixel Formats:**
- `BGR8` / `RGB8` - Standard 8-bit color (OpenCV compatible)
- `Mono8` / `Mono12` / `Mono16` - Grayscale imaging
- `BayerRG8` / `BayerRG12` - Raw Bayer for custom debayering

**Use Cases:**
- **Standard Fusion:** BGR8 for thermal overlay
- **High Precision:** Mono12/16 for detailed analysis
- **Custom Processing:** Raw Bayer with optimized algorithms

### 7. Advanced Features

**Gamma Correction:**
- Non-linear response for human perception
- Adjustable gamma value (0.5 - 4.0 typical)

**Sharpness:**
- Hardware-based edge enhancement
- Adjustable intensity

**LUT (Lookup Table):**
- Custom pixel value remapping
- Contrast enhancement

**Sequencer Mode:**
- Multi-state capture sequences
- Different settings per frame

---

## GUI Panel Design

### FireflyControlPanel Layout

```
╔═══════════════════════════════════════════════╗
║  🎥 FLIR Firefly Camera Control              ║
╠═══════════════════════════════════════════════╣
║  Camera Status                                ║
║  ○ Connected: Firefly BFLY-U3-23S6M-C        ║
║  ○ Serial: 18251234                           ║
║  ○ Resolution: 1920×1200 @ 60 FPS             ║
║  ○ Pixel Format: BGR8                         ║
╠═══════════════════════════════════════════════╣
║  📊 Exposure Control                          ║
║  ┌─────────────────────────────────────────┐  ║
║  │ Mode: ● Auto  ○ Manual                  │  ║
║  │ Time: [░░░░░░░░░░] 5000 µs             │  ║
║  │ Range: 100 - 30000 µs                   │  ║
║  │ Target Brightness: [░░░░] 128 / 255    │  ║
║  └─────────────────────────────────────────┘  ║
╠═══════════════════════════════════════════════╣
║  🔆 Gain Control                              ║
║  ┌─────────────────────────────────────────┐  ║
║  │ Mode: ● Auto  ○ Manual                  │  ║
║  │ Gain: [░░░░░░░░░░] 6.0 dB              │  ║
║  │ Range: 0.0 - 18.0 dB                    │  ║
║  └─────────────────────────────────────────┘  ║
╠═══════════════════════════════════════════════╣
║  🎨 White Balance                             ║
║  ┌─────────────────────────────────────────┐  ║
║  │ Mode: ● Auto  ○ Manual                  │  ║
║  │ Red Ratio:  [░░░░░░] 1.25              │  ║
║  │ Blue Ratio: [░░░░░░] 1.85              │  ║
║  │  [Calibrate on White]                   │  ║
║  └─────────────────────────────────────────┘  ║
╠═══════════════════════════════════════════════╣
║  ⚡ Trigger Configuration                     ║
║  ┌─────────────────────────────────────────┐  ║
║  │ Mode: ○ Free Run  ○ Software  ○ GPIO   │  ║
║  │ Source: [Line0 ▼]                       │  ║
║  │ Activation: [Rising Edge ▼]             │  ║
║  │  [🎯 Fire Software Trigger]             │  ║
║  └─────────────────────────────────────────┘  ║
╠═══════════════════════════════════════════════╣
║  🖼️ Image Settings                            ║
║  ┌─────────────────────────────────────────┐  ║
║  │ Gamma: [░░░░░░░░] 1.0                  │  ║
║  │ Sharpness: [░░░░░░] 50%                │  ║
║  │ ☑ Auto Contrast                         │  ║
║  └─────────────────────────────────────────┘  ║
╠═══════════════════════════════════════════════╣
║   [💾 Save Preset]  [📂 Load Preset]        ║
║   [🔄 Reset to Defaults]                     ║
╚═══════════════════════════════════════════════╝
```

### Integration Points

**Location in GUI:**
- **Primary:** Settings tab alongside Boson SDK panel
- **Quick Access:** Pop-out floating panel
- **Status Bar:** Key parameters display (Exp: 5ms, Gain: 6dB, WB: Auto)

**Theme Support:**
- Inherit from existing Dark/Light/Solarized themes
- Consistent with BosonSDKPanel styling

---

## Implementation Plan

### Phase 1: Core Infrastructure

**Files to Modify:**

#### [rgb_camera_firefly.py](file:///c:/Users/stati/Desktop/Projects/Thermal-Inspection/rgb_camera_firefly.py)

Add control methods to `RGBCameraFirefly` class:

```python
def set_exposure_mode(self, mode: str) -> bool:
    """
    Set exposure control mode
    
    Args:
        mode: 'Off', 'Once', or 'Continuous'
    """
    if not self.is_open or self.cam is None:
        return False
    
    try:
        nodemap = self.cam.GetNodeMap()
        node_exposure_auto = PySpin.CEnumerationPtr(nodemap.GetNode('ExposureAuto'))
        
        if PySpin.IsAvailable(node_exposure_auto) and PySpin.IsWritable(node_exposure_auto):
            mode_entry = node_exposure_auto.GetEntryByName(mode)
            if PySpin.IsAvailable(mode_entry) and PySpin.IsReadable(mode_entry):
                node_exposure_auto.SetIntValue(mode_entry.GetValue())
                logger.info(f'Exposure mode set to: {mode}')
                return True
        return False
    except PySpin.SpinnakerException as ex:
        logger.error(f'Error setting exposure mode: {ex}')
        return False

def set_exposure_time(self, time_us: float) -> bool:
    """
    Set manual exposure time in microseconds
    
    Args:
        time_us: Exposure time (e.g., 5000 = 5ms)
    """
    if not self.is_open or self.cam is None:
        return False
    
    try:
        # First set mode to manual
        self.set_exposure_mode('Off')
        
        nodemap = self.cam.GetNodeMap()
        node_exposure_time = PySpin.CFloatPtr(nodemap.GetNode('ExposureTime'))
        
        if PySpin.IsAvailable(node_exposure_time) and PySpin.IsWritable(node_exposure_time):
            # Clamp to valid range
            min_exp = node_exposure_time.GetMin()
            max_exp = node_exposure_time.GetMax()
            clamped_time = max(min_exp, min(time_us, max_exp))
            
            node_exposure_time.SetValue(clamped_time)
            logger.info(f'Exposure time set to: {clamped_time} µs')
            return True
        return False
    except PySpin.SpinnakerException as ex:
        logger.error(f'Error setting exposure time: {ex}')
        return False

def get_exposure_time(self) -> float:
    """Get current exposure time in microseconds"""
    return self.get_property('ExposureTime') or 0.0

def set_gain(self, gain_db: float) -> bool:
    """
    Set manual gain in decibels
    
    Args:
        gain_db: Gain value (0.0 - 18.0 dB typical)
    """
    if not self.is_open or self.cam is None:
        return False
    
    try:
        # First set mode to manual
        self.set_gain_mode('Off')
        
        nodemap = self.cam.GetNodeMap()
        node_gain = PySpin.CFloatPtr(nodemap.GetNode('Gain'))
        
        if PySpin.IsAvailable(node_gain) and PySpin.IsWritable(node_gain):
            min_gain = node_gain.GetMin()
            max_gain = node_gain.GetMax()
            clamped_gain = max(min_gain, min(gain_db, max_gain))
            
            node_gain.SetValue(clamped_gain)
            logger.info(f'Gain set to: {clamped_gain} dB')
            return True
        return False
    except PySpin.SpinnakerException as ex:
        logger.error(f'Error setting gain: {ex}')
        return False

def set_white_balance_mode(self, mode: str) -> bool:
    """Set white balance mode: 'Off', 'Once', 'Continuous'"""
    return self.set_property('BalanceWhiteAuto', mode)

def calibrate_white_balance(self) -> bool:
    """Perform one-shot white balance calibration"""
    return self.set_white_balance_mode('Once')

def set_trigger_mode(self, enabled: bool, source: str = 'Software') -> bool:
    """
    Configure trigger mode
    
    Args:
        enabled: True to enable triggering, False for free-run
        source: 'Software', 'Line0', 'Line1', etc.
    """
    if not self.is_open or self.cam is None:
        return False
    
    try:
        nodemap = self.cam.GetNodeMap()
        
        # Set trigger mode
        node_trigger_mode = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerMode'))
        if PySpin.IsAvailable(node_trigger_mode) and PySpin.IsWritable(node_trigger_mode):
            mode_value = 'On' if enabled else 'Off'
            mode_entry = node_trigger_mode.GetEntryByName(mode_value)
            if PySpin.IsAvailable(mode_entry):
                node_trigger_mode.SetIntValue(mode_entry.GetValue())
        
        if enabled:
            # Set trigger source
            node_trigger_source = PySpin.CEnumerationPtr(nodemap.GetNode('TriggerSource'))
            if PySpin.IsAvailable(node_trigger_source) and PySpin.IsWritable(node_trigger_source):
                source_entry = node_trigger_source.GetEntryByName(source)
                if PySpin.IsAvailable(source_entry):
                    node_trigger_source.SetIntValue(source_entry.GetValue())
        
        logger.info(f'Trigger mode: {enabled}, source: {source}')
        return True
    except PySpin.SpinnakerException as ex:
        logger.error(f'Error setting trigger mode: {ex}')
        return False

def execute_software_trigger(self) -> bool:
    """Fire software trigger to capture next frame"""
    if not self.is_open or self.cam is None:
        return False
    
    try:
        nodemap = self.cam.GetNodeMap()
        node_trigger_software = PySpin.CCommandPtr(nodemap.GetNode('TriggerSoftware'))
        
        if PySpin.IsAvailable(node_trigger_software) and PySpin.IsWritable(node_trigger_software):
            node_trigger_software.Execute()
            return True
        return False
    except PySpin.SpinnakerException as ex:
        logger.error(f'Error executing software trigger: {ex}')
        return False
```

### Phase 2: GUI Panel Implementation

**New File:** `firefly_control_panel.py`

```python
\"\"\"
Firefly Camera Control Panel for GUI
Professional control panel for FLIR Firefly advanced features
\"\"\"
from PySide6.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, 
    QSlider, QPushButton, QRadioButton, QComboBox,
    QCheckBox, QButtonGroup
)
from PySide6.QtCore import pyqtSignal, Qt

class FireflyControlPanel(QGroupBox):
    \"\"\"Advanced control panel for Firefly camera features\"\"\"
    
    # Signals
    exposure_mode_changed = pyqtSignal(str)  # 'Off', 'Once', 'Continuous'
    exposure_time_changed = pyqtSignal(float)  # microseconds
    gain_mode_changed = pyqtSignal(str)
    gain_changed = pyqtSignal(float)  # dB
    white_balance_mode_changed = pyqtSignal(str)
    white_balance_calibrate = pyqtSignal()
    trigger_mode_changed = pyqtSignal(bool, str)  # enabled, source
    trigger_fire = pyqtSignal()
    gamma_changed = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(\"🎥 Firefly Camera Control\", parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout()
        
        # === Camera Status Section ===
        self._create_status_section(layout)
        
        # === Exposure Control ===
        self._create_exposure_section(layout)
        
        # === Gain Control ===
        self._create_gain_section(layout)
        
        # === White Balance ===
        self._create_white_balance_section(layout)
        
        # === Trigger Configuration ===
        self._create_trigger_section(layout)
        
        # === Image Settings ===
        self._create_image_settings_section(layout)
        
        # === Preset Management ===
        preset_layout = QHBoxLayout()
        save_btn = QPushButton(\"💾 Save Preset\")
        load_btn = QPushButton(\"📂 Load Preset\")
        reset_btn = QPushButton(\"🔄 Reset Defaults\")
        preset_layout.addWidget(save_btn)
        preset_layout.addWidget(load_btn)
        preset_layout.addWidget(reset_btn)
        layout.addLayout(preset_layout)
        
        self.setLayout(layout)
    
    def _create_exposure_section(self, parent_layout):
        \"\"\"Create exposure control widgets\"\"\"
        group = QGroupBox(\"📊 Exposure Control\")
        layout = QVBoxLayout()
        
        # Mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel(\"Mode:\"))
        
        self.exp_mode_group = QButtonGroup()
        self.exp_auto_radio = QRadioButton(\"Auto\")
        self.exp_manual_radio = QRadioButton(\"Manual\")
        self.exp_auto_radio.setChecked(True)
        
        self.exp_mode_group.addButton(self.exp_auto_radio, 0)
        self.exp_mode_group.addButton(self.exp_manual_radio, 1)
        
        mode_layout.addWidget(self.exp_auto_radio)
        mode_layout.addWidget(self.exp_manual_radio)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # Exposure time slider
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel(\"Time:\"))
        
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setMinimum(100)  # 100 µs
        self.exposure_slider.setMaximum(30000)  # 30 ms
        self.exposure_slider.setValue(5000)  # 5 ms default
        self.exposure_slider.setEnabled(False)  # Disabled in auto mode
        
        self.exposure_label = QLabel(\"5000 µs\")
        self.exposure_label.setMinimumWidth(80)
        
        time_layout.addWidget(self.exposure_slider)
        time_layout.addWidget(self.exposure_label)
        layout.addLayout(time_layout)
        
        # Connect signals
        self.exp_auto_radio.toggled.connect(self._on_exposure_mode_changed)
        self.exposure_slider.valueChanged.connect(self._on_exposure_time_changed)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _on_exposure_mode_changed(self, checked):
        \"\"\"Handle exposure mode change\"\"\"
        if checked:  # Auto mode
            self.exposure_slider.setEnabled(False)
            self.exposure_mode_changed.emit('Continuous')
        else:  # Manual mode
            self.exposure_slider.setEnabled(True)
            self.exposure_mode_changed.emit('Off')
            # Also emit current time value
            self.exposure_time_changed.emit(self.exposure_slider.value())
    
    def _on_exposure_time_changed(self, value):
        \"\"\"Handle exposure time slider change\"\"\"
        self.exposure_label.setText(f\"{value} µs\")
        if self.exp_manual_radio.isChecked():
            self.exposure_time_changed.emit(float(value))
    
    # Similar implementations for gain, white balance, trigger sections...
```

### Phase 3: Main Application Integration

**Modify:** [`inspection_gui_qt.py`](file:///c:/Users/stati/Desktop/Projects/Thermal-Inspection/inspection_gui_qt.py)

```python
from firefly_control_panel import FireflyControlPanel

class InspectionAppWindow(QMainWindow):
    def __init__(self):
        # ... existing code ...
        
        # Add Firefly panel to settings tabs
        self.firefly_panel = FireflyControlPanel()
        self.settings_tabs.addTab(self.firefly_panel, \"Firefly Camera\")
        
        # Connect Firefly panel signals to handlers
        self._connect_firefly_signals()
    
    def _connect_firefly_signals(self):
        \"\"\"Connect Firefly control panel signals\"\"\"
        self.firefly_panel.exposure_mode_changed.connect(self._on_firefly_exposure_mode)
        self.firefly_panel.exposure_time_changed.connect(self._on_firefly_exposure_time)
        self.firefly_panel.gain_mode_changed.connect(self._on_firefly_gain_mode)
        self.firefly_panel.gain_changed.connect(self._on_firefly_gain)
        self.firefly_panel.white_balance_mode_changed.connect(self._on_firefly_wb_mode)
        self.firefly_panel.white_balance_calibrate.connect(self._on_firefly_wb_calibrate)
        self.firefly_panel.trigger_mode_changed.connect(self._on_firefly_trigger_mode)
        self.firefly_panel.trigger_fire.connect(self._on_firefly_trigger_fire)
    
    def _on_firefly_exposure_mode(self, mode: str):
        \"\"\"Handle Firefly exposure mode change\"\"\"
        if self.app and hasattr(self.app.rgb_camera, 'set_exposure_mode'):
            self.app.rgb_camera.set_exposure_mode(mode)
    
    def _on_firefly_exposure_time(self, time_us: float):
        \"\"\"Handle Firefly exposure time change\"\"\"
        if self.app and hasattr(self.app.rgb_camera, 'set_exposure_time'):
            self.app.rgb_camera.set_exposure_time(time_us)
    
    # ... similar handlers for other controls ...
```

**Modify:** [`inspection_main.py`](file:///c:/Users/stati/Desktop/Projects/Thermal-Inspection/inspection_main.py)

```python
class ThermalInspectionFusion:
    # Add wrapper methods that the GUI can call
    
    def set_firefly_exposure_mode(self, mode: str):
        \"\"\"Set Firefly camera exposure mode\"\"\"
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_exposure_mode(mode)
        return False
    
    def set_firefly_exposure_time(self, time_us: float):
        \"\"\"Set Firefly camera exposure time\"\"\"
        if isinstance(self.rgb_camera, RGBCameraFirefly):
            return self.rgb_camera.set_exposure_time(time_us)
        return False
    
    # ... similar methods for all Firefly features ...
```

### Phase 4: Advanced Features

**Multi-Camera Synchronization:**
```python
def enable_camera_sync(thermal_cam, rgb_cam):
    \"\"\"Synchronize thermal and RGB captures via software trigger\"\"\"
    # Enable software trigger on Firefly
    rgb_cam.set_trigger_mode(True, 'Software')
    
    # In capture loop:
    while running:
        # Fire RGB trigger
        rgb_cam.execute_software_trigger()
        
        # Read both cameras (RGB waits for trigger)
        ret_rgb, frame_rgb = rgb_cam.read()
        ret_thermal, frame_thermal = thermal_cam.read()
        
        # Frames are now synchronized
        fused = fusion_processor.process(frame_rgb, frame_thermal)
```

**ROI-Based Inspection:**
```python
def configure_hardware_roi(camera, x, y, width, height):
    \"\"\"Configure hardware ROI for faster frame rates\"\"\"
    camera.set_property('OffsetX', x)
    camera.set_property('OffsetY', y)
    camera.set_property('Width', width)
    camera.set_property('Height', height)
    
    # Example: 640x480 ROI at 120 FPS vs. 1920x1200 at 60 FPS
```

---

## Verification Plan

### Unit Tests

```python
# tests/test_firefly_controls.py
def test_exposure_control():
    cam = RGBCameraFirefly()
    assert cam.open()
    
    # Test manual exposure
    assert cam.set_exposure_mode('Off')
    assert cam.set_exposure_time(5000.0)
    assert abs(cam.get_exposure_time() - 5000.0) < 10.0
    
    # Test auto exposure
    assert cam.set_exposure_mode('Continuous')
    
def test_trigger_mode():
    cam = RGBCameraFirefly()
    assert cam.open()
    
    # Enable software trigger
    assert cam.set_trigger_mode(True, 'Software')
    
    # Fire trigger and capture
    assert cam.execute_software_trigger()
    ret, frame = cam.read()
    assert ret and frame is not None
```

### Integration Tests

1. **GUI Panel Functionality:**
   - All sliders update camera properties in real-time
   - Mode switches properly enable/disable controls
   - Status display reflects actual camera state

2. **Thermal Fusion Quality:**
   - Fixed exposure eliminates brightness flicker
   - White balance consistency across frames
   - Global shutter prevents fusion artifacts

3. **Performance:**
   - No frame rate degradation from control updates
   - ROI mode achieves higher FPS
   - Trigger mode latency < 50ms

---

## User Documentation

### Quick Start Guide

**1. Basic Setup:**
- Connect Firefly camera via USB 3.0
- Application auto-detects and opens Firefly panel
- Default settings work for most scenarios

**2. Thermal Fusion Optimization:**
```
Settings → Firefly Camera
1. Exposure: Set to Manual, 5000 µs (5 ms)
2. Gain: Auto or 0-6 dB manual
3. White Balance: Continuous Auto
4. Result: Stable, consistent fusion
```

**3. Low Light Inspection:**
```
1. Exposure: Manual, 15000-20000 µs
2. Gain: Manual, 9-12 dB
3. White Balance: Once (calibrate on white before)
4. Result: Bright, low-noise images
```

**4. Motion Capture:**
```
1. Exposure: Manual, 500-1000 µs (fast)
2. Gain: Auto (compensates for low exposure)
3. Result: Frozen motion, no blur
```

### Presets System

**Built-in Presets:**
- `Thermal Fusion Standard` - Balanced settings for indoor fusion
- `Outdoor Bright` - Sunlight compensation
- `Low Light` - High gain for dark environments
- `Fast Motion` - Short exposure for moving subjects
- `Precision Inspection` - Fixed manual settings

**Custom Presets:**
- Save current settings with descriptive name
- Load quickly between inspection modes
- Export/import for sharing between systems

---

## Benefits Summary

### Image Quality
- ✅ **Eliminates motion blur** via global shutter
- ✅ **Consistent exposure** for stable thermal fusion
- ✅ **True color** via advanced white balance
- ✅ **Low noise** from optimized gain control

### Workflow Efficiency
- 🚀 **Faster frame rates** with hardware ROI
- 🚀 **Multi-camera sync** via trigger modes
- 🚀 **One-click presets** for common scenarios
- 🚀 **Real-time adjustment** without recalibration

### Professional Features
- 🎯 **Precise control** over every imaging parameter
- 🎯 **Repeatable results** from saved configurations
- 🎯 **Automated workflows** via software triggers
- 🎯 **Export-ready imagery** with optimal settings

---

## Next Steps

1. **Review this document** and provide feedback
2. **Prioritize features** - implement in phases or all at once?
3. **Test Firefly camera** - connect camera for hardware validation
4. **Begin implementation** - start with Phase 1 (core controls)
5. **Iterate on GUI** - refine panel layout based on usage

---

## Appendix: PySpin Node Reference

### Common Node Names

| Feature | Node Name | Type | Typical Values |
|---------|-----------|------|----------------|
| **Exposure** | | | |
| Auto Mode | `ExposureAuto` | Enum | Off, Once, Continuous |
| Exposure Time | `ExposureTime` | Float | 100 - 30000 µs |
| **Gain** | | | |
| Auto Mode | `GainAuto` | Enum | Off, Once, Continuous |
| Gain Value | `Gain` | Float | 0.0 - 18.0 dB |
| **White Balance** | | | |
| Auto Mode | `BalanceWhiteAuto` | Enum | Off, Once, Continuous |
| Color Selector | `BalanceRatioSelector` | Enum | Red, Blue |
| Ratio Value | `BalanceRatio` | Float | 0.5 - 3.0 |
| **Trigger** | | | |
| Mode | `TriggerMode` | Enum | Off, On |
| Source | `TriggerSource` | Enum | Software, Line0, Line1, Line2 |
| Activation | `TriggerActivation` | Enum | RisingEdge, FallingEdge, LevelHigh, LevelLow |
| Selector | `TriggerSelector` | Enum | FrameStart, AcquisitionStart |
| Execute | `TriggerSoftware` | Command | - |
| **Image** | | | |
| Width | `Width` | Integer | 16 - max width |
| Height | `Height` | Integer | 2 - max height |
| Offset X | `OffsetX` | Integer | 0 - (max width - width) |
| Offset Y | `OffsetY` | Integer | 0 - (max height - height) |
| Pixel Format | `PixelFormat` | Enum | BGR8, RGB8, Mono8, Mono12, BayerRG8 |
| Gamma | `Gamma` | Float | 0.5 - 4.0 |

### Code Snippet: Reading All Available Nodes

```python
def list_camera_features(camera):
    \"\"\"Enumerate all available camera features\"\"\"
    nodemap = camera.GetNodeMap()
    
    # Get root node
    category = PySpin.CCategoryPtr(nodemap.GetNode('Root'))
    if not PySpin.IsAvailable(category) or not PySpin.IsReadable(category):
        return
    
    features = category.GetFeatures()
    for feature in features:
        node_feature = PySpin.CValuePtr(feature)
        print(f'{node_feature.GetName()}: {node_feature.ToString()}')
```

Use this to discover camera-specific features and capabilities!
