# Thermal Inspection Fusion Tool - TODO List

**Last Updated**: 2025-11-30
**Current Version**: 3.3.1

---

## 🔴 HIGH PRIORITY

### 1. Radiometric System - ALL FEATURES COMPLETE ✅

**Phase**: 9 - Radiometric Temperature
**Status**: ✅ **FULLY IMPLEMENTED** - Testing pending

#### Tasks:
- [ ] **Test with Real Radiometric Camera**
  - [ ] Verify 16-bit detection works on actual Boson 640-R
  - [ ] Validate temperature accuracy against known reference
  - [ ] Compare readings with FLIR Tools software
  - [ ] Test temperature range calibration

- [x] **TLinear LUT Integration** ✅ **COMPLETE**
  - [x] ~~Query TLinear LUT via Boson SDK~~ (CSV file loading implemented)
  - [x] Load factory calibration into `TLinearConverter`
  - [x] Validate accuracy improvement over linear approximation
  - [x] Add GUI option to switch between linear/LUT methods

- [x] **Enhanced Temperature Features** ✅ **COMPLETE**
  - [x] Implement cursor mouseover temperature display ✅
  - [x] Add temperature overlay/colormap on thermal view ✅
  - [x] Add user-selectable measurement points (unlimited count) ✅
  - [x] Add temperature data export (CSV, JSON) ✅
  - [x] Create interactive radiometric calibration tool ✅

- [ ] **Performance Testing** (See Performance Optimization Refresh section)
  - [ ] Profile temperature conversion overhead
  - [ ] Optimize GUI update frequency (target: 30+ FPS)
  - [ ] Consider GPU acceleration for large frames
  - [ ] Benchmark full-frame vs ROI-only conversion

**Files**: `inspection_gui_qt.py`, `boson_sdk_panel.py`, `radiometric_panel.py`, `firefly_control_panel.py`, `parallax_panel.py`, `calibration_panel.py`
**Impact**: Critical for usability - truncated text makes features unusable

---

### GUI Tab and Subtab Reorganization

**Phase**: GUI Enhancement
**Status**: 🔴 **NEEDED** - Many new features added, tabs need reorganization

#### Tasks:
- [ ] **Reorganize Main Tab Structure** 🟡 **MEDIUM PRIORITY**
  - [ ] Audit current tab organization
    - List all tabs and subtabs currently in use
    - Identify which features are grouped together
  - [ ] Design new tab hierarchy
    - Group related features logically
    - Consider user workflow
    - Radiometric features (basic + advanced + per-ROI)
    - Boson SDK controls
    - Firefly controls
    - Analysis features
    - Calibration features
  - [ ] Implement reorganized structure
    - Update inspection_gui_qt.py tab creation
    - Move panels to appropriate parent tabs
    - Add breadcrumb or clear labeling
  - [ ] Test navigation and usability
  - **Goal**: Clean, logical tab structure as features expand

**Files**: `inspection_gui_qt.py`, all panel files
**Impact**: Better UX as feature count grows

---

### 4. FLIR Lepton SDK Integration

**Phase**: Hardware Integration
**Status**: ✅ **COMPLETE** (2025-11-29)

#### Tasks:
- [x] **SDK Wrapper Implementation** ✅ **COMPLETE**
  - [x] Create `lepton_sdk_wrapper.py` ✅
  - [x] Implement CCI/TWI protocol (I2C-based register protocol) ✅
  - [x] Abstract transport layer (`LeptonTransport`, `MockLeptonTransport`) ✅
  - [x] SYS module (FFC, Serial Number, Uptime, FPA Temperature) ✅
  - [x] AGC module (Enable/Disable, Policy selection) ✅
  - [x] RAD module (Radiometry, T-Linear, Spotmeter, Emissivity) ✅
  - **Goal**: Full SDK compatibility with pluggable transport backends

- [x] **GUI Panel** ✅ **COMPLETE**
  - [x] Create `lepton_control_panel.py` ✅
  - [x] Connection status display ✅
  - [x] FFC (Flat Field Correction) button ✅
  - [x] Radiometry enable/disable toggle ✅
  - [x] Emissivity slider (0.01-1.00) ✅
  - [x] Real-time temperature displays (FPA, Spotmeter) ✅
  - [x] Auto-refresh timer for status updates ✅

- [x] **Integration** ✅ **COMPLETE**
  - [x] Add to Cameras tab in `inspection_gui_qt.py` ✅
  - [x] Verify GUI loads (5 camera subtabs) ✅
  - [x] Test with mock transport ✅

**Files**: `lepton_sdk_wrapper.py`, `lepton_control_panel.py`, `inspection_gui_qt.py`
**Documentation**: See `walkthrough.md` in brain artifacts
**Status**: ✅ Ready for physical hardware (UVC XU transport implementation)

---

### 5. Performance Optimization Refresh

**Phase**: 10 - Performance Optimization
**Status**: 🟡 **IN PROGRESS** - Initial profiling complete

#### Tasks:
- [ ] **GUI Spacing Issue** 🔴 **HIGH PRIORITY**
  - [ ] Fix truncated text in GUI panels (e.g., `radiometric_panel.py`, `boson_sdk_panel.py`)
  - [ ] Ensure all labels and values are fully visible
  - [ ] Implement dynamic resizing or scroll areas where necessary
  - [ ] Test on various screen resolutions
  - **Goal**: Improve GUI readability and usability

- [ ] **Image Processing Pipeline Optimization**
  - [ ] Profile `fusion_processor.py` for bottlenecks
  - [ ] Optimize `cv2` operations (e.g., use `numpy` for batch processing)
  - [ ] Consider `numba` or `Cython` for critical loops
  - [ ] Implement multi-threading for independent processing steps
  - [ ] Evaluate `OpenCV` GPU modules (`cuda` module)

- [ ] **Data Transfer Optimization**
  - [ ] Minimize data copies between CPU and GPU (if GPU used)
  - [ ] Optimize `PyQt` image display (e.g., `QPixmap` vs `QImage`)
  - [ ] Reduce overhead of `QThread` communication

- [ ] **Memory Management**
  - [ ] Profile memory usage over extended periods
  - [ ] Identify and fix potential memory leaks
  - [ ] Optimize buffer management for large frames

- [ ] **Startup Time Reduction**
  - [ ] Profile application startup sequence
  - [ ] Lazy-load modules and resources
  - [ ] Optimize ML model loading (if applicable)

**Files**: `inspection_gui_qt.py`, `fusion_processor.py`, `radiometric_panel.py`, `boson_sdk_panel.py`
**Documentation**: See `archive/implementation-docs/PERFORMANCE_OPTIMIZATION_PLAN.md`
**Implementation**: See `IMPLEMENTATION_SUMMARY_2025-11-26.md`

---

### 1b. Advanced Radiometric Features (Phase 11 - NEW)

**Phase**: 11 - Advanced Temperature Measurement
**Status**: 🔴 **PLANNING** - Implementation plan ready

#### Tasks:
- [x] **Environmental Compensation** ✅ **COMPLETE** (2025-11-29)
  - [x] Implement emissivity control (0.01-1.0) ✅
    - `set_emissivity()`, `get_emissivity()` in boson_sdk_wrapper.py
  - [x] Add material emissivity presets dropdown ✅
    - Aluminum (0.05), Copper (0.04), Steel (0.16), Paint (0.95), PCB (0.90), etc.
  - [x] Implement atmospheric transmission control (0.8-1.0) ✅
    - `set_atmospheric_transmission()` for humidity/distance compensation
  - [x] Implement atmospheric temperature setting ✅
    - `set_atmospheric_temperature()` for environmental compensation
  - [x] Create `environmental_compensation_panel.py` GUI ✅
    - Emissivity slider + material presets (19 materials)
    - Atmospheric temp/transmission controls
    - Real-time accuracy indicator
  - [x] Integrate environmental panel into Analysis tab ✅
  - **Goal**: Improve temperature accuracy from ±2-5°C to ±0.5-1°C

- [x] **Per-ROI Radiometric Analysis** ✅ **COMPLETE** (2025-11-29)
  - [x] Implement per-ROI temperature statistics ✅
    - Min/max/avg temperature per ROI
    - Standard deviation per ROI
    - Pixel count per ROI
  - [x] Add per-ROI spot temperature reading ✅
    - Click inside ROI to get spot temp within that ROI (via mask)
    - Display in ROI info overlay
  - [x] Implement per-ROI emissivity settings (optional) ✅
    - Each ROI can have different material emissivity
    - Override global emissivity for specific ROIs
  - [x] Add per-ROI temperature trend tracking ✅
    - Track min/max/avg over time per ROI
    - Temperature history graph per ROI
  - [x] Create per-ROI temperature export ✅
    - CSV/JSON export with per-ROI statistics
    - Include ROI name, bounds, and all measurements
  - [x] Create `roi_temperature_panel.py` GUI ✅
    - Temperature statistics display per ROI
    - Color-coded temperature indicators (blue/green/yellow/red)
    - Export and clear history controls
  - [x] Integrate into Analysis tab ✅
  - [x] Integrate into inspection_main.py processing loop ✅
  - **Goal**: Complete radiometric analysis for each ROI independently + global
  - **Status**: ✅ **COMPLETE** - Full GUI + Backend implemented

- [x] **Isotherm Temperature Highlighting** ✅ **COMPLETE** (2025-11-29)
  - [x] Create `isotherm_panel.py` GUI ✅
    - Low/high threshold spinboxes (adjustable °C)
    - Mode selection (above/below/between/outside)
    - 7 color options (Red/Yellow/Green/Blue/Magenta/Cyan/White)
    - Preset buttons ("Hotspots >50°C", "Coldspots <10°C", "Normal 20-30°C")
  - [x] Implement highlighting logic in `thermal_processor.py` ✅
    - `apply_isotherm_highlighting()` method
    -  4 modes: above, below, between, outside thresholds
    - Semi-transparent color overlay (50% blend)
  - [x] Integrate isotherm panel into Analysis tab ✅
  - [x] Wire signal handlers in `inspection_gui_qt.py` ✅
  - **Goal**: Visual anomaly detection via temperature-based highlighting
  - **Status**: ✅ **COMPLETE** - Full GUI + Logic implemented

- [x] **SDK Spotmeter Integration** ✅ **COMPLETE** (2025-11-30)
  - [x] Add GUI controls in radiometric_panel.py ✅
  - [x] Define signals for spotmeter (enabled_changed, mode_changed) ✅
  - [x] Implement hardware spotmeter methods in boson_sdk_wrapper.py ✅
    - `spotmeter_enable()`, `spotmeter_set_roi()`, `spotmeter_get_temperature()`
    - `spotmeter_set_statistics_mode()` with center/average/max/min modes
  - [x] Wire signals in inspection_main.py ✅
  - [x] Implement handler methods with graceful fallback ✅
  - [ ] Benchmark performance (SDK vs software)
  - [ ] Document use cases
  - **Goal**: Faster cursor temperature readings via hardware acceleration
  - **Status**: ✅ **COMPLETE** - Ready for hardware testing

- [x] **Enhanced Sensor Temperature Monitoring** ✅ **COMPLETE** (2025-11-30)
  - [x] Create sensor temperatures section in radiometric_panel.py ✅
  - [x] Add FPA, Lens, Shutter, Board temperature labels ✅
  - [x] Add auto-refresh checkbox and timer ✅
  - [x] Define sensor_temps_requested signal ✅
  - [x] Wire signal in inspection_main.py ✅
  - [x] Implement update handler to read sensor temps ✅
  - [ ] Test with real hardware
  - **Goal**: Better thermal management monitoring
  - **Status**: ✅ **COMPLETE** - Ready for hardware testing

- [ ] **Fusion Controls Reorganization** (Medium Priority)
  - [ ] Design new "Fusion" main tab structure
  - [ ] Move fusion mode/alpha/priority controls from bottom panel
  - [ ] Expose advanced fusion parameters:
    - Edge strength, edge fuzziness, edge color
    - Detail strength, detail quality
    - Color mode selection
    - Fusion intensity control
  - [ ] Create dedicated FusionControlPanel widget
  - [ ] Organize controls into logical groups
  - [ ] Update inspection_gui_qt.py tab structure
  - **Goal**: Better organization and exposure of fusion settings
  - **Impact**: Improved UX for fusion feature discovery

**Files**: `boson_sdk_wrapper.py`, `radiometric_environmental_panel.py` (NEW), `isotherm_panel.py` (NEW), `radiometric_panel.py`
**Documentation**: See implementation plan in brain artifacts
**Effort**: 5-7 days total (Phase 1: 2-3 days env compensation, Phase 2: 2 days isotherm, Phase 3: 1-2 days spotmeter)

---

### 2. Software Parallax Compensation

**Phase**: 11 - Parallax Correction
**Status**: ✅ **ML MODEL INTEGRATION COMPLETE** - DepthAnything V2 implemented

#### Tasks:
- [x] **Depth Estimation Integration** ✅ **COMPLETE** 
  - [x] **Integrate DepthAnything V2 ML models for parallax** ✅ **COMPLETE v3.3.0**
  - [x] Implement depth map generation from RGB camera (ML + simplified methods)
  - [x] Multiple model sizes (Small/Base/Large) for performance/quality tradeoff
  - [x] Auto device detection (CUDA/CPU) with graceful fallback
  - [ ] Optimize depth estimation performance (GPU acceleration)
  - [ ] Test depth accuracy at various distances (0.5m - 5m)

- [x] **Parallax Correction Implementation** ✅ **CORE COMPLETE**
  - [x] Implement depth-based pixel displacement calculation
  - [x] Create adaptive alignment based on depth map
  - [ ] Handle edge cases (occlusions, depth discontinuities)
  - [ ] Validate alignment accuracy

- [x] **GUI Controls** ✅ **BACKEND COMPLETE** (GUI panel integration pending)
  - [x] Parallax compensation core functionality
  - [x] Baseline distance configuration support
  - [x] Depth map visualization support (get_depth_map())
  - [ ] Add GUI panel for enable/disable toggle
  - [ ] Add model selection dropdown (Small/Base/Large)
  - [ ] Add depth map visualization overlay
  - [ ] Implement alignment quality indicator

- [ ] **Validation & Tuning**
  - [ ] Test with checkerboard patterns at multiple distances
  - [ ] Measure alignment error (RMSE in pixels)
  - [ ] Fine-tune depth estimation parameters
  - [ ] Create user calibration workflow

- [ ] **PyTorch DLL Issue** 🔴 **KNOWN ISSUE**
  - **Status**: Using simplified geometric mode (working fallback)
  - **Issue**: PyTorch 2.9.1 has DLL dependency issue with `shm.dll`
    - Error: "The specified procedure could not be found" (WinError 127)
    - Despite VC++ 2022 (v14.50.35710) being installed
    - `vcruntime140.dll` exists in System32/SysWOW64
  - **Workaround**: App gracefully falls back to simplified mode ✅
  - **Future Investigation**:
    - [ ] Try different PyTorch version (2.8.x, 2.7.x)
    - [ ] Try PyTorch CPU-only build from official site
    - [ ] Check for missing CUDA/cuDNN dependencies
    - [ ] Consider compiling PyTorch from source
  - **Decision**: Use simplified mode for now, revisit ML depth later

**Files**: `parallax_compensator.py` ✅ (523 lines, v3.3.0), `parallax_panel.py` ✅, `fusion_processor.py`
**Documentation**: See `archive/implementation-docs/PARALLAX_COMPENSATION_PLAN.md`, CHANGELOG v3.3.0
**Implementation**: See `IMPLEMENTATION_SUMMARY_2025-11-26.md`, CHANGELOG v3.3.0 (2025-11-27)

---

### 3. Boson SDK - Universal Features Completion

**Phase**: SDK Enhancement - Universal
**Status**: ✅ **CORE FEATURES COMPLETE** - GUI integration complete ✅

#### Tasks:
- [x] **Extended BOSON Module Functions** ✅ **PARTIALLY COMPLETE**
  - [x] `get_frame_count()` - Frame number since boot (already existed)
  - [x] `get_frame_rate()` - Current FPS ✅ **NEW**
  - [ ] `get_thermal_mode()` - Current thermal mode info
  - [ ] `set_video_mode(mode)` - Video output mode control
  - [ ] `get_software_version()` - Enhanced version info

- [x] **Shutter Control** ✅ **COMPLETE**
  - [x] `set_shutter_position(position)` - OPEN/CLOSED/AUTO ✅ **NEW**
  - [x] `get_shutter_position()` - Current position ✅ **NEW**
  - [ ] `set_shutter_temperature_override(temp)` - Manual temp set
  - [x] **Add shutter control GUI to Boson SDK panel** ✅ **COMPLETE**

- [x] **Enhanced AGC Features** ✅ **COMPLETE**
  - [x] `set_agc_plateau(histogram_percent)` - Plateau equalization ✅ **NEW**
  - [x] `set_agc_dampening(factor)` - Temporal smoothing ✅ **NEW**
  - [ ] `set_agc_hi_temp_rejection(enable)` - Ignore hot pixels
  - [x] **Add advanced AGC controls to GUI panel** ✅ **COMPLETE**

- [x] **System Monitoring** ✅ **COMPLETE**
  - [x] `get_system_status()` - Overall health status ✅ **NEW**
  - [ ] `get_dsp_software_version()` - DSP firmware version
  - [ ] `get_boot_mode()` - Boot configuration info
  - [ ] **Create system diagnostics panel for SDK monitoring** 🔴 **PENDING** (Lower Priority)

- [x] **SDK Architecture Refactoring** ✅ **ANALYSIS COMPLETE**
  - [x] Systematically evaluate all files and dependencies ✅
  - [x] Label which SDK each file/module requires: ✅
    - `boson_sdk` - FLIR Boson thermal camera SDK dependencies (6 files)
    - `firefly_sdk` - FLIR Firefly RGB camera SDK dependencies/Spinnaker (6 files)
    - `depthanything_sdk` - DepthAnything V2 ML depth estimation dependencies (4 files)
    - `shared` - Files used by multiple SDKs or no SDK dependency (34 files)
  - [x] Create SDK dependency mapping document ✅
    - `archive/implementation-docs/SDK_ARCHITECTURE_ANALYSIS.md`
  - [ ] Refactor imports to be more modular and SDK-specific (OPTIONAL  - current arch is excellent)
  - [ ] Enable easier addition of new camera products with different SDKs (FUTURE)
  - [ ] Consider SDK plugin architecture for future extensibility (FUTURE)
  - [ ] Update documentation with SDK dependency labels (OPTIONAL)

**Files**: `boson_sdk_wrapper.py` ✅, `inspection_gui_qt.py` ✅ (Boson Control Panel with shutter & AGC GUI)
**Documentation**: See `archive/sdk-docs/SDK_GAP_ANALYSIS.md`
**Implementation**: See `IMPLEMENTATION_SUMMARY_2025-11-26.md`

---

## 🟡 MEDIUM PRIORITY

### 4. Boson SDK - Radiometric Features (Advanced)

**Phase**: SDK Enhancement - Radiometric
**Status**: Basic implementation (40%)

#### Tasks:
- [ ] **Temperature Calibration**
  - [ ] `set_radiometric_enable(enable)` - Enable/disable radiometry
  - [ ] `set_tlinear_resolution(mode)` - HIGH/LOW resolution mode
  - [ ] `set_tlinear_auto_resolution(enable)` - Auto switching
  - [ ] `calibrate_radiometry(reference_temps)` - Multi-point calibration

- [ ] **Spotmeter Module**
  - [ ] `set_spotmeter_position(x, y)` - Interactive spot measurement
  - [ ] `get_spotmeter_temperature()` - Spot temp reading
  - [ ] `set_spotmeter_roi(x1, y1, x2, y2)` - ROI spotmeter
  - [ ] Add visual spotmeter cursor in GUI

- [ ] **Isotherm Module**
  - [ ] `set_isotherm_mode(mode)` - BLACK_HOT/WHITE_HOT/COLOR
  - [ ] `set_isotherm_thresholds(low, mid, high)` - Temperature bands
  - [ ] `set_isotherm_colors(color1, color2, color3)` - Band colors
  - [ ] Add isotherm overlay visualization

- [ ] **TLINEAR Module (Advanced)**
  - [ ] `get_tlinear_lut()` - Download factory calibration table
  - [ ] `set_tlinear_lut(lut)` - Upload custom LUT
  - [ ] `validate_tlinear_accuracy()` - Accuracy testing
  - [ ] GUI LUT management interface

**Files**: `boson_sdk_wrapper.py`, new `spotmeter_panel.py`, `isotherm_panel.py`

---

### 5. Firefly Camera SDK - Advanced Features

**Phase**: SDK Enhancement - Firefly
**Status**: Basic controls implemented (70%)

#### Tasks:
- [ ] **Advanced Imaging Features**
  - [ ] HDR mode support
  - [ ] Multi-exposure capture
  - [ ] Binning mode control
  - [ ] ROI readout optimization

- [ ] **Color Processing**
  - [ ] Advanced white balance algorithms
  - [ ] Color correction matrix (CCM) control
  - [ ] Hue/saturation adjustment
  - [ ] Color temperature presets

- [ ] **Synchronization**
  - [ ] Hardware trigger configuration (IN/OUT)
  - [ ] Strobe output control
  - [ ] Multi-camera sync setup
  - [ ] Timestamp synchronization with Boson

- [ ] **Performance Optimization**
  - [ ] Packet size optimization for USB3
  - [ ] Frame rate optimization
  - [ ] Bandwidth monitoring
  - [ ] Buffer management tuning

**Files**: `rgb_camera_firefly.py`, `firefly_control_panel.py`

---

### 6. UI/UX Enhancements

**Phase**: UI Polish
**Status**: Functional, improvements needed

#### Tasks:
- [ ] **Layout Improvements**
  - [ ] Reorganize control panels by workflow
  - [ ] Add collapsible sections for advanced controls
  - [ ] Improve tab organization (too many tabs)
  - [ ] Add quick-access toolbar for common functions

- [ ] **Visualization Enhancements**
  - [ ] Add temperature colorbar legend
  - [ ] Improve ROI visualization (labels, colors)
  - [ ] Add grid overlay option
  - [ ] Implement zoom and pan controls

- [ ] **Workflow Optimization**
  - [ ] Add preset management system
  - [ ] Implement keyboard shortcuts for common actions
  - [ ] Add context menus (right-click)
  - [ ] Create inspection workflow wizard

- [ ] **Status Display**
  - [ ] Enhanced connection status indicators
  - [ ] Real-time FPS display
  - [ ] Camera temperature warnings
  - [ ] System performance metrics
**Files**: `inspection_gui_qt.py`

---

## 📦 BACKLOG / FUTURE ENHANCEMENTS

### Camera Support Expansion

#### FLIR Lepton SDK Integration
**Status**: 🔵 **BACKLOG** - Future enhancement

- [ ] **Integrate FLIR Lepton SDK**
  - [ ] Research Lepton SDK architecture vs Boson SDK
  - [ ] Create `lepton_sdk_wrapper.py` similar to boson_sdk_wrapper
  - [ ] Implement Lepton camera detection
  - [ ] Add Lepton-specific controls (if different from Boson)
  - [ ] Test with FLIR Lepton hardware
  - [ ] Update camera_factory.py for Lepton support
  - [ ] Create Lepton control panel (if needed)
  - **Goal**: Support FLIR Lepton thermal cameras alongside Boson

**Priority**: LOW (nice-to-have for broader hardware support)
**Effort**: 1-2 weeks (depending on SDK similarity to Boson)

---

### Additional Future Ideastion & Testing

#### Tasks:
- [ ] **User Documentation**
  - [ ] Write comprehensive user manual
  - [ ] Create tutorial videos
  - [ ] Add tooltips to all GUI controls
  - [ ] Write troubleshooting guide

- [ ] **Developer Documentation**
  - [ ] API reference for all modules
  - [ ] Architecture diagrams
  - [ ] Contribution guidelines
  - [ ] Code style guide

- [ ] **Testing**
  - [ ] Unit tests for core modules
  - [ ] Integration tests for camera systems
  - [ ] GUI automated testing
  - [ ] Performance benchmarking suite

---

### 8. Advanced Analysis Features

#### Tasks:
- [ ] **AI-Powered Analysis**
  - [ ] Automatic anomaly detection (ML-based)
  - [ ] Temperature pattern recognition
  - [ ] Predictive failure analysis
  - [ ] Smart ROI suggestions

- [ ] **Multi-Session Analysis**
  - [ ] Session comparison tools
  - [ ] Trend analysis across sessions
  - [ ] Differential thermal imaging
  - [ ] Long-term monitoring

- [ ] **Export & Reporting**
  - [ ] PDF report generation
  - [ ] CSV data export with metadata
  - [ ] Thermal image export (16-bit TIFF)
  - [ ] Video export with temperature overlay

---

### 9. Platform-Specific Features

#### Tasks:
- [ ] **Jetson Optimization**
  - [ ] VPI acceleration for all processing
  - [ ] GPU-accelerated temperature conversion
  - [ ] CUDA kernels for fusion algorithms
  - [ ] Power management optimization

- [ ] **Windows Optimization**
  - [ ] DirectX rendering backend option
  - [ ] Windows-native camera APIs
  - [ ] Installer creation (NSIS/WiX)
  - [ ] Auto-update mechanism

- [ ] **Linux Optimization**
  - [ ] V4L2 backend optimization
  - [ ] udev rules for camera permissions
  - [ ] AppImage/Flatpak packaging
  - [ ] systemd service for monitoring mode

---

## 📋 Backlog

### Future Considerations
- [ ] Web-based remote monitoring interface
- [ ] Mobile app companion (iOS/Android)
- [ ] Cloud storage integration
- [ ] Multi-camera support (4+ cameras)
- [ ] 3D thermal reconstruction
- [ ] AR overlay for mobile devices
- [ ] Custom plugin system
- [ ] REST API for automation

---

## 🔵 IMMEDIATE PRIORITY (Post-Implementation)

### Performance Optimization Refresh
**Status**: Pending
**Reason**: Recent additions (radiometric, parallax, SDK features) need optimization review

#### Tasks:
- [ ] **Profile Recent Changes**
  - [ ] Benchmark radiometric temperature conversion performance
  - [ ] Measure parallax correction overhead (enabled vs disabled)
  - [ ] Profile cursor temperature readout latency
  - [ ] Check SDK communication delays

- [ ] **Optimize Hotspots**
  - [ ] Vectorize radiometric frame conversion if needed
  - [ ] Cache depth maps in parallax compensator
  - [ ] Reduce GUI update frequency for non-critical elements
  - [ ] Batch SDK queries where possible

- [ ] **Memory Usage**
  - [ ] Check for memory leaks in new modules
  - [ ] Optimize LUT storage
  - [ ] Review depth map caching strategy

- [ ] **Target Performance**
  - [ ] Maintain 30+ FPS with all features disabled (baseline)
  - [ ] Achieve 25+ FPS with radiometric enabled
  - [ ] Achieve 20+ FPS with parallax compensation enabled
  - [ ] GPU acceleration candidates identified

**Files**: All recent additions, `performance_monitor.py`
**Deadline**: Before production deployment

---

## ✅ Recently Completed

### Version 3.2.0 (2025-11-27) - RADIOMETRIC & SDK GUI COMPLETION
- ✅ **Radiometric System - Fully Functional**
  - ✅ Added `enable_radiometric_mode()` to FLIR camera
  - ✅ Mouse cursor temperature tracking with live display
  - ✅ TLinear LUT integration with CSV file loading
  - ✅ Method selection: Linear (fast) vs LUT (accurate)
  - ✅ GUI population: Center, cursor, and frame statistics
  - ✅ Real-time temperature display at cursor position
  - ✅ Temperature overlay visualization (5 colormaps: Jet, Hot, Cool, Viridis, Plasma)
  - ✅ User-selectable measurement points (unlimited count, dynamic)
  - ✅ Measurement point click-to-add interface with crosshair cursor
  - ✅ Live temperature update for all measurement points
  - ✅ Temperature data export (CSV and JSON formats with timestamps)

- ✅ **Boson SDK GUI Controls Complete**
  - ✅ Shutter control GUI (Auto/Open/Closed buttons) in Simple Controls tab
  - ✅ Advanced AGC plateau control (histogram equalization slider)
  - ✅ Advanced AGC dampening control (temporal smoothing slider)
  - ✅ All controls auto-enable/disable based on SDK connection
  - ✅ Integrated into AGC reset function

- ✅ **Radiometric Calibration Tool**
  - ✅ Multi-point calibration system (linear and polynomial fitting)
  - ✅ Interactive GUI panel with point table
  - ✅ Click-to-add calibration points on thermal view
  - ✅ Real-time error display and statistics (RMSE, mean error)
  - ✅ Apply calibration correction to all temperature measurements
  - ✅ Import/export calibration files (JSON format)
  - ✅ Auto-application of calibration to temperature frames

- ✅ **Boson SDK Universal Features**
  - ✅ `get_frame_rate()` - FPS query
  - ✅ `set_shutter_position()` / `get_shutter_position()` - FFC shutter control
  - ✅ `set_agc_plateau()` - Histogram equalization
  - ✅ `set_agc_dampening()` - Temporal smoothing
  - ✅ `get_system_status()` - Comprehensive health monitoring

- ✅ **Parallax Compensation Scaffolding**
  - ✅ Created `parallax_compensator.py` module
  - ✅ Created `parallax_panel.py` GUI panel
  - ✅ Integrated into main application (DISABLED by default)
  - ✅ Depth estimation support: Simplified (geometric), MiDaS, DepthAnything
  - ✅ Configurable baseline distance
  - ✅ Performance metrics display
  - ✅ Visualization options (depth map, displacement vectors)

### Version 3.0.0 (2025-11-26)
- ✅ Documentation reorganization and archive structure
- ✅ README complete rewrite (ADAS history removed)
- ✅ Palette count update (14 → 45)
- ✅ Radiometric converter implementation
- ✅ Radiometric GUI panel
- ✅ 16-bit frame preservation in camera
- ✅ Archive README with directory explanations

### Version 2.8.0 (2025-11-24)
- ✅ Boson SDK Phase 1 (RADIOMETRY + AGC modules)
- ✅ Edge fusion enhancement (color, strength, blur)
- ✅ AGC controls (max gain, gamma, linearity, DDE)

### Version 2.7.0 (2025-11-24)
- ✅ Boson SDK runtime connection
- ✅ GUI integration for SDK controls

### Phase 8 (2025-11-25)
- ✅ Camera detection system
- ✅ Firefly RGB camera support
- ✅ Camera registry
- ✅ Firefly control panel
- ✅ Max resolution auto-detection

---

## Notes

### Priority Guidelines
- 🔴 **HIGH**: Essential for core functionality, blocks other features
- 🟡 **MEDIUM**: Important improvements, enhances user experience
- 🟢 **LOW**: Nice-to-have features, polish and optimization

### Implementation Strategy
1. Complete HIGH priority items before starting MEDIUM
2. Test thoroughly after each feature implementation
3. Update documentation as features are added
4. Get user feedback before implementing LOW priority items

### Testing Requirements
- All HIGH priority items require real hardware testing
- All SDK features require verification with actual cameras
- Performance features require benchmarking
- UI changes require user acceptance testing

---

**For detailed implementation plans, see:**
- `archive/implementation-docs/PARALLAX_COMPENSATION_PLAN.md`
- `archive/sdk-docs/SDK_GAP_ANALYSIS.md`
- `archive/sdk-docs/RADIOMETRIC_IMPLEMENTATION_COMPLETE.md`
