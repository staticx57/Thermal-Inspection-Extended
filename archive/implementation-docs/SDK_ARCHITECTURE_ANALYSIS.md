# SDK Architecture Dependency Mapping

## Overview

This document maps all Python files in the Thermal Inspection Fusion Tool to their SDK dependencies. This enables:
- Clear understanding of which files require which SDKs
- Easier addition of new camera products with different SDKs
- Future plugin architecture planning
- Modular dependency management

**Date Created**: 2025-11-27  
**Total Files**: 50 Python files analyzed

---

## SDK Categories

### 1. Boson SDK (`boson_sdk`)
**Purpose**: FLIR Boson thermal camera SDK dependencies (serial communication, radiometric control)

**Files**:
- `boson_sdk_wrapper.py` (35,895 bytes) - Core Boson SDK Python wrapper
- `boson_sdk_panel.py` (11,786 bytes) - GUI controls for Boson SDK features
- `boson_serial.py` (19,687 bytes) - Serial communication with Boson
- `debug_boson_serial.py` (4,601 bytes) - Boson serial debugging utility
- `test_boson_serial.py` (6,683 bytes) - Boson serial test script
- `test_sdk_integration.py` (1,667 bytes) - SDK integration tests

**Dependencies**:
- `pyserial` - Serial port communication
- Boson SDK DLLs (optional, for advanced features)

**Used By**:
- `inspection_main.py` - Main app (optional Boson SDK support)
- `inspection_gui_qt.py` - GUI (Boson SDK panel integration)
- `flir_camera.py` - Thermal camera interface with optional SDK

---

### 2. Firefly SDK (`firefly_sdk`)
**Purpose**: FLIR Firefly RGB camera SDK dependencies (Spinnaker SDK for industrial cameras)

**Files**:
- `rgb_camera_firefly.py` (40,001 bytes) - Firefly camera interface via Spinnaker
- `firefly_control_panel.py` (20,010 bytes) - GUI controls for Firefly camera
- `diagnose_spinnaker.py` (12,243 bytes) - Spinnaker diagnostic utility
- `verify_pyspin.py` (8,216 bytes) - PySpin installation verification
- `test_firefly_quick.py` (4,873 bytes) - Quick Firefly test
- `test_simple_firefly.py` (2,088 bytes) - Simple Firefly test

**Dependencies**:
- `PySpin` - Python bindings for Spinnaker SDK
- Spinnaker SDK (FLIR industrial camera SDK)

**Used By**:
- `camera_detector.py` - Auto-detection with Spinnaker priority
- `inspection_main.py` - RGB camera initialization
- `inspection_gui_qt.py` - Firefly control panel integration

---

### 3. DepthAnything SDK (`depthanything_sdk`)
**Purpose**: ML depth estimation for parallax compensation

**Files**:
- `parallax_compensator.py` (20,092 bytes) - Depth estimation + parallax correction
- `parallax_panel.py` (13,297 bytes) - GUI controls for parallax compensation
- `generate_parallax.py` (20,502 bytes) - Code generation script for parallax module
- `fix_parallax.py` (3,995 bytes) - Parallax module repair utility

**Dependencies**:
- `torch` (PyTorch) - Deep learning framework
- `transformers` (HuggingFace) - DepthAnything V2 models
- `huggingface-hub` - Model downloads
- `PIL` (Pillow) - Image conversion

**Used By**:
- `inspection_main.py` - Optional parallax compensation
- `fusion_processor.py` - Thermal-RGB alignment

**Status**: ✅ Graceful fallback to simplified mode if dependencies unavailable

---

### 4. Shared / Core (`shared`)
**Purpose**: Files with no SDK dependency or used by multiple SDKs

#### Camera Management (Multi-SDK)
- `camera_detector.py` (37,433 bytes) - Detects thermal/RGB cameras (Spinnaker + UVC)
- `camera_factory.py` (17,186 bytes) - Camera instantiation factory
- `camera_initializer.py` (11,871 bytes) - Thread-safe camera initialization
- `camera_monitor.py` (7,942 bytes) - Camera connection monitoring
- `camera_registry.py` (11,056 bytes) - Persistent camera assignments
- `threaded_camera_capture.py` (5,925 bytes) - Multi-threaded frame capture
- `rgb_camera.py` (13,067 bytes) - Base RGB camera interface
- `rgb_camera_uvc.py` (12,236 bytes) - UVC webcam interface (no SDK)
- `flir_camera.py` (25,534 bytes) - Thermal camera interface (optional Boson SDK)

#### Thermal Processing (No SDK)
- `thermal_processor.py` (29,182 bytes) - Thermal frame processing
- `thermal_analyzer.py` (37,410 bytes) - Temperature analysis, hot/cold spot detection
- `roi_manager.py` (23,588 bytes) - ROI creation and management
- `palette_manager.py` (38,551 bytes) - 45 thermal palettes

#### Fusion \u0026 Processing (No SDK)
- `fusion_processor.py` (32,399 bytes) - 7 fusion algorithms
- `measurement_points.py` (9,537 bytes) - Temperature measurement points

#### Radiometric Processing (Optional Boson SDK)
- `radiometric_converter.py` (22,176 bytes) - 16-bit temperature conversion
- `radiometric_panel.py` (23,764 bytes) - Radiometric GUI panel
- `radiometric_calibration.py` (12,666 bytes) - Temperature calibration
- `calibration_panel.py` (14,883 bytes) - Calibration GUI panel

#### GUI \u0026 Application (Multi-SDK Integration)
- `inspection_gui_qt.py` (234,206 bytes) - Main Qt GUI (integrates all panels)
- `inspection_main.py` (135,549 bytes) - Main application (integrates all SDKs)
- `settings_editor.py` (62,348 bytes) - Settings editor GUI
- `settings_manager.py` (17,969 bytes) - Configuration management
- `config.py` (15,811 bytes) - Configuration handling
- `preset_manager.py` (9,503 bytes) - Preset management
- `view_mode.py` (321 bytes) - View mode enumeration

#### Media \u0026 Recording (No SDK)
- `media_recorder.py` (18,053 bytes) - Video/snapshot recording
- `placeholder_frames.py` (6,468 bytes) - Placeholder frame generation

#### Utilities (No SDK)
- `performance_monitor.py` (6,642 bytes) - FPS and performance tracking
- `multi_row_tabwidget.py` (7,422 bytes) - Custom Qt widget
- `camera_calibration.py` (16,713 bytes) - Camera intrinsic/extrinsic calibration

#### Test Scripts (Various)
- `test_camera_detection.py` (4,841 bytes) - Camera detection tests
- `test_max_resolution.py` (7,207 bytes) - Resolution detection test

#### Backup/Legacy
- `inspection_gui_qt_pyqt5_backup.py` (48,497 bytes) - PyQt5 backup (deprecated)

---

## SDK Dependency Matrix

| SDK Category | File Count | Total Size | Required | Fallback Available |
|--------------|------------|------------|----------|-------------------|
| **Boson SDK** | 6 files | ~78 KB | Optional | ✅ Yes (basic thermal) |
| **Firefly SDK** | 6 files | ~92 KB | Optional | ✅ Yes (UVC webcam) |
| **DepthAnything SDK** | 4 files | ~58 KB | Optional | ✅ Yes (simplified mode) |
| **Shared/Core** | 34 files | ~682 KB | Required | N/A |

---

## Modularity Assessment

### ✅ Excellent Modularity
- **Boson SDK**: Cleanly isolated in wrapper + panel files
- **Firefly SDK**: Cleanly isolated in RGB camera + panel files  
- **DepthAnything SDK**: Cleanly isolated in parallax module

### ⚠️ Areas for Improvement

1. **`inspection_main.py` (135 KB)**:
   - Imports all SDKs
   - Could benefit from plugin architecture for SDK loading
   - Recommendation: Create SDK plugin loader

2. **`camera_detector.py` (37 KB)**:
   - Has PySpin imports for Firefly detection
   - Well-handled with try/except fallback
   - Recommendation: Keep as-is, good graceful degradation

3. **`flir_camera.py` (25 KB)**:
   - Optional Boson SDK imports
   - Well-handled with availability flags
   - Recommendation: Keep as-is

---

## Recommended Refactoring (Future)

### Phase 1: SDK Plugin Architecture
```python
# sdk_loader.py (proposed)
class SDKPlugin:
    def __init__(self, name: str, required: bool = False):
        self.name = name
        self.available = False
        self.module = None
    
    def load(self) -> bool:
        try:
            # Dynamic import based on plugin name
            if self.name == "boson_sdk":
                from boson_sdk_wrapper import BosonSDKWrapper
                self.module = BosonSDKWrapper
                self.available = True
            # ... repeat for other SDKs
        except ImportError:
            if self.required:
                raise
            return False
        return True
```

### Phase 2: Dependency Injection
- Pass SDK instances to classes that need them
- Avoid global imports where possible
- Enable unit testing without SDK dependencies

### Phase 3: Configuration-Based Loading
```json
{
  "sdks": {
    "boson_sdk": {"enabled": true, "required": false},
    "firefly_sdk": {"enabled": true, "required": false},
    "depthanything_sdk": {"enabled": false, "required": false}
  }
}
```

---

## Current Architecture Strengths

1. ✅ **Graceful Degradation**: All SDKs have fallbacks
2. ✅ **Try/Except Isolation**: SDK imports wrapped in error handling
3. ✅ **Availability Flags**: `BOSON_SDK_AVAILABLE`, `TRANSFORMERS_AVAILABLE`
4. ✅ **Optional Features**: No SDK is strictly required for basic operation
5. ✅ **Clean Separation**: SDK-specific code isolated in dedicated files

---

## Integration Points

### Main Application (`inspection_main.py`)
```python
Line 61: from parallax_compensator import ParallaxCompensator  # DepthAnything SDK
Line 2665: from parallax_compensator import DepthEstimator     # DepthAnything SDK
# Boson SDK: Optional initialization via command-line flag
# Firefly SDK: Auto-detected via camera_detector.py
```

### GUI (`inspection_gui_qt.py`)
```python
Line 32: from firefly_control_panel import FireflyControlPanel  # Firefly SDK
Line 33: from radiometric_panel import RadiometricPanel         # Boson SDK (optional)
Line 34: from parallax_panel import ParallaxPanel               # DepthAnything SDK
Line 4688: from calibration_panel import CalibrationPanel       # Shared
```

---

## Conclusion

**Current Status**: ✅ **Excellent SDK architecture** with clean separation and graceful fallbacks

**Strengths**:
- All SDKs are optional with fallback modes
- Clear file organization by SDK dependency
- Minimal coupling between SDK-specific and shared code

**Future Opportunities**:
- Plugin architecture for easier addition of new camera SDKs
- Configuration-based SDK loading
- Dependency injection for better testability

**Recommendation**: Current architecture is production-ready. SDK plugin architecture can be implemented incrementally as new camera products are added.
