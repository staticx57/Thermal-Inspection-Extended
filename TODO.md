# Thermal Inspection Fusion Tool - TODO List

**Last Updated**: 2025-11-26
**Current Version**: 3.0.0

---

## 🔴 HIGH PRIORITY

### 1. Radiometric System Verification & Completion

**Phase**: 9 - Radiometric Temperature (Testing & Refinement)
**Status**: Implementation complete, testing pending

#### Tasks:
- [ ] **Test with Real Radiometric Camera**
  - [ ] Verify 16-bit detection works on actual Boson 640-R
  - [ ] Validate temperature accuracy against known reference
  - [ ] Compare readings with FLIR Tools software
  - [ ] Test temperature range calibration

- [ ] **TLinear LUT Integration**
  - [ ] Query TLinear LUT via Boson SDK
  - [ ] Load factory calibration into `TLinearConverter`
  - [ ] Validate accuracy improvement over linear approximation
  - [ ] Add GUI option to switch between linear/LUT methods

- [ ] **Enhanced Temperature Features**
  - [ ] Implement cursor mouseover temperature display
  - [ ] Add temperature overlay/colormap on thermal view
  - [ ] Create interactive calibration tool
  - [ ] Add temperature data export (CSV, JSON)

- [ ] **Performance Testing**
  - [ ] Profile temperature conversion overhead
  - [ ] Optimize GUI update frequency (target: 30+ FPS)
  - [ ] Consider GPU acceleration for large frames
  - [ ] Benchmark full-frame vs ROI-only conversion

**Files**: `radiometric_converter.py`, `radiometric_panel.py`, `flir_camera.py`
**Documentation**: See `archive/sdk-docs/RADIOMETRIC_IMPLEMENTATION_COMPLETE.md`

---

### 2. Software Parallax Compensation

**Phase**: 11 - Parallax Correction
**Status**: Plan complete, implementation pending

#### Tasks:
- [ ] **Depth Estimation Integration**
  - [ ] Integrate MiDaS or DepthAnything model
  - [ ] Implement depth map generation from RGB camera
  - [ ] Optimize depth estimation performance (GPU acceleration)
  - [ ] Test depth accuracy at various distances (0.5m - 5m)

- [ ] **Parallax Correction Implementation**
  - [ ] Implement depth-based pixel displacement calculation
  - [ ] Create adaptive alignment based on depth map
  - [ ] Handle edge cases (occlusions, depth discontinuities)
  - [ ] Validate alignment accuracy

- [ ] **GUI Controls**
  - [ ] Add parallax compensation enable/disable toggle
  - [ ] Create baseline distance configuration slider
  - [ ] Add depth map visualization option
  - [ ] Implement alignment quality indicator

- [ ] **Validation & Tuning**
  - [ ] Test with checkerboard patterns at multiple distances
  - [ ] Measure alignment error (RMSE in pixels)
  - [ ] Fine-tune depth estimation parameters
  - [ ] Create user calibration workflow

**Files**: New module `parallax_compensator.py`, updates to `fusion_processor.py`
**Documentation**: See `archive/implementation-docs/PARALLAX_COMPENSATION_PLAN.md`

---

### 3. Boson SDK - Universal Features Completion

**Phase**: SDK Enhancement - Universal
**Status**: Partial implementation (60%)

#### Tasks:
- [ ] **Extended BOSON Module Functions**
  - [ ] `get_frame_count()` - Frame number since boot
  - [ ] `get_frame_rate()` - Current FPS
  - [ ] `get_thermal_mode()` - Current thermal mode info
  - [ ] `set_video_mode(mode)` - Video output mode control
  - [ ] `get_software_version()` - Enhanced version info

- [ ] **Shutter Control**
  - [ ] `set_shutter_position(position)` - OPEN/CLOSED/AUTO
  - [ ] `get_shutter_position()` - Current position
  - [ ] `set_shutter_temperature_override(temp)` - Manual temp set
  - [ ] Add shutter control to GUI

- [ ] **Enhanced AGC Features**
  - [ ] `set_agc_plateau(histogram_percent)` - Plateau equalization
  - [ ] `set_agc_dampening(factor)` - Temporal smoothing
  - [ ] `set_agc_hi_temp_rejection(enable)` - Ignore hot pixels
  - [ ] Add advanced AGC panel in GUI

- [ ] **System Monitoring**
  - [ ] `get_system_status()` - Overall health status
  - [ ] `get_dsp_software_version()` - DSP firmware version
  - [ ] `get_boot_mode()` - Boot configuration info
  - [ ] Add system diagnostics panel

**Files**: `boson_sdk_wrapper.py`, `boson_sdk_panel.py`
**Documentation**: See `archive/sdk-docs/SDK_GAP_ANALYSIS.md`

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

## 🟢 LOW PRIORITY

### 7. Documentation & Testing

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

## ✅ Recently Completed

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
