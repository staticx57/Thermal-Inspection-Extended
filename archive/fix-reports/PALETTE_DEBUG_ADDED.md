# Palette Crash Debug Enhancement
**Date:** 2025-11-25
**Status:** Debugging Added

## Problem

User reports application still crashes when changing palettes (tested with SEPIA and GRAY), despite fixes for:
1. Initialization crash (signals during population) ✅ FIXED
2. Name cleaning (lstrip vs strip) ✅ FIXED

## Investigation

### Palette Flow Analysis
1. **GUI Side:**
   - Dropdown shows: `"  gray"` (from `PaletteType.GRAY.value`)
   - User selects, cleaned to: `"gray"`
   - Signal emitted: `palette_changed.emit("gray")`

2. **Backend Side:**
   - Receives: `"gray"` (lowercase)
   - Converts: `PaletteType("gray")` → `PaletteType.GRAY` ✅ This works!
   - Sets: `palette_manager.set_global_palette(PaletteType.GRAY)`

### Test Results
```python
>>> from palette_manager import PaletteType
>>> PaletteType("gray")
PaletteType.GRAY  # ✅ Works!
>>>  PaletteType("sepia")
PaletteType.SEPIA  # ✅ Works!
```

### Conclusion
The enum conversion works correctly. The crash must be happening:
- **During palette application** (not during enum creation)
- **In the rendering pipeline** (when using the new palette)
- **Possibly a threading issue** (GUI thread vs processing thread)

## Solution: Enhanced Error Handling

Added comprehensive try-except with logging to `_on_global_palette_changed()`:

**Location:** `inspection_gui_qt.py:4564-4575`

```python
def _on_global_palette_changed(self, palette_name: str):
    """Handle global palette selection from analysis panel."""
    try:
        logger.info(f"Attempting to change palette to: '{palette_name}' (type: {type(palette_name)})")
        if self.app:
            self.app.set_palette(palette_name)
        logger.info(f"Global palette changed successfully: {palette_name}")
    except Exception as e:
        logger.error(f"CRASH in _on_global_palette_changed with palette '{palette_name}': {e}", exc_info=True)
        # Show error to user
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Palette Error", f"Failed to change palette to '{palette_name}':\n{e}")
```

### What This Does

1. **Logs palette name and type** before attempting change
2. **Catches any exception** that occurs
3. **Logs full stack trace** to debug log
4. **Shows error dialog** to user instead of crashing
5. **Allows app to continue** running after error

## Next Steps for Testing

When you run the app and change palette:

### If Error Dialog Appears:
- Note the exact error message
- Check `thermal_inspection_debug.log` for full stack trace
- This will tell us exactly where and why it's crashing

### Expected Log Output:
```
INFO: Attempting to change palette to: 'gray' (type: <class 'str'>)
[Either SUCCESS or ERROR with details]
```

### Possible Root Causes to Check:

1. **Thread Safety Issue:**
   - Palette change from GUI thread
   - Rendering happens in processing thread
   - Need mutex/lock?

2. **OpenCV/CUDA Issue:**
   - Palette application uses CUDA
   - Memory allocation failure?
   - Need to check GPU memory?

3. **Palette Data Issue:**
   - Some palettes have corrupt LUT data?
   - Need to validate palette data?

4. **Timing Issue:**
   - Change happens mid-frame processing?
   - Need to queue palette changes?

## Files Modified

- `inspection_gui_qt.py:4564-4575` - Added error handling to `_on_global_palette_changed()`

## Testing Instructions

1. Run application: `python inspection_main.py`
2. Navigate to Settings tab
3. Open palette dropdown
4. Select a palette (try GRAY or SEPIA)
5. Observe:
   - Does error dialog appear?
   - What's the error message?
   - Check console output
   - Check `thermal_inspection_debug.log`

## Expected Output

**If it works:**
```
INFO: Attempting to change palette to: 'gray' (type: <class 'str'>)
INFO: Switched to palette: gray
INFO: Global palette changed successfully: gray
```

**If it fails:**
```
INFO: Attempting to change palette to: 'gray' (type: <class 'str'>)
ERROR: CRASH in _on_global_palette_changed with palette 'gray': [detailed error]
[Full stack trace with line numbers]
```

## Status

✅ **DEBUG LOGGING ADDED**

The next palette change attempt will:
- Capture the exact error
- Show where it fails
- Allow us to fix the root cause

---

**Enhancement added by:** Claude Code
**Purpose:** Identify exact crash location
**Risk:** None (only adds error handling)
**Next:** Test and analyze error output
