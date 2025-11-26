# Graceful Failure Implementation Guide

## ✅ Completed

### 1. LiDAR Interface (`lidar_interface.py`)
- ✅ Abstract base class `LiDARInterface`
- ✅ Pandar 40P implementation (placeholder, ready for driver)
- ✅ Mock LiDAR for testing
- ✅ Status enum (Disconnected/Connecting/Connected/Error/Not Configured)
- ✅ Point cloud data structure
- ✅ Factory function `create_lidar()`

**Usage:**
```python
from lidar_interface import create_lidar, LiDARStatus

# Create LiDAR instance
lidar = create_lidar("pandar")

# Check status
status = lidar.get_status()  # Returns LiDARStatus enum

# Try to connect
if lidar.connect(ip="192.168.1.201"):
    # Read point cloud
    point_cloud = lidar.read_point_cloud()
```

### 2. Camera Detection Fix
- ✅ Reduced `max_devices` to 1 on Windows (prevents driver crashes)
- ✅ Early termination after consecutive failures
- ✅ Thermal camera already has graceful failure in `main.py:366-373`

---

## 🔄 In Progress / Remaining

### 3. Placeholder Frame Generation

**Create `placeholder_frames.py`:**
```python
"""
Placeholder frames for disconnected cameras
Shows user-friendly message when camera is not connected
"""
import cv2
import numpy as np
from enum import Enum

class CameraStatus(Enum):
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    RETRYING = "Retrying..."
    ERROR = "Error"

def create_placeholder_frame(width: int, height: int,
                            camera_name: str,
                            status: CameraStatus,
                            message: str = "") -> np.ndarray:
    """
    Create placeholder frame for disconnected camera

    Args:
        width: Frame width
        height: Frame height
        camera_name: Name of camera ("Thermal", "RGB", "LiDAR")
        status: Camera status
        message: Additional message

    Returns:
        Placeholder frame (BGR image)
    """
    # Create dark gray background
    frame = np.full((height, width, 3), 40, dtype=np.uint8)

    # Colors based on status
    colors = {
        CameraStatus.CONNECTED: (0, 255, 0),      # Green
        CameraStatus.DISCONNECTED: (128, 128, 128),  # Gray
        CameraStatus.RETRYING: (0, 255, 255),     # Yellow
        CameraStatus.ERROR: (0, 0, 255),          # Red
    }
    color = colors.get(status, (128, 128, 128))

    # Draw border
    cv2.rectangle(frame, (10, 10), (width-10, height-10), color, 3)

    # Add camera icon (simple circle)
    center_x, center_y = width // 2, height // 2 - 50
    cv2.circle(frame, (center_x, center_y), 40, color, -1)
    cv2.circle(frame, (center_x, center_y), 20, (40, 40, 40), -1)

    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX

    # Camera name
    text = f"{camera_name} Camera"
    text_size = cv2.getTextSize(text, font, 1.2, 2)[0]
    text_x = (width - text_size[0]) // 2
    cv2.putText(frame, text, (text_x, center_y + 80),
               font, 1.2, (255, 255, 255), 2)

    # Status
    status_text = status.value
    text_size = cv2.getTextSize(status_text, font, 0.8, 2)[0]
    text_x = (width - text_size[0]) // 2
    cv2.putText(frame, status_text, (text_x, center_y + 120),
               font, 0.8, color, 2)

    # Additional message
    if message:
        text_size = cv2.getTextSize(message, font, 0.6, 1)[0]
        text_x = (width - text_size[0]) // 2
        cv2.putText(frame, message, (text_x, center_y + 160),
                   font, 0.6, (200, 200, 200), 1)

    return frame
```

### 4. Camera Status System

**Modify `main.py` to add status tracking:**
```python
class ThermalFusionApp:
    def __init__(self):
        # ... existing code ...

        # Camera status tracking
        self.thermal_status = CameraStatus.DISCONNECTED
        self.rgb_status = CameraStatus.DISCONNECTED
        self.lidar_status = CameraStatus.DISCONNECTED

        # LiDAR integration
        self.lidar = None
        self.lidar_enabled = False

    def _try_connect_thermal(self):
        """Modified to update status"""
        try:
            self.thermal_status = CameraStatus.RETRYING
            # ... existing connection code ...
            if connected:
                self.thermal_status = CameraStatus.CONNECTED
                return True
            else:
                self.thermal_status = CameraStatus.DISCONNECTED
                return False
        except Exception as e:
            self.thermal_status = CameraStatus.ERROR
            return False

    def _try_connect_lidar(self) -> bool:
        """Connect to LiDAR sensor"""
        try:
            if not self.args.lidar_type:
                return False

            from lidar_interface import create_lidar, LiDARStatus

            self.lidar_status = CameraStatus.RETRYING
            self.lidar = create_lidar(self.args.lidar_type)

            lidar_ip = getattr(self.args, 'lidar_ip', '192.168.1.201')
            if self.lidar.connect(ip=lidar_ip):
                self.lidar_status = CameraStatus.CONNECTED
                self.lidar_enabled = True
                logger.info(f"[OK] LiDAR connected: {self.lidar.name}")
                return True
            else:
                self.lidar_status = CameraStatus.DISCONNECTED
                return False

        except Exception as e:
            logger.warning(f"LiDAR connection failed: {e}")
            self.lidar_status = CameraStatus.ERROR
            return False

    def retry_cameras(self):
        """Retry connecting all cameras - called by GUI button"""
        logger.info("Retrying camera connections...")

        # Retry thermal
        if not self.thermal_connected:
            self._try_connect_thermal()

        # Retry RGB
        if not self.rgb_available:
            # ... retry RGB connection ...
            pass

        # Retry LiDAR
        if not self.lidar_enabled:
            self._try_connect_lidar()

    def get_display_frame(self):
        """Get frame for display - with placeholders if needed"""
        # If thermal connected, get real frame
        if self.thermal_connected and self.thermal_camera:
            ret, thermal_frame = self.thermal_camera.read()
            if not ret:
                thermal_frame = create_placeholder_frame(
                    640, 480, "Thermal",
                    CameraStatus.ERROR,
                    "Frame read failed"
                )
        else:
            # Show placeholder
            thermal_frame = create_placeholder_frame(
                640, 480, "Thermal",
                self.thermal_status,
                "Press 'Retry Cameras' in Developer panel"
            )

        # Similar for RGB
        if self.rgb_available and self.rgb_camera:
            ret, rgb_frame = self.rgb_camera.read()
            if not ret:
                rgb_frame = create_placeholder_frame(
                    640, 480, "RGB",
                    CameraStatus.ERROR
                )
        else:
            rgb_frame = create_placeholder_frame(
                640, 480, "RGB",
                self.rgb_status
            )

        return thermal_frame, rgb_frame
```

### 5. GUI Status Indicators

**Modify `developer_panel.py` to add:**
```python
def create_status_section(self):
    """Create camera status indicators"""
    status_layout = QHBoxLayout()

    # Thermal status
    self.thermal_status_label = QLabel("⚫ Thermal")
    status_layout.addWidget(self.thermal_status_label)

    # RGB status
    self.rgb_status_label = QLabel("⚫ RGB")
    status_layout.addWidget(self.rgb_status_label)

    # LiDAR status
    self.lidar_status_label = QLabel("⚫ LiDAR")
    status_layout.addWidget(self.lidar_status_label)

    # Retry button
    retry_btn = QPushButton("Retry Cameras")
    retry_btn.clicked.connect(self.on_retry_cameras)
    status_layout.addWidget(retry_btn)

    return status_layout

def update_status_indicators(self, thermal_status, rgb_status, lidar_status):
    """Update status LED indicators"""
    status_colors = {
        CameraStatus.CONNECTED: "🟢",
        CameraStatus.DISCONNECTED: "⚫",
        CameraStatus.RETRYING: "🟡",
        CameraStatus.ERROR: "🔴",
    }

    self.thermal_status_label.setText(
        f"{status_colors[thermal_status]} Thermal"
    )
    self.rgb_status_label.setText(
        f"{status_colors[rgb_status]} RGB"
    )
    self.lidar_status_label.setText(
        f"{status_colors[lidar_status]} LiDAR"
    )
```

### 6. Command Line Arguments

**Add to `main.py` argument parser:**
```python
parser.add_argument('--lidar-type', type=str,
                   choices=['pandar', 'pandar_40p', 'mock', 'none'],
                   default='none',
                   help='LiDAR sensor type')
parser.add_argument('--lidar-ip', type=str,
                   default='192.168.1.201',
                   help='LiDAR IP address')
parser.add_argument('--thermal-id', type=int, default=None,
                   help='Thermal camera device ID')
parser.add_argument('--rgb-id', type=int, default=None,
                   help='RGB camera device ID')
```

---

## 🧪 Testing Plan

### Test Scenarios

**1. Zero Cameras**
```bash
# Disconnect all cameras
python main.py
# Expected: GUI opens, shows 3 placeholder frames, retry button visible
```

**2. Thermal Only**
```bash
python main.py --disable-rgb
# Expected: Thermal works, RGB placeholder, LiDAR placeholder
```

**3. Thermal + RGB**
```bash
python main.py
# Expected: Both work, LiDAR placeholder
```

**4. Thermal + RGB + Mock LiDAR**
```bash
python main.py --lidar-type mock
# Expected: All 3 "connected" (LiDAR simulated)
```

**5. Hot-Plug Test**
```bash
python main.py
# 1. Start with no cameras
# 2. Connect thermal camera
# 3. Click "Retry Cameras"
# Expected: Thermal auto-detects and starts working
```

---

## 📋 Implementation Checklist

- [x] Create `lidar_interface.py` with Pandar 40P support
- [ ] Create `placeholder_frames.py` with status indicators
- [ ] Modify `main.py`:
  - [ ] Add camera status enums
  - [ ] Add `_try_connect_lidar()`
  - [ ] Add `retry_cameras()` method
  - [ ] Modify `get_display_frame()` to use placeholders
  - [ ] Add LiDAR command line arguments
- [ ] Modify `developer_panel.py`:
  - [ ] Add status LED indicators
  - [ ] Add "Retry Cameras" button
  - [ ] Wire up button to `app.retry_cameras()`
- [ ] Modify `video_worker.py`:
  - [ ] Handle None frames gracefully
  - [ ] Use placeholder frames when cameras disconnected
- [ ] Update `README.md`:
  - [ ] Document LiDAR support
  - [ ] Document graceful failure behavior
  - [ ] Add camera ID command line options
- [ ] Test all scenarios

---

## 🚀 Quick Start (After Implementation)

**Run with all features:**
```bash
python main.py --lidar-type pandar --lidar-ip 192.168.1.201
```

**Manual camera selection:**
```bash
python main.py --thermal-id 0 --rgb-id 1
```

**Test mode with mock sensors:**
```bash
python main.py --lidar-type mock
```

---

## 📊 Status Summary

| Feature | Status | File |
|---------|--------|------|
| LiDAR Interface | ✅ Complete | `lidar_interface.py` |
| Placeholder Frames | 🔄 Need to create | `placeholder_frames.py` |
| Camera Status Tracking | 🔄 Partial (thermal done) | `main.py` |
| Retry Button | ⏳ Not started | `developer_panel.py` |
| Status Indicators | ⏳ Not started | `developer_panel.py` |
| CLI Arguments | ⏳ Not started | `main.py` |

**Estimated remaining time:** 2-3 hours for full implementation + testing
