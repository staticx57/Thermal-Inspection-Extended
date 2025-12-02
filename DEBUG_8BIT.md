# Debugging: Enable 8-Bit Estimation Not Interactive

## Signal Chain Analysis

### 1. Checkbox Definition (radiometric_panel.py:164-172)
```python
self.enable_8bit_checkbox = QCheckBox("Enable 8-Bit Estimation")
self.enable_8bit_checkbox.setEnabled(False)  # Initially disabled
self.enable_8bit_checkbox.toggled.connect(self.estimation_8bit_enabled_changed.emit)
```
✅ Checkbox emits panel signal

### 2. Panel Signal Definition (radiometric_panel.py:35)
```python
estimation_8bit_enabled_changed = pyqtSignal(bool)
```
✅ Signal defined

### 3. Enable Controls (radiometric_panel.py:508-522)
```python
def set_8bit_estimation_available(self, available: bool, auto_enabled: bool = False):
    self.enable_8bit_checkbox.setEnabled(available)  # Enables checkbox
    self.apply_scene_range_btn.setEnabled(available)
    self.single_point_calib_btn.setEnabled(available)
    self.two_point_calib_btn.setEnabled(available)
    
    if auto_enabled:
        self.enable_8bit_checkbox.setChecked(True)  # Auto-checks it
```
✅ Method enables controls

### 4. GUI Signal Connection (inspection_gui_qt.py:5021)
```python
self._safe_connect("radiometric_panel", "estimation_8bit_enabled_changed", 
                   self._on_8bit_estimation_toggled, "(radiometric 8-bit)")
```
✅ Panel signal connected to GUI handler

### 5. GUI Handler (inspection_gui_qt.py:5231-5244)
```python
def _on_8bit_estimation_toggled(self, enabled: bool):
    if self.app and hasattr(self.app, 'set_8bit_estimation_enabled'):
        self.app.set_8bit_estimation_enabled(enabled)
        logger.info(f"8-bit temperature estimation: {'enabled' if enabled else 'disabled'}")
        
        # Update status banner
        if hasattr(self.radiometric_panel, 'update_active_mode_status'):
            mode_info = self.app.get_active_temperature_mode()
            self.radiometric_panel.update_active_mode_status(...)
```
✅ Handler calls app method

## WAIT - POTENTIAL ISSUE FOUND!

Look at line 5021: `self._safe_connect("radiometric_panel", ...)`

But in `_build_ui` (line 4738):
```python
self.radiometric_panel = self.analysis_panel.radiometric_panel_general
```

**The panel is NESTED!** It's `self.analysis_panel.radiometric_panel_general`, not directly `self.radiometric_panel`.

The connection is trying to access `self.radiometric_panel` but the alias might not be set yet when signals connect!

## Solution

Check if `self.radiometric_panel` exists when `_connect_signals()` is called.
