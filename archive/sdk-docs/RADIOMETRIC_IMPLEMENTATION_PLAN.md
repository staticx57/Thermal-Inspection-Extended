# Radiometric Temperature Implementation Plan

## Overview

Implement radiometric temperature measurement for FLIR Boson cameras that support 16-bit absolute temperature output. This enables precise temperature readings for thermal inspection applications.

---

## Current Status

### ✅ What's Working
- 16-bit frame detection (dtype check in `flir_camera.py:154-187`)
- Basic frame normalization for display
- FPA temperature monitoring
- Non-radiometric Boson support

### ⏳ What's Missing
- Radiometric camera detection
- 16-bit to temperature conversion
- TLinear lookup table functions
- Spot temperature measurement
- Temperature calibration
- Radiometric mode enable/disable

---

## Implementation Phases

### Phase 1: Radiometric Detection & Mode Setup

**Goal**: Detect if camera is radiometric and enable the mode

**Files to Modify**:
- `flir_camera.py` - Add radiometric detection
- `boson_sdk_wrapper.py` - Add radiometric control functions

**Tasks**:
1. Detect radiometric capability via SDK
2. Add method to enable/disable radiometric mode
3. Store radiometric status in camera object
4. Update GUI to show radiometric status

**Implementation**:
```python
# In boson_sdk_wrapper.py
def is_radiometric_capable(self) -> bool:
    """Check if camera supports radiometric mode"""
    if not self.is_connected():
        return False

    try:
        # Check camera part number for radiometric indicator
        info = self.get_camera_info()
        if info and info.camera_part_number:
            # Radiometric Bosons have 'R' in part number
            return 'R' in info.camera_part_number.upper()
        return False
    except Exception as e:
        logger.error(f"Error checking radiometric capability: {e}")
        return False

def enable_radiometric_mode(self) -> bool:
    """Enable radiometric temperature output"""
    if not self.is_connected():
        return False

    try:
        # Set to RAW14 or TLINEAR mode
        # This depends on SDK version and camera model
        # May need to use undocumented functions
        logger.info("Attempting to enable radiometric mode...")

        # Method 1: Try via transfer function
        # result = self.send_command(FUNC_TRANSFER_GET_MODE)

        # Method 2: Check current output format
        # If already in 16-bit mode, radiometric may be active

        return True
    except Exception as e:
        logger.error(f"Error enabling radiometric mode: {e}")
        return False
```

### Phase 2: Temperature Conversion

**Goal**: Convert 16-bit pixel values to actual temperatures

**Conversion Methods**:

#### Method 1: Linear Approximation (Simple, less accurate)
```python
def pixel_to_temperature_linear(pixel_value: int, min_temp: float = -40.0, max_temp: float = 550.0) -> float:
    """
    Convert 16-bit pixel value to temperature using linear scaling

    Args:
        pixel_value: Raw 16-bit value (0-65535)
        min_temp: Minimum temperature in Celsius
        max_temp: Maximum temperature in Celsius

    Returns:
        Temperature in Celsius
    """
    # Normalize to 0-1
    normalized = pixel_value / 65535.0

    # Scale to temperature range
    temperature = min_temp + (normalized * (max_temp - min_temp))

    return temperature
```

#### Method 2: TLinear Lookup Table (Accurate, requires calibration)
```python
class TLinearConverter:
    """
    Converts raw radiometric pixel values to temperature using TLinear LUT

    The TLinear (Temperature Linear) lookup table provides accurate
    pixel-to-temperature conversion specific to each camera.
    """

    def __init__(self):
        self.lut = None
        self.lut_size = 0
        self.min_value = 0
        self.max_value = 65535

    def load_lut_from_camera(self, sdk: BosonSDK) -> bool:
        """
        Load TLinear LUT from camera via SDK

        Note: This requires SDK functions that may not be in boson_serial
        May need to use direct register access or file-based LUT
        """
        try:
            # Attempt to get LUT from camera
            # This is camera-specific and may require manufacturer support
            logger.info("Loading TLinear LUT from camera...")

            # Placeholder - actual implementation depends on SDK version
            # lut_data = sdk.get_tlinear_lut()

            return False  # Not yet implemented
        except Exception as e:
            logger.error(f"Error loading TLinear LUT: {e}")
            return False

    def load_lut_from_file(self, filepath: str) -> bool:
        """
        Load TLinear LUT from calibration file

        File format: CSV or binary with pixel_value -> temperature mapping
        """
        try:
            import csv
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header

                lut_dict = {}
                for row in reader:
                    pixel_val = int(row[0])
                    temp_c = float(row[1])
                    lut_dict[pixel_val] = temp_c

            self.lut = lut_dict
            self.lut_size = len(lut_dict)
            logger.info(f"Loaded TLinear LUT with {self.lut_size} entries")
            return True

        except Exception as e:
            logger.error(f"Error loading LUT from file: {e}")
            return False

    def pixel_to_temperature(self, pixel_value: int) -> Optional[float]:
        """
        Convert pixel value to temperature using LUT

        Args:
            pixel_value: 16-bit raw value

        Returns:
            Temperature in Celsius, or None if LUT not loaded
        """
        if self.lut is None:
            return None

        # Direct lookup
        if pixel_value in self.lut:
            return self.lut[pixel_value]

        # Interpolate if exact value not in LUT
        keys = sorted(self.lut.keys())
        if pixel_value < keys[0]:
            return self.lut[keys[0]]
        if pixel_value > keys[-1]:
            return self.lut[keys[-1]]

        # Find surrounding values and interpolate
        for i in range(len(keys) - 1):
            if keys[i] <= pixel_value <= keys[i+1]:
                # Linear interpolation
                x0, x1 = keys[i], keys[i+1]
                y0, y1 = self.lut[x0], self.lut[x1]
                t = (pixel_value - x0) / (x1 - x0)
                return y0 + t * (y1 - y0)

        return None

    def convert_frame(self, frame_16bit: np.ndarray) -> np.ndarray:
        """
        Convert entire 16-bit frame to temperature array

        Args:
            frame_16bit: (H, W) uint16 array

        Returns:
            (H, W) float32 array in Celsius
        """
        if self.lut is None:
            # Fallback to linear approximation
            return frame_16bit.astype(np.float32) / 65535.0 * 590 - 40

        # Vectorized LUT lookup
        temp_frame = np.zeros_like(frame_16bit, dtype=np.float32)

        for pixel_val in np.unique(frame_16bit):
            mask = (frame_16bit == pixel_val)
            temp = self.pixel_to_temperature(pixel_val)
            if temp is not None:
                temp_frame[mask] = temp

        return temp_frame
```

### Phase 3: Spot Temperature Measurement

**Goal**: Get temperature at specific pixel coordinates

```python
# In flir_camera.py or thermal_analyzer.py

def get_spot_temperature(self, frame_16bit: np.ndarray, x: int, y: int,
                        converter: TLinearConverter) -> Optional[float]:
    """
    Get temperature at specific pixel location

    Args:
        frame_16bit: Raw 16-bit frame
        x, y: Pixel coordinates
        converter: TLinear converter instance

    Returns:
        Temperature in Celsius, or None if radiometric not available
    """
    if frame_16bit is None or frame_16bit.dtype != np.uint16:
        return None

    if not (0 <= y < frame_16bit.shape[0] and 0 <= x < frame_16bit.shape[1]):
        return None

    pixel_value = frame_16bit[y, x]
    temperature = converter.pixel_to_temperature(pixel_value)

    return temperature


def get_roi_temperature_stats(self, frame_16bit: np.ndarray, roi_mask: np.ndarray,
                              converter: TLinearConverter) -> dict:
    """
    Get temperature statistics for ROI

    Returns:
        {
            'min_temp': float,
            'max_temp': float,
            'mean_temp': float,
            'std_temp': float,
            'min_location': (x, y),
            'max_location': (x, y)
        }
    """
    if frame_16bit is None or frame_16bit.dtype != np.uint16:
        return None

    # Convert ROI pixels to temperature
    roi_pixels = frame_16bit[roi_mask > 0]
    roi_temps = np.array([converter.pixel_to_temperature(p) for p in roi_pixels
                         if converter.pixel_to_temperature(p) is not None])

    if len(roi_temps) == 0:
        return None

    # Find min/max locations
    min_temp = roi_temps.min()
    max_temp = roi_temps.max()

    temp_frame = converter.convert_frame(frame_16bit)
    min_y, min_x = np.unravel_index(temp_frame.argmin(), temp_frame.shape)
    max_y, max_x = np.unravel_index(temp_frame.argmax(), temp_frame.shape)

    return {
        'min_temp': float(min_temp),
        'max_temp': float(max_temp),
        'mean_temp': float(roi_temps.mean()),
        'std_temp': float(roi_temps.std()),
        'min_location': (int(min_x), int(min_y)),
        'max_location': (int(max_x), int(max_y))
    }
```

### Phase 4: GUI Integration

**Goal**: Display real-time temperature readings in GUI

**New GUI Elements**:
```python
# In inspection_gui_qt.py or new radiometric_panel.py

class RadiometricPanel(QGroupBox):
    """Panel for radiometric temperature display and controls"""

    def __init__(self, parent=None):
        super().__init__("🌡️ Radiometric Temperature", parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()

        # Status
        self.status_label = QLabel("Radiometric: Not Available")
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)

        # Enable/Disable
        self.enable_checkbox = QCheckBox("Enable Radiometric Mode")
        self.enable_checkbox.setEnabled(False)
        layout.addWidget(self.enable_checkbox)

        # Spot temperature (cursor position)
        spot_group = QGroupBox("Spot Temperature (Cursor)")
        spot_layout = QFormLayout()

        self.cursor_x_label = QLabel("--")
        self.cursor_y_label = QLabel("--")
        self.cursor_temp_label = QLabel("--°C")
        self.cursor_temp_label.setStyleSheet("font-size: 14pt; font-weight: bold;")

        spot_layout.addRow("X:", self.cursor_x_label)
        spot_layout.addRow("Y:", self.cursor_y_label)
        spot_layout.addRow("Temperature:", self.cursor_temp_label)

        spot_group.setLayout(spot_layout)
        layout.addWidget(spot_group)

        # Center spot (crosshair)
        center_group = QGroupBox("Center Spot")
        center_layout = QFormLayout()

        self.center_temp_label = QLabel("--°C")
        self.center_temp_label.setStyleSheet("font-size: 14pt; font-weight: bold;")

        center_layout.addRow("Temperature:", self.center_temp_label)
        center_group.setLayout(center_layout)
        layout.addWidget(center_group)

        # Temperature range
        range_group = QGroupBox("Frame Temperature Range")
        range_layout = QFormLayout()

        self.min_temp_label = QLabel("--°C")
        self.max_temp_label = QLabel("--°C")
        self.mean_temp_label = QLabel("--°C")

        range_layout.addRow("Minimum:", self.min_temp_label)
        range_layout.addRow("Maximum:", self.max_temp_label)
        range_layout.addRow("Average:", self.mean_temp_label)

        range_group.setLayout(range_layout)
        layout.addWidget(range_group)

        layout.addStretch()
        self.setLayout(layout)

    def set_radiometric_status(self, available: bool, enabled: bool):
        """Update radiometric status"""
        if available:
            if enabled:
                self.status_label.setText("✅ Radiometric: Enabled")
                self.status_label.setStyleSheet("color: #0a0; font-weight: bold;")
            else:
                self.status_label.setText("⚫ Radiometric: Available (Disabled)")
                self.status_label.setStyleSheet("color: #666; font-weight: bold;")
            self.enable_checkbox.setEnabled(True)
        else:
            self.status_label.setText("❌ Radiometric: Not Available")
            self.status_label.setStyleSheet("color: #999; font-weight: bold;")
            self.enable_checkbox.setEnabled(False)

    def update_spot_temperature(self, x: int, y: int, temperature: float):
        """Update cursor spot temperature"""
        self.cursor_x_label.setText(str(x))
        self.cursor_y_label.setText(str(y))
        self.cursor_temp_label.setText(f"{temperature:.1f}°C")

    def update_frame_statistics(self, min_temp: float, max_temp: float, mean_temp: float):
        """Update frame temperature statistics"""
        self.min_temp_label.setText(f"{min_temp:.1f}°C")
        self.max_temp_label.setText(f"{max_temp:.1f}°C")
        self.mean_temp_label.setText(f"{mean_temp:.1f}°C")
```

### Phase 5: Calibration & Testing

**Goal**: Calibrate and validate temperature accuracy

**Calibration Process**:
1. Use known temperature references (ice water = 0°C, boiling water = 100°C)
2. Measure pixel values at known temperatures
3. Create calibration curve
4. Compare with factory TLinear LUT (if available)
5. Document accuracy (±2°C typical for Boson)

**Calibration Tool**:
```python
class RadiometricCalibration:
    """Tool for calibrating radiometric temperature conversion"""

    def __init__(self):
        self.reference_points = []  # List of (pixel_value, known_temp)

    def add_reference_point(self, pixel_value: int, known_temp: float):
        """Add calibration point"""
        self.reference_points.append((pixel_value, known_temp))
        logger.info(f"Added calibration point: {pixel_value} -> {known_temp}°C")

    def compute_linear_fit(self) -> Tuple[float, float]:
        """
        Compute linear fit: temp = slope * pixel + offset

        Returns:
            (slope, offset) tuple
        """
        if len(self.reference_points) < 2:
            raise ValueError("Need at least 2 reference points for calibration")

        pixels = np.array([p[0] for p in self.reference_points])
        temps = np.array([p[1] for p in self.reference_points])

        # Linear regression
        slope, offset = np.polyfit(pixels, temps, 1)

        logger.info(f"Calibration: temp = {slope:.6f} * pixel + {offset:.2f}")
        return (slope, offset)

    def save_calibration(self, filepath: str):
        """Save calibration to file"""
        with open(filepath, 'w') as f:
            f.write("# Radiometric Calibration\n")
            f.write(f"# Generated: {datetime.now()}\n")
            f.write("# pixel_value,temperature_celsius\n")

            for pixel_val, temp in sorted(self.reference_points):
                f.write(f"{pixel_val},{temp}\n")

        logger.info(f"Calibration saved to {filepath}")
```

---

## File Structure

```
Thermal-Inspection/
├── radiometric_converter.py       # NEW - TLinear converter
├── radiometric_panel.py           # NEW - GUI panel
├── radiometric_calibration.py     # NEW - Calibration tools
├── flir_camera.py                 # MODIFY - Add radiometric support
├── boson_sdk_wrapper.py           # MODIFY - Add radiometric functions
├── thermal_analyzer.py            # MODIFY - Add temp measurement
├── inspection_gui_qt.py           # MODIFY - Integrate panel
├── calibration/
│   ├── tlinear_default.csv        # Default TLinear LUT
│   └── calibration_*.json         # User calibration files
└── tests/
    └── test_radiometric.py        # Unit tests
```

---

## Implementation Order

### Week 1: Foundation
1. Create `radiometric_converter.py` with basic pixel-to-temp conversion
2. Modify `flir_camera.py` to preserve 16-bit data (don't normalize)
3. Add radiometric detection to `boson_sdk_wrapper.py`
4. Test with 16-bit frame capture

### Week 2: Temperature Measurement
1. Implement spot temperature measurement
2. Implement ROI temperature statistics
3. Add temperature overlay on display
4. Test accuracy with known temperatures

### Week 3: GUI Integration
1. Create `radiometric_panel.py`
2. Integrate into main GUI
3. Add cursor temperature tracking (mouseover)
4. Add center crosshair with temperature

### Week 4: Calibration
1. Create calibration tool
2. Generate default TLinear LUT
3. Document calibration procedure
4. Validate accuracy

### Week 5: Polish & Documentation
1. Add user guide for radiometric features
2. Create calibration tutorial
3. Add temperature export (CSV with temps, not just pixel values)
4. Performance optimization

---

## Testing Requirements

### Unit Tests
- Pixel-to-temperature conversion accuracy
- LUT loading and lookup
- Frame conversion performance
- ROI temperature statistics

### Integration Tests
- Enable/disable radiometric mode
- GUI temperature display updates
- Temperature logging
- Export temperature data

### Validation Tests
- Known temperature references (0°C, 100°C)
- Thermal gradient accuracy
- ROI measurement consistency
- Long-term stability

---

## Performance Considerations

### Optimization Strategies
1. **Vectorized Conversion**: Use NumPy for frame conversion (avoid loops)
2. **LUT Caching**: Pre-compute common pixel values
3. **Partial Frame**: Only convert ROI regions, not entire frame
4. **Update Rate**: Update temperature display at 5-10 Hz, not full frame rate
5. **Threading**: Convert temperature in background thread

**Expected Performance**:
- Frame conversion: < 10ms (640x512 on CPU)
- Spot temperature: < 1ms
- ROI statistics: < 5ms (typical ROI size)

---

## User Documentation Outline

### Quick Start
1. Check if camera is radiometric
2. Enable radiometric mode
3. View spot temperature (cursor)
4. Measure ROI temperatures
5. Export temperature data

### Calibration Guide
1. Prepare reference temperatures
2. Capture reference frames
3. Run calibration tool
4. Validate accuracy
5. Save calibration file

### Troubleshooting
- "Radiometric Not Available" → Check camera model
- Inaccurate readings → Recalibrate or check references
- Poor performance → Reduce update rate

---

## Success Criteria

✅ **Must Have**:
- Detect radiometric capability
- Convert 16-bit pixels to temperature
- Display spot temperature (cursor)
- Measure ROI temperature statistics
- Export temperature data

⭐ **Nice to Have**:
- TLinear LUT from camera
- User calibration tool
- Temperature heatmap overlay
- Historical temperature tracking

---

## References

- FLIR Boson Radiometric Mode Application Note
- Teledyne FLIR SDK Documentation
- "Radiometric Calibration of Microbolometer Cameras" (technical paper)

---

**Document Version**: 1.0
**Date**: 2025-11-25
**Status**: Ready for Implementation
**Next Step**: Create `radiometric_converter.py` with basic conversion
