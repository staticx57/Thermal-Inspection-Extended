# Hot/Cold Spot Temperature Conversion & Configurable Spot Count

## Summary

This document summarizes the completed implementation of:
1. **Temperature unit conversion for hot/cold spots** - Ensures displayed values match selected unit (°C, °F, K)
2. **Configurable hot/cold spot count** - User can select how many spots to display (1, 2, 3, 5, 10, 20)

---

## 1. Temperature Unit Conversion for Hot/Cold Spots ✅

### Problem
Hot/cold spots were displaying raw Celsius values with temperature unit symbols but not actually converting the values when Fahrenheit or Kelvin was selected.

**Example of bug:**
- Selected unit: Fahrenheit
- Hot spot displayed: "44.7°F" (should be "112.5°F")
- The value was still Celsius, just with the wrong symbol

### Solution
Added `_format_temperature_with_unit()` helper method in `inspection_gui_qt.py` that:
1. Accesses the `radiometric_converter` from the app
2. Converts temperature using `converter.convert_temperature(temp_celsius)`
3. Gets the proper unit symbol using `converter.get_temperature_unit_symbol()`
4. Returns the converted value with correct symbol

### Implementation Details

**File:** `inspection_gui_qt.py`

**Helper Method (lines 770-797):**
```python
def _format_temperature_with_unit(self, temp_celsius: float, original_unit: str) -> tuple:
    """Convert temperature from Celsius to current unit and return with unit symbol."""
    # If it's raw AGC value, don't convert
    if "(raw)" in original_unit:
        return (temp_celsius, original_unit)

    # Get radiometric converter from app
    if self.parent() and hasattr(self.parent(), 'app') and self.parent().app:
        app = self.parent().app
        if hasattr(app, 'thermal_camera') and app.thermal_camera:
            if hasattr(app.thermal_camera, 'radiometric_converter'):
                converter = app.thermal_camera.radiometric_converter
                if converter:
                    converted_temp = converter.convert_temperature(temp_celsius)
                    unit_symbol = converter.get_temperature_unit_symbol()
                    return (converted_temp, unit_symbol)

    # Fallback: return Celsius
    return (temp_celsius, "°C")
```

**Usage in paintEvent (lines 867-868, 875-878):**
```python
# Hot spots
temp_c, unit_symbol = self._format_temperature_with_unit(hot_spot.max_temp, hot_spot.unit)
draw_label(int(wx) + 10, int(wy), f"{temp_c:.1f}{unit_symbol}", QColor(255, 100, 100))

# Cold spots
temp_c, unit_symbol = self._format_temperature_with_unit(cold_spot.min_temp, cold_spot.unit)
draw_label(int(wx) + 10, int(wy), f"{temp_c:.1f}{unit_symbol}", QColor(100, 100, 255))
```

### Result
Hot/cold spot labels now display temperatures in the selected unit:
- **Celsius:** "44.7°C"
- **Fahrenheit:** "112.5°F"
- **Kelvin:** "317.85K"

---

## 2. Configurable Hot/Cold Spot Count ✅

### Feature Overview
Users can now control how many hot and cold spots are displayed, ranging from 1 to 20 spots.

### GUI Controls

**File:** `radiometric_panel.py` (lines 116-143)

**Hot Spot Control:**
```python
# Max hot spots
hot_spot_layout = QHBoxLayout()
hot_spot_layout.addWidget(QLabel("Max Hot Spots:"))
self.max_hot_spots_spin = QComboBox()
self.max_hot_spots_spin.addItems(['1', '2', '3', '5', '10', '20'])
self.max_hot_spots_spin.setCurrentIndex(2)  # Default to 3
self.max_hot_spots_spin.setToolTip("Maximum number of hot spots to display")
self.max_hot_spots_spin.currentIndexChanged.connect(self._on_max_hot_spots_changed)
```

**Cold Spot Control:**
```python
# Max cold spots
cold_spot_layout = QHBoxLayout()
cold_spot_layout.addWidget(QLabel("Max Cold Spots:"))
self.max_cold_spots_spin = QComboBox()
self.max_cold_spots_spin.addItems(['1', '2', '3', '5', '10', '20'])
self.max_cold_spots_spin.setCurrentIndex(2)  # Default to 3
self.max_cold_spots_spin.setToolTip("Maximum number of cold spots to display")
self.max_cold_spots_spin.currentIndexChanged.connect(self._on_max_cold_spots_changed)
```

### Signal Chain

**1. Panel Handlers** (`radiometric_panel.py`, lines 513-531)
```python
def _on_max_hot_spots_changed(self, index: int):
    """Handle max hot spots combo box change."""
    try:
        count = int(self.max_hot_spots_spin.currentText())
        logger.info(f"[DEBUG] Max hot spots changed to: {count}")
        self.max_hot_spots_changed.emit(count)
        logger.info(f"[DEBUG] Signal emitted successfully for hot spots: {count}")
    except Exception as e:
        logger.error(f"[ERROR] Exception in _on_max_hot_spots_changed: {e}", exc_info=True)

def _on_max_cold_spots_changed(self, index: int):
    """Handle max cold spots combo box change."""
    try:
        count = int(self.max_cold_spots_spin.currentText())
        logger.info(f"[DEBUG] Max cold spots changed to: {count}")
        self.max_cold_spots_changed.emit(count)
        logger.info(f"[DEBUG] Signal emitted successfully for cold spots: {count}")
    except Exception as e:
        logger.error(f"[ERROR] Exception in _on_max_cold_spots_changed: {e}", exc_info=True)
```

**2. Signal Definitions** (`radiometric_panel.py`, lines 44-45)
```python
max_hot_spots_changed = pyqtSignal(int)   # Emits new max hot spots count
max_cold_spots_changed = pyqtSignal(int)  # Emits new max cold spots count
```

**3. Signal Connections** (`inspection_gui_qt.py`, lines 2028-2030)
```python
self.radiometric_panel.max_hot_spots_changed.connect(self._on_max_hot_spots_changed)
self.radiometric_panel.max_cold_spots_changed.connect(self._on_max_cold_spots_changed)
```

**4. GUI Handlers** (`inspection_gui_qt.py`, lines 2115-2141)
```python
def _on_max_hot_spots_changed(self, count: int):
    """Handle max hot spots count change from radiometric panel."""
    try:
        logger.info(f"[DEBUG] GUI received max_hot_spots signal: {count}")
        # Access app through parent window
        window = self.window()
        if window and hasattr(window, 'app') and window.app:
            window.app.set_max_hot_spots(count)
            logger.info(f"[DEBUG] app.set_max_hot_spots({count}) completed")
        else:
            logger.warning("[DEBUG] Cannot set max hot spots: window or app not found")
    except Exception as e:
        logger.error(f"[ERROR] Exception in _on_max_hot_spots_changed: {e}", exc_info=True)

def _on_max_cold_spots_changed(self, count: int):
    """Handle max cold spots count change from radiometric panel."""
    try:
        logger.info(f"[DEBUG] GUI received max_cold_spots signal: {count}")
        # Access app through parent window
        window = self.window()
        if window and hasattr(window, 'app') and window.app:
            window.app.set_max_cold_spots(count)
            logger.info(f"[DEBUG] app.set_max_cold_spots({count}) completed")
        else:
            logger.warning("[DEBUG] Cannot set max cold spots: window or app not found")
    except Exception as e:
        logger.error(f"[ERROR] Exception in _on_max_cold_spots_changed: {e}", exc_info=True)
```

**Note:** These handlers are in the `ThermalAnalysisPanel` class, which doesn't have direct access to `self.app`. They access the app through `self.window()` which returns the parent `InspectionAppWindow` instance.

**5. Backend Methods** (`inspection_main.py`, lines 3846-3876)
```python
def set_max_hot_spots(self, count: int):
    """
    Set maximum number of hot spots to display.

    Args:
        count: Maximum number of hot spots (1-20)
    """
    try:
        if self.thermal_analyzer:
            self.thermal_analyzer.max_hot_spots = count
            logger.info(f"Max hot spots set to: {count}")
        else:
            logger.warning("Cannot set max hot spots: thermal analyzer not initialized")
    except Exception as e:
        logger.error(f"Error setting max hot spots: {e}")

def set_max_cold_spots(self, count: int):
    """
    Set maximum number of cold spots to display.

    Args:
        count: Maximum number of cold spots (1-20)
    """
    try:
        if self.thermal_analyzer:
            self.thermal_analyzer.max_cold_spots = count
            logger.info(f"Max cold spots set to: {count}")
        else:
            logger.warning("Cannot set max cold spots: thermal analyzer not initialized")
    except Exception as e:
        logger.error(f"Error setting max cold spots: {e}")
```

### Detection Limiting

**File:** `thermal_analyzer.py`

**Hot Spot Detection (lines 333-335):**
```python
# Sort by max temperature (hottest first)
hot_spots.sort(key=lambda x: x.max_temp, reverse=True)

# Limit to max_hot_spots (0 means no limit)
if self.max_hot_spots > 0 and len(hot_spots) > self.max_hot_spots:
    hot_spots = hot_spots[:self.max_hot_spots]

return hot_spots
```

**Cold Spot Detection (lines 413-415):**
```python
# Sort by min temperature (coldest first)
cold_spots.sort(key=lambda x: x.min_temp)

# Limit to max_cold_spots (0 means no limit)
if self.max_cold_spots > 0 and len(cold_spots) > self.max_cold_spots:
    cold_spots = cold_spots[:self.max_cold_spots]

return cold_spots
```

### Debugging Infrastructure

All handlers include comprehensive error handling:
- **Try-except blocks** at every level (panel, GUI, backend)
- **Debug logging** before and after operations
- **Full stack traces** with `exc_info=True`
- **Warnings** when components aren't initialized

This allows tracking exactly where any issues occur if the feature doesn't work as expected.

---

## Design Decisions

### 1. Why No "All" Option?
The "All" option was removed because:
- Hot/cold spots are detected **regions (blobs)**, not individual pixels
- Showing all regions could mean dozens or hundreds of spots, making the display unusable
- The feature is meant to highlight the most significant thermal anomalies
- Maximum of 20 provides enough flexibility without overwhelming the display

### 2. Why These Specific Values? (1, 2, 3, 5, 10, 20)
- **1-3:** Common use cases for highlighting single or few most significant spots
- **5:** Good balance for industrial inspection (catching multiple anomalies)
- **10:** Higher detail for complex scenes
- **20:** Maximum useful number before display becomes cluttered

### 3. Temperature Storage Convention
- All temperatures stored internally as **Celsius**
- Conversion happens at **display time only**
- This ensures consistency across the codebase
- The `radiometric_converter` handles all conversions centrally

---

## Files Modified

### Core Implementation
1. **inspection_gui_qt.py**
   - Added `_format_temperature_with_unit()` helper method
   - Modified hot/cold spot drawing to convert temperatures
   - Added signal handlers for spot count controls
   - Added extensive debugging infrastructure

2. **radiometric_panel.py**
   - Added temperature unit combo box
   - Added hot/cold spot count controls
   - Added signal definitions
   - Added panel handlers with error handling

3. **inspection_main.py**
   - Added `set_max_hot_spots()` method
   - Added `set_max_cold_spots()` method
   - Enhanced error handling and logging

4. **thermal_analyzer.py**
   - Added `max_hot_spots` config parameter (default: 3)
   - Added `max_cold_spots` config parameter (default: 3)
   - Updated detection methods to limit results

---

## Testing

### Temperature Conversion Testing
1. **Test Celsius:**
   - Select °C from dropdown
   - Hot spot should show e.g., "44.7°C"
   - Cold spot should show e.g., "20.1°C"

2. **Test Fahrenheit:**
   - Select °F from dropdown
   - Hot spot should show e.g., "112.5°F" (not "44.7°F")
   - Cold spot should show e.g., "68.2°F" (not "20.1°F")

3. **Test Kelvin:**
   - Select K from dropdown
   - Hot spot should show e.g., "317.85K"
   - Cold spot should show e.g., "293.25K"

### Spot Count Testing
1. **Test Hot Spot Count:**
   - Set max hot spots to 1 - verify only 1 hot spot displays
   - Set max hot spots to 5 - verify up to 5 hot spots display
   - Set max hot spots to 20 - verify up to 20 hot spots display

2. **Test Cold Spot Count:**
   - Set max cold spots to 1 - verify only 1 cold spot displays
   - Set max cold spots to 5 - verify up to 5 cold spots display
   - Set max cold spots to 20 - verify up to 20 cold spots display

3. **Test Independent Controls:**
   - Set hot spots to 1, cold spots to 10
   - Verify 1 hot spot and 10 cold spots display independently

### Debug Output Monitoring
If issues occur, check `thermal_inspection_debug.log` for:
- `[DEBUG] Max hot/cold spots changed to: X`
- `[DEBUG] Signal emitted successfully`
- `[DEBUG] GUI received signal`
- `[DEBUG] app.set_max_X_spots() completed`
- Any `[ERROR]` messages with stack traces

---

## Current Status

### ✅ Completed
- Temperature unit conversion for hot/cold spots
- Configurable hot/cold spot count (1-20)
- Full signal chain from GUI to backend
- Comprehensive error handling and debugging
- Fixed handler access to app through parent window
- Documentation

### ✅ Bug Fixes Applied
**Issue:** Handler methods couldn't access app instance
- **Error:** `'ThermalAnalysisPanel' object has no attribute 'app'`
- **Root Cause:** Handlers were in `ThermalAnalysisPanel` class which doesn't have direct access to `self.app`
- **Fix:** Changed handlers to access app through parent window using `self.window()`
- **Result:** Handlers now properly call `window.app.set_max_hot_spots()` and `window.app.set_max_cold_spots()`
- **Tested:** User confirmed no crashes when setting values to 5 and 20

### 🧪 Ready for Testing
- Test that changing spot count actually changes the number of spots displayed
- Monitor debug log for successful backend method calls
- Confirm temperature conversion works across all units

---

## Next Steps (from TEMPERATURE_UNITS_AND_HOT_COLD_SPOTS.md)

### Phase 3: Hot/Cold Spot Temperature Fix 🚧 (Still Pending)
When 8-bit temperature estimation is active, hot/cold spots should analyze the temperature-converted frame instead of the raw AGC frame.

**Required changes in `inspection_main.py` (around line 1122):**
```python
if self.thermal_analyzer:
    # Use temperature-converted frame if 8-bit estimation is active
    if self.temp_estimation_enabled and self.temp_estimator:
        # Get FPA temperature
        fpa_temp_result = self.thermal_camera.get_fpa_temperature()
        if fpa_temp_result:
            fpa_temp_c = fpa_temp_result[1]

            # Convert AGC frame to temperature map
            temp_map = self.temp_estimator.estimate_temperature_map(
                thermal_frame,
                fpa_temp_c
            )

            # Analyze temperature map instead of AGC frame
            result['thermal_stats'] = self.thermal_analyzer.analyze_frame(temp_map)
    else:
        # Use raw AGC frame - hot/cold spots will show 0-255 values
        result['thermal_stats'] = self.thermal_analyzer.analyze_frame(thermal_frame)
```

This ensures hot/cold spots show actual estimated temperatures (e.g., "25.3°C") instead of raw AGC values (e.g., "127 (raw)") when 8-bit estimation is enabled.

---

## References

- **TEMPERATURE_UNITS_AND_HOT_COLD_SPOTS.md** - Original implementation plan
- **radiometric_converter.py** - Temperature conversion engine
- **thermal_analyzer.py** - Hot/cold spot detection
- **inspection_gui_qt.py** - Display and user interaction
- **radiometric_panel.py** - Radiometric controls GUI
