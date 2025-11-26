# Camera Detection Crash Fix & Graceful Degradation Plan

## Issue Diagnosed

**Problem:** Windows OpenCV drivers cause fatal exceptions (0xc06d007e) when probing non-existent camera indices.
- Exception occurs at driver/DLL level
- Python try-except cannot catch it
- Application crashes immediately

## Immediate Fix Applied

### camera_detector.py Changes
```python
# Changed max_devices from 5 → 1
def _probe_windows_cameras(max_devices: int = 1)

# Added early termination
MAX_CONSECUTIVE_FAILURES = 1  # Stop after 1 failure
```

**Result:** Application now works with `--disable-rgb` flag

## User Requirements (New)

### 1. Graceful Failure
- ✅ Window must stay open even if all cameras fail
- ✅ Show reconnection prompt in GUI
- ✅ Allow manual camera retry
- ✅ Don't crash on camera errors

### 2. Multi-Camera Support
- ✅ Support 0-3 cameras connected
  - **Thermal camera** (FLIR Boson or generic)
  - **RGB camera** (FLIR Firefly or UVC)
  - **Future: 3rd camera** (optional)
- ✅ Auto-detect and handle any combination

### 3. Hot-Plug Support
- ✅ Cameras can be disconnected/reconnected
- ✅ Auto-retry every 3 seconds (already implemented)
- ✅ Show connection status in GUI

### 4. LiDAR Placeholder
- ✅ Add LiDAR connection placeholder
- ✅ Future: Pandar 40P integration
- ✅ Prepare data fusion pipeline

---

## Implementation Plan

### Phase 1: Graceful Failure (Priority 1)
**File:** `main.py`

**Changes needed:**
1. Wrap all camera initialization in try-except
2. If camera fails, show "No camera" placeholder frame
3. Add "Retry Cameras" button in developer panel
4. Continue to GUI even with 0 cameras
5. Show camera status (connected/disconnected/retrying)

**Example:**
```python
def initialize():
    try:
        thermal_camera = open_thermal()
    except:
        thermal_camera = None
        show_thermal_placeholder()

    try:
        rgb_camera = open_rgb()
    except:
        rgb_camera = None
        show_rgb_placeholder()

    # Always continue to GUI
    return True  # Never return False
```

### Phase 2: Camera Status UI
**File:** `driver_gui_qt.py`, `developer_panel.py`

**Add:**
- Camera status indicators (green/red/yellow LEDs)
- "Retry Cameras" button
- Connection status text:
  - "Thermal: Connected (640x480)"
  - "RGB: Disconnected - Retrying..."
  - "LiDAR: Not configured"

### Phase 3: Safe Camera Probing
**File:** `camera_detector.py`

**Options:**
1. **Option A:** Only probe camera 0 (current fix)
2. **Option B:** Use Windows API to enumerate cameras (safer)
3. **Option C:** Add --camera-ids flag for manual specification

**Recommended:** Option C + Option A
```bash
# Auto-detect (safe, only checks camera 0)
python main.py

# Manual specification (advanced users with multiple cameras)
python main.py --thermal-id 0 --rgb-id 1 --camera-id-3 2
```

### Phase 4: LiDAR Placeholder
**Files to create:**
- `lidar_interface.py` - Abstract LiDAR interface
- `pandar_40p.py` - Pandar 40P specific implementation
- `lidar_fusion.py` - LiDAR + Camera fusion

**Structure:**
```python
class LiDARInterface:
    def connect(self, port):
        pass

    def read_point_cloud(self):
        pass

    def get_status(self):
        return "Not connected"
```

---

## Testing Matrix

| Scenario | Expected Behavior |
|----------|-------------------|
| 0 cameras | App opens, shows placeholders, retry button visible |
| 1 thermal | Thermal view works, RGB placeholder shown |
| 1 thermal + 1 RGB | Full fusion works |
| 2+ cameras | Auto-select thermal + RGB, ignore extras |
| Camera disconnect mid-run | Auto-retry every 3s, show status |
| Camera reconnect | Auto-detect and resume |

---

## Current Status

✅ **Fixed:** Windows camera crash (reduced max_devices to 1)
✅ **Working:** Thermal-only mode with `--disable-rgb`
⏳ **TODO:** Graceful failure (window stays open)
⏳ **TODO:** Camera status UI
⏳ **TODO:** LiDAR placeholder

---

## Quick Fix for Immediate Use

**Run thermal-only (works now):**
```cmd
python main.py --disable-rgb
```

**For full implementation:**
- See next message for code changes
- Estimated time: 1-2 hours for graceful failure
- Estimated time: 30min for LiDAR placeholder

