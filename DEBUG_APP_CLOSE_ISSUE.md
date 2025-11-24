# Debugging Guide for "Application Doesn't Stay Open" Issue

## Problem
After QWidget fixes, `inspection_main.py` doesn't stay open

##Potential Root Causes

### 1. Main Loop Issue (Most Likely)
The application uses `while self.running` loop at line 971 of `inspection_main.py`.
This loop continues until `self.running = False`.

**Check:** Is `self.running` being set to False somewhere?

### 2. No Cameras Connected
If no thermal camera is detected, the loop still runs but may appear to do nothing.
The window should still stay open showing placeholders.

### 3. Qt Event Loop Integration  
Line 1158: Uses `self.qt_app.processEvents()` instead of `qt_app.exec()`.
This is correct for the custom loop architecture.

### 4. Window Close Event
If the window is closed, it might not signal the main loop to stop.

## Quick Diagnostic Commands

```bash
# Test 1: Check if GUI window can be created
python -c "from inspection_gui_qt import InspectionAppWindow; from PyQt6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); win = InspectionAppWindow(); win.show(); print('Window shown')"

# Test 2: Run main app and capture output
python inspection_main.py 2>&1 | tee output.log

# Test 3: Run in headless mode  
python inspection_main.py --headless

# Test 4: Check for runtime errors
python -u inspection_main.py
```

## What to Check

1. **Does the window appear at all?**
   - YES → Window closes immediately (check for early exit)
   - NO → Window never shows (initialization issue)

2. **Any error messages in console?**

3. **Check the debug log:**
   ```bash
   tail -50 thermal_inspection_debug.log
   ```

4. **Are cameras connected?**
   - Thermal camera should be on device 0
   - RGB camera optional

## My Analysis

The QWidget changes I made should NOT cause the application to close:
- Increased widget sizes (non-breaking)
- Added tooltips (non-breaking)
- Standardized spacing (non-breaking) 
- All changes compile successfully

**Hypothesis**: The issue might be pre-existing or unrelated to QWidget fixes.

## Next Steps

Please provide:
1. Exact behavior when running `python inspection_main.py`
2. Any error messages
3. Contents of `thermal_inspection_debug.log` (last 50 lines)
4. Whether you have cameras connected
