# Signal Connection Audit

## Signals Defined in radiometric_panel.py

1. `spotmeter_enabled_changed = pyqtSignal(bool)` - Line 30
2. `spotmeter_mode_changed = pyqtSignal(str)` - Line 31
3. `sensor_temps_requested = pyqtSignal()` - Line 32
4. `estimation_8bit_enabled_changed = pyqtSignal(bool)` - Line 35
5. `temperature_range_changed = pyqtSignal(float, float)` - Line 36
6. `calibrate_single_point_requested = pyqtSignal()` - Line 37
7. `calibrate_two_point_requested = pyqtSignal()` - Line 38

## Expected Connections in inspection_gui_qt.py

Checking which signals are connected...
