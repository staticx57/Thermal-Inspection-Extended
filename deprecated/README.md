# Deprecated Module Archive

**Created:** 2025-12-18  
**Updated:** 2025-12-19  
**Purpose:** Archive of original module files before package restructure

---

## What's Here

This folder contains **64 preserved files** from the original codebase:

1. **Original Full Modules** - The complete implementations before migration
2. **Backward Compatibility Shims** - Small wrapper files that were in root directory

These files are preserved for reference and rollback purposes. **Do NOT import from this folder.**

---

## Current Application Structure

The application now uses:
- **Package location:** `thermal_inspection/` - The authoritative source code
- **CLI Entry Point:** `python -m thermal_inspection`
- All imports should use `from thermal_inspection.module import ...`

---

## Archived Files (64 total)

### Processing/Analysis
- thermal_analyzer.py (shim)
- thermal_processor.py (shim)
- fusion_processor.py (shim)
- roi_manager.py (shim)
- roi_radiometric_analyzer.py (shim)
- palette_manager.py (shim)
- radiometric_converter.py (full)
- isotherm_bands.py (full)
- line_profile_tool.py (full)
- parallax_compensator.py (full)

### Cameras
- flir_camera.py (shim)
- rgb_camera.py (shim)
- rgb_camera_firefly.py (shim)
- rgb_camera_uvc.py (shim)
- camera_backends.py (shim)
- camera_detector.py (shim)
- camera_factory.py (shim)
- camera_registry.py (shim)
- camera_manager.py (full)
- camera_initializer.py (full)
- camera_monitor.py (full)
- camera_calibration.py (full)
- threaded_camera_capture.py (full)
- opencv_thermal_backend.py (full)
- pyusb_thermal_backend.py (full)

### SDK
- boson_sdk_wrapper.py (shim)
- boson_serial.py (shim)
- flirpy_sdk_bridge.py (shim)
- flirpy_thermal_backend.py (shim)
- lepton_sdk_wrapper.py (shim)
- usb_fslp_transport.py (full)

### GUI Panels
- boson_control_panel.py (full)
- boson_sdk_panel.py (full)
- calibration_panel.py (full)
- environmental_compensation_panel.py (full)
- firefly_control_panel.py (full)
- fusion_panel.py (full)
- gradient_overlay_panel.py (full)
- grid_overlay_panel.py (full)
- isotherm_panel.py (full)
- lepton_control_panel.py (full)
- line_profile_panel.py (full)
- parallax_panel.py (full)
- radiometric_panel.py (full)
- roi_temperature_panel.py (full)
- spot_meter_panel.py (full)

### GUI Widgets
- colorbar_widget.py (full)
- multi_row_tabwidget.py (full)
- spot_alert_dialog.py (full)
- temperature_histogram_widget.py (full)

### Utils
- config.py (shim)
- exceptions.py (shim)
- materials.py (shim)
- performance_monitor.py (shim)
- settings_manager.py (shim)
- view_mode.py (shim)
- measurement_points.py (full)
- media_recorder.py (full)
- placeholder_frames.py (full)
- preset_manager.py (full)
- radiometric_calibration.py (full)
- spot_meter_exporter.py (full)
- thermal_estimator.py (full)

---

## File Types

- **Shim files** (~300-700 bytes): Small re-export wrappers, safe to delete
- **Full files** (~5KB-50KB): Complete original implementations, kept for reference

---

## Recovery Instructions

If you need to restore old functionality:

1. Copy the needed file(s) back to the root directory
2. Ensure the `thermal_inspection/` package is NOT in PYTHONPATH for that file
3. Old import paths will work again

**Recommended:** Use the new package paths instead (`from thermal_inspection.module import ...`)

---

## Safe to Delete When

This folder can be safely deleted once:
1. ✅ All imports verified working with package paths
2. ✅ 127/127 unit tests passing
3. ⏳ External tools updated to use new paths
4. ⏳ Deprecation warning period passed (suggested: 30 days)
