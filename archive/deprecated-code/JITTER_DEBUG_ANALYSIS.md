# GUI Button Jitter - Debug Analysis and Solutions

## Problem Statement
- **Symptom**: Button positions shift left/right
- **Frequency**: Every frame
- **Context**: No sensors attached (ThinkPad testing)
- **Screenshot**: Cannot capture as it's a dynamic issue

## Web Research Findings

### 1. OpenCV Window Backend Issues (Most Likely Cause)
**Source**: GitHub OpenCV issues #20821, #20824, #20822

**Problem**:
- GTK2/GTK3/Qt backend conflicts on Linux cause flickering and content shifting
- GTK interface breaks when mixing Qt and OpenCV
- OpenCV defaults to GTK2 but should prefer GTK3
- Future fix: OpenGL with double buffering for proper visualization

**Evidence**:
- Multiple users report flickering after system updates
- Qt/GNOME incompatibility reported
- Backend choice affects display stability

### 2. imshow() Timing Issues
**Source**: OpenCV Q&A Forum, Stack Overflow

**Problem**:
- `imshow()` only copies Mat header, actual blitting happens in `waitKey()`
- Timing issues when OS is busy can cause visual stuttering
- Windows not in focus sometimes stutter and skip frames

**Current Code**:
```python
cv2.imshow(self.window_name, frame)
return cv2.waitKey(1) & 0xFF  # 1ms delay
```
This should be sufficient, but timing variations could cause issues.

### 3. Font Rendering Antialiasing
**Source**: Previous investigation

**Problem**:
- `cv2.getTextSize()` may return slightly different values due to antialiasing
- Subpixel positioning varies frame-to-frame
- Creates text shimmer effect

**Note**: This would affect TEXT position within buttons, not BUTTON positions themselves.

## Debug Logging Added

### 1. Placeholder Frame Dimensions (main.py:669-670)
```python
if self.frame_count % 30 == 0:
    logger.info(f"[DEBUG] Frame {self.frame_count}: Placeholder thermal_frame.shape = {thermal_frame.shape}, res = {res}")
```
**Purpose**: Verify placeholder frame size is consistent

### 2. Canvas Dimensions (driver_gui.py:343-354)
```python
if self._debug_frame_count % 30 == 0:
    print(f"[DEBUG] Frame {self._debug_frame_count}: Canvas.shape = {canvas.shape}, "
          f"orig = {orig_w}x{orig_h}, scaled = {scaled_w}x{scaled_h}, scale_factor = {self.scale_factor}")
```
**Purpose**: Verify scaled canvas size is consistent

### 3. OpenCV Backend Detection (driver_gui.py:348-350)
```python
backend_name = cv2.videoio_registry.getBackendName(cv2.CAP_ANY)
print(f"[DEBUG] OpenCV Window Backend: {backend_name}")
```
**Purpose**: Identify which window backend (GTK2/GTK3/Qt) is being used

### 4. Button Positioning Calculations (driver_gui.py:524-526)
```python
if hasattr(self, '_debug_frame_count') and self._debug_frame_count % 30 == 0:
    print(f"[DEBUG] Button calc: gui_scale={gui_scale}, button_spacing={button_spacing}, "
          f"top_margin={top_margin}, left_margin={left_margin}")
```
**Purpose**: Verify button position calculations are stable

### 5. Individual Button Positions (driver_gui.py:578-579)
```python
if btn_id == 'view_mode_cycle' and hasattr(self, '_debug_frame_count') and self._debug_frame_count % 30 == 0:
    print(f"[DEBUG] Button '{btn_id}' position: x={current_x}, y={button_y}, width={width}")
```
**Purpose**: Track actual button X position for first button

## Expected Debug Output

When running with no sensors attached, you should see output like:

```
[DEBUG] OpenCV Window Backend: GTK2  <-- Identifies backend
[DEBUG] Frame 0: Canvas.shape = (1024, 1280, 3), orig = 640x512, scaled = 1280x1024, scale_factor = 2.0
[DEBUG] Button calc: gui_scale=1.8, button_spacing=27, top_margin=81, left_margin=27
[DEBUG] Button 'view_mode_cycle' position: x=27, y=81, width=288

[DEBUG] Frame 30: Placeholder thermal_frame.shape = (512, 640), res = (640, 512)
[DEBUG] Frame 30: Canvas.shape = (1024, 1280, 3), orig = 640x512, scaled = 1280x1024, scale_factor = 2.0
[DEBUG] Button calc: gui_scale=1.8, button_spacing=27, top_margin=81, left_margin=27
[DEBUG] Button 'view_mode_cycle' position: x=27, y=81, width=288
```

### What to Look For:

1. **Canvas.shape changing between frames** → Root cause identified
2. **Button position X value changing** → Confirms jitter source
3. **Backend = GTK2** → Known problematic backend
4. **Backend = GTK3 or Qt** → Should be more stable
5. **All values consistent** → Problem is elsewhere (window backend, display server)

## Potential Solutions (Priority Order)

### Solution 1: Try Different OpenCV Build (Quick Test)
```bash
# Check current OpenCV build
python3 -c "import cv2; print(cv2.getBuildInformation())" | grep -i "gui\|gtk\|qt"

# If GTK2, try to force GTK3 (if available):
export OPENCV_VIDEOIO_PRIORITY_GTK=3
python3 main.py ...
```

### Solution 2: Fixed Canvas Architecture (Definitive Fix)
**Implement the fixed UI canvas approach from `/tmp/fixed_ui_architecture.md`:**

```python
class DriverGUI:
    def __init__(self, ui_width=1920, ui_height=1080):
        # Fixed UI canvas size
        self.ui_width = ui_width
        self.ui_height = ui_height

        # Video viewport (letterboxed content)
        self.video_viewport = {
            'x': 0, 'y': 100,
            'width': ui_width,
            'height': ui_height - 200
        }

        # Fixed button positions (NEVER change)
        self.button_positions = {
            'view_mode_cycle': (20, 20, 280, 50),  # x, y, w, h
            # ... fixed positions for all buttons
        }
```

**Benefits**:
- Canvas ALWAYS same size → buttons ALWAYS at same pixel positions
- Window scaling handled by OpenCV, not our code
- Professional, stable GUI regardless of content
- Eliminates ALL jitter sources

**Effort**: 30-60 minutes to implement

### Solution 3: Switch to Qt GUI (Long-term)
Implement Option 2 from `GUI_IMPROVEMENT_OPTIONS.md` - professional PyQt5/PySide6 GUI.

**Effort**: 4-8 hours
**Benefit**: Professional, flicker-free, platform-independent

## Next Steps

1. **Run the application** and observe debug output
2. **Copy debug logs** showing 2-3 cycles of output
3. **Analyze patterns**:
   - Are canvas dimensions stable?
   - Are button positions stable?
   - Which backend is being used?
4. **Based on findings**, implement appropriate solution

## Diagnostic Script

Run `check_opencv_backend.py` to see OpenCV build configuration:
```bash
python3 check_opencv_backend.py
```

This will show:
- OpenCV version
- GUI backend (GTK2/GTK3/Qt)
- OpenGL support
- Available window flags

---

**Created**: 2025-11-14
**Issue**: Button position jitter every frame
**Status**: Debug logging added, awaiting test results
