# Temperature Units & Hot/Cold Spot Fixes

## Changes Made

### 1. Kelvin Support Added ✅
**File:** `radiometric_converter.py`

**New Methods:**
```python
def celsius_to_kelvin(temp_c: float) -> float:
    """K = C + 273.15"""
    return temp_c + 273.15

def kelvin_to_celsius(temp_k: float) -> float:
    """C = K - 273.15"""
    return temp_k - 273.15
```

**Updated Methods:**
- `convert_temperature()` - Now handles C, F, and K
- `get_temperature_unit_symbol()` - Returns '°C', '°F', or 'K'
- `set_temperature_unit(unit)` - Accepts 'C', 'F', or 'K'

---

## What Still Needs to be Done

### 2. Add Temperature Unit Selector to GUI 🚧
**File:** `radiometric_panel.py`
**Location:** Near the top of the panel

**Add:**
```python
# Temperature Unit Selection
unit_label = QLabel("Temperature Unit:")
self.temp_unit_combo = QComboBox()
self.temp_unit_combo.addItems(['°C (Celsius)', '°F (Fahrenheit)', 'K (Kelvin)'])
self.temp_unit_combo.setCurrentIndex(0)  # Default to Celsius
```

**Signal:**
```python
temp_unit_changed = pyqtSignal(str)  # Emits 'C', 'F', or 'K'
```

---

### 3. Fix Hot/Cold Spots to Show Temperatures 🚧
**Problem:** Hot/cold spots currently show raw AGC values (0-255) when they should show estimated temperatures when 8-bit estimation is enabled

**File:** `inspection_main.py`
**Location:** Around line 1122 where `thermal_analyzer.analyze_frame()` is called

**Current code:**
```python
if self.thermal_analyzer:
    result['thermal_stats'] = self.thermal_analyzer.analyze_frame(thermal_frame)
```

**Needs to become:**
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

            # Mark as radiometric so hot/cold spots show °C
            # (Analyzer will use temperature values directly)
    else:
        # Use raw AGC frame - hot/cold spots will show 0-255 values
        result['thermal_stats'] = self.thermal_analyzer.analyze_frame(thermal_frame)
```

**Also need to update thermal_analyzer config:**
When 8-bit estimation is enabled, set the analyzer's `is_radiometric` flag to True so it knows to use temperature units.

---

### 4. Propagate Temperature Unit Throughout System 🚧

**Files that need updating:**

#### `inspection_main.py`
- Store global `temperature_unit` setting ('C', 'F', or 'K')
- Pass unit to `radiometric_converter` during initialization
- Pass unit to `thermal_estimator` if it needs it
- Pass unit to `thermal_analyzer` config

#### `thermal_estimator.py` (if needed)
- Add `temperature_unit` parameter to constructor
- Convert output temperatures before returning
- Or just always return Celsius and let display layer convert

#### `inspection_gui_qt.py`
- Connect temperature unit combo box signal
- Update all temperature displays when unit changes
- Call `app.set_temperature_unit(unit)` when changed

---

## Implementation Plan

### Phase 1: GUI Unit Selector ✅ (Ready to implement)
1. Add combo box to Radiometric Panel
2. Connect signal to GUI handler
3. GUI handler calls `app.set_temperature_unit(unit)`

### Phase 2: Backend Unit Propagation ✅ (Ready to implement)
1. Add `set_temperature_unit(unit)` method to `inspection_main.py`
2. Update `radiometric_converter` unit
3. Update `thermal_analyzer` config if needed
4. Regenerate temperature displays

### Phase 3: Hot/Cold Spot Temperature Fix 🚧 (Needs code changes)
1. Detect when 8-bit estimation is active
2. Generate temperature map from AGC frame
3. Pass temperature map to `thermal_analyzer`
4. Update `thermal_analyzer` to know it's working with temperatures
5. Hot/cold spots will now show °C values

### Phase 4: Update All Display Code ✅ (Mostly done)
Most displays already use `radiometric_converter.convert_temperature()`, so they'll automatically respect the unit setting once it's propagated.

**Places that display temperatures:**
- Hot spot labels (line 867 in inspection_gui_qt.py)
- Cold spot labels (line 875 in inspection_gui_qt.py)
- ROI temperature stats
- Hardware spot meter
- 8-bit estimation statistics panel
- Calibration displays

---

## Temperature Unit Symbols

| Unit | Symbol | Formula from Celsius |
|------|--------|---------------------|
| Celsius | °C | C |
| Fahrenheit | °F | F = C × 9/5 + 32 |
| Kelvin | K | K = C + 273.15 |

---

## Testing Plan

### Test Unit Conversions
1. Set unit to °C - verify displays show Celsius
2. Set unit to °F - verify conversion: 0°C = 32°F, 100°C = 212°F
3. Set unit to K - verify conversion: 0°C = 273.15K, 100°C = 373.15K

### Test Hot/Cold Spots
**With 8-bit estimation OFF:**
- Hot/cold spots should show raw AGC values (0-255)
- Unit should say "(raw)" not "°C"

**With 8-bit estimation ON:**
- Hot/cold spots should show estimated temperatures
- Unit should show °C, °F, or K depending on setting
- Values should be reasonable (e.g., 20-50°C for indoor scenes)

### Test ROI Analysis
- Draw ROI, verify min/max/avg temps show in correct unit
- Change unit, verify ROI temps update
- Verify per-ROI stats respect global unit setting

---

## Example Usage

```python
# User selects Fahrenheit from dropdown
app.set_temperature_unit('F')

# All displays now show Fahrenheit:
# - Hot spot: "112.5°F" instead of "44.7°C"
# - Cold spot: "68.2°F" instead of "20.1°C"
# - ROI stats: "Min: 65°F, Max: 110°F, Avg: 87.5°F"

# User switches to Kelvin
app.set_temperature_unit('K')

# All displays update:
# - Hot spot: "317.85K" instead of "44.7°C"
# - Cold spot: "293.25K" instead of "20.1°C"
# - ROI stats: "Min: 291.15K, Max: 316.15K, Avg: 303.65K"
```

---

## Next Steps

1. **Add GUI unit selector** - Combo box in Radiometric Panel
2. **Wire up signal chain** - Unit change → backend → display refresh
3. **Fix hot/cold spots** - Use temperature map when 8-bit estimation active
4. **Test thoroughly** - Verify all temperature displays respect unit setting

Would you like me to implement these changes now?
