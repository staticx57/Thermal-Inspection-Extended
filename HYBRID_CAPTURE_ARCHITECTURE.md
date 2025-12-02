# Hybrid Multi-Backend Capture Architecture

**Goal**: Support multiple camera backends with runtime selection
**Cameras**: FLIR Boson (thermal), Firefly (RGB)
**Backends**: OpenCV, PySpin, PyUSB

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│                  (inspection_main.py)                       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Unified API
                         │
┌────────────────────────▼────────────────────────────────────┐
│              CameraManager (New!)                           │
│  - Manages multiple cameras                                 │
│  - Backend selection                                        │
│  - Runtime switching                                        │
└────────┬───────────────────────────────┬────────────────────┘
         │                               │
         │ thermal_camera               │ rgb_camera
         │                               │
┌────────▼──────────────┐      ┌────────▼──────────────┐
│  ThermalCamera        │      │  RGBCamera            │
│  (Abstract Base)      │      │  (Abstract Base)      │
└────┬───────┬──────────┘      └────┬──────────────────┘
     │       │                      │
     │       │                      │
┌────▼───┐ ┌─▼───────┐      ┌──────▼──────┐
│ OpenCV │ │ PyUSB   │      │  PySpin     │
│ Backend│ │ Backend │      │  Backend    │
│        │ │         │      │             │
│ 8-bit  │ │ 16-bit  │      │  RGB        │
│ T-Linear│ │ Y16     │      │  High-res   │
└────────┘ └─────────┘      └─────────────┘
```

---

## Implementation Design

### 1. Abstract Base Classes

```python
# camera_backends.py

from abc import ABC, abstractmethod
import numpy as np

class CameraBackend(ABC):
    """Abstract base class for all camera backends."""

    @abstractmethod
    def open(self) -> bool:
        """Open the camera."""
        pass

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray]:
        """Read a frame. Returns (success, frame)."""
        pass

    @abstractmethod
    def release(self):
        """Release camera resources."""
        pass

    @abstractmethod
    def get_info(self) -> dict:
        """Get camera information."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend can be initialized."""
        pass


class ThermalBackend(CameraBackend):
    """Base class for thermal camera backends."""

    @abstractmethod
    def get_temperature_map(self) -> np.ndarray:
        """Get temperature map if available."""
        pass

    @abstractmethod
    def is_radiometric(self) -> bool:
        """Returns True if backend provides true radiometric data."""
        pass
```

### 2. OpenCV Thermal Backend (8-bit)

```python
# opencv_thermal_backend.py

import cv2
from camera_backends import ThermalBackend

class OpenCVThermalBackend(ThermalBackend):
    """
    OpenCV backend for FLIR Boson thermal camera.

    Provides: 8-bit T-Linear processed thermal images
    Quality: Excellent for visual inspection
    Radiometric: No (use pseudo-estimation)
    """

    def __init__(self, device_id=1, com_port='COM7'):
        self.device_id = device_id
        self.com_port = com_port
        self.cap = None
        self.sdk = None

    def is_available(self) -> bool:
        """Check if OpenCV can access the camera."""
        try:
            test_cap = cv2.VideoCapture(self.device_id)
            available = test_cap.isOpened()
            test_cap.release()
            return available
        except:
            return False

    def open(self) -> bool:
        """Open camera with DirectShow backend."""
        try:
            # Open video
            self.cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                return False

            # Open SDK
            from boson_sdk_wrapper import BosonSDK
            self.sdk = BosonSDK(com_port=self.com_port)
            if self.sdk.connect():
                # Enable T-Linear mode
                self.sdk.enable_tlinear_control()
                self.sdk.set_usb_video_ir16_mode(2)  # T-Linear

            return True
        except Exception as e:
            print(f"OpenCV thermal backend failed: {e}")
            return False

    def read(self) -> tuple[bool, np.ndarray]:
        """Read 8-bit thermal frame."""
        if not self.cap:
            return False, None
        return self.cap.read()

    def release(self):
        """Release resources."""
        if self.cap:
            self.cap.release()
        if self.sdk:
            self.sdk.disconnect()

    def get_info(self) -> dict:
        """Get backend information."""
        return {
            'backend': 'OpenCV DirectShow',
            'type': 'thermal',
            'bit_depth': 8,
            'radiometric': False,
            'resolution': (640, 512),
            'features': ['T-Linear processing', 'Runtime mode switching', 'SDK control']
        }

    def is_radiometric(self) -> bool:
        return False

    def get_temperature_map(self) -> np.ndarray:
        """Returns None - no true radiometric data."""
        return None
```

### 3. PyUSB Thermal Backend (16-bit)

```python
# pyusb_thermal_backend.py

import usb.core
import numpy as np
from camera_backends import ThermalBackend

class PyUSBThermalBackend(ThermalBackend):
    """
    Direct USB backend for FLIR Boson thermal camera.

    Provides: True 16-bit Y16 radiometric data
    Quality: Absolute temperature accuracy (±2°C)
    Radiometric: Yes (full calibration)

    Requirements: WinUSB driver (replaces UVC driver)
    """

    def __init__(self, vid=0x09CB, pid=0x4007):
        self.vid = vid
        self.pid = pid
        self.dev = None
        self.endpoint = None

    def is_available(self) -> bool:
        """Check if PyUSB can access the camera."""
        try:
            dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            return dev is not None
        except:
            return False

    def open(self) -> bool:
        """Open camera via direct USB access."""
        try:
            # Find device
            self.dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
            if self.dev is None:
                return False

            # Get video streaming endpoint
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0, 0)]  # First interface, first alternate setting
            self.endpoint = intf[0]  # First endpoint (usually EP1 IN)

            return True
        except Exception as e:
            print(f"PyUSB thermal backend failed: {e}")
            return False

    def read(self) -> tuple[bool, np.ndarray]:
        """Read 16-bit Y16 frame from USB."""
        if not self.dev or not self.endpoint:
            return False, None

        try:
            # Read bulk transfer (640*512*2 bytes + 12 byte UVC header)
            data = self.dev.read(
                self.endpoint.bEndpointAddress,
                640 * 512 * 2 + 12,
                timeout=1000
            )

            # Skip UVC header (12 bytes)
            frame_data = data[12:]

            # Convert to 16-bit array
            frame = np.frombuffer(frame_data, dtype=np.uint16)
            frame = frame.reshape(512, 640)

            return True, frame
        except Exception as e:
            print(f"USB read error: {e}")
            return False, None

    def release(self):
        """Release USB device."""
        if self.dev:
            usb.util.dispose_resources(self.dev)
            self.dev = None

    def get_info(self) -> dict:
        """Get backend information."""
        return {
            'backend': 'PyUSB Direct',
            'type': 'thermal',
            'bit_depth': 16,
            'radiometric': True,
            'resolution': (640, 512),
            'features': ['True radiometric', 'Absolute temps', '±2°C accuracy']
        }

    def is_radiometric(self) -> bool:
        return True

    def get_temperature_map(self) -> np.ndarray:
        """Convert 16-bit values to temperature in Celsius."""
        ret, frame = self.read()
        if not ret:
            return None

        # FLIR formula: temp_kelvin = pixel_value / 100.0
        temp_k = frame.astype(float) / 100.0
        temp_c = temp_k - 273.15

        return temp_c
```

### 4. PySpin RGB Backend

```python
# pyspin_rgb_backend.py

import PySpin
import numpy as np
from camera_backends import CameraBackend

class PySpinRGBBackend(CameraBackend):
    """
    PySpin backend for Firefly RGB camera.

    Provides: High-resolution RGB images
    """

    def __init__(self, serial_number=None):
        self.serial_number = serial_number
        self.system = None
        self.cam = None

    def is_available(self) -> bool:
        """Check if PySpin can access Firefly camera."""
        try:
            system = PySpin.System.GetInstance()
            cam_list = system.GetCameras()
            available = cam_list.GetSize() > 0
            cam_list.Clear()
            system.ReleaseInstance()
            return available
        except:
            return False

    def open(self) -> bool:
        """Open Firefly camera."""
        try:
            self.system = PySpin.System.GetInstance()
            cam_list = self.system.GetCameras()

            if cam_list.GetSize() == 0:
                return False

            # Get first camera or by serial
            self.cam = cam_list[0]
            self.cam.Init()
            self.cam.BeginAcquisition()

            return True
        except Exception as e:
            print(f"PySpin RGB backend failed: {e}")
            return False

    def read(self) -> tuple[bool, np.ndarray]:
        """Read RGB frame."""
        if not self.cam:
            return False, None

        try:
            image_result = self.cam.GetNextImage(1000)

            if image_result.IsIncomplete():
                return False, None

            # Convert to numpy array
            frame = image_result.GetNDArray()
            image_result.Release()

            return True, frame
        except Exception as e:
            return False, None

    def release(self):
        """Release camera."""
        if self.cam:
            self.cam.EndAcquisition()
            self.cam.DeInit()
            del self.cam
        if self.system:
            self.system.ReleaseInstance()

    def get_info(self) -> dict:
        """Get backend information."""
        return {
            'backend': 'PySpin',
            'type': 'rgb',
            'bit_depth': 8,
            'radiometric': False,
            'resolution': (1440, 1080),  # Firefly resolution
            'features': ['High resolution', 'Color', 'Machine vision']
        }
```

### 5. Camera Manager (Orchestration)

```python
# camera_manager.py

from typing import Optional, Dict
from camera_backends import CameraBackend
from opencv_thermal_backend import OpenCVThermalBackend
from pyusb_thermal_backend import PyUSBThermalBackend
from pyspin_rgb_backend import PySpinRGBBackend

class CameraManager:
    """
    Manages multiple cameras with different backends.

    Provides unified interface for application layer.
    """

    def __init__(self):
        self.thermal_backend: Optional[CameraBackend] = None
        self.rgb_backend: Optional[CameraBackend] = None
        self.thermal_mode = 'opencv'  # 'opencv' or 'usb'

    def initialize_thermal(self, mode='opencv') -> bool:
        """
        Initialize thermal camera with specified backend.

        Args:
            mode: 'opencv' for 8-bit T-Linear, 'usb' for 16-bit radiometric
        """
        self.thermal_mode = mode

        if mode == 'opencv':
            backend = OpenCVThermalBackend(device_id=1, com_port='COM7')
        elif mode == 'usb':
            backend = PyUSBThermalBackend()
        else:
            raise ValueError(f"Unknown thermal mode: {mode}")

        # Check availability
        if not backend.is_available():
            print(f"Thermal backend '{mode}' not available")
            return False

        # Open
        if backend.open():
            self.thermal_backend = backend
            print(f"Thermal camera initialized: {mode}")
            return True
        else:
            print(f"Failed to open thermal backend: {mode}")
            return False

    def initialize_rgb(self) -> bool:
        """Initialize RGB camera (Firefly via PySpin)."""
        backend = PySpinRGBBackend()

        if not backend.is_available():
            print("RGB backend (PySpin) not available")
            return False

        if backend.open():
            self.rgb_backend = backend
            print("RGB camera initialized: PySpin")
            return True
        else:
            print("Failed to open RGB backend")
            return False

    def read_thermal(self):
        """Read frame from thermal camera."""
        if not self.thermal_backend:
            return False, None
        return self.thermal_backend.read()

    def read_rgb(self):
        """Read frame from RGB camera."""
        if not self.rgb_backend:
            return False, None
        return self.rgb_backend.read()

    def get_thermal_temperature_map(self):
        """Get temperature map from thermal camera (if radiometric)."""
        if not self.thermal_backend:
            return None

        if hasattr(self.thermal_backend, 'get_temperature_map'):
            return self.thermal_backend.get_temperature_map()
        return None

    def switch_thermal_mode(self, mode: str) -> bool:
        """
        Switch thermal camera backend at runtime.

        Args:
            mode: 'opencv' or 'usb'
        """
        # Release current backend
        if self.thermal_backend:
            self.thermal_backend.release()
            self.thermal_backend = None

        # Initialize new backend
        return self.initialize_thermal(mode)

    def get_info(self) -> dict:
        """Get information about all active cameras."""
        info = {}

        if self.thermal_backend:
            info['thermal'] = self.thermal_backend.get_info()

        if self.rgb_backend:
            info['rgb'] = self.rgb_backend.get_info()

        return info

    def release_all(self):
        """Release all cameras."""
        if self.thermal_backend:
            self.thermal_backend.release()
        if self.rgb_backend:
            self.rgb_backend.release()
```

---

## Usage Examples

### Example 1: Basic Setup

```python
from camera_manager import CameraManager

# Create manager
manager = CameraManager()

# Initialize thermal with OpenCV (8-bit, works now)
manager.initialize_thermal(mode='opencv')

# Initialize RGB
manager.initialize_rgb()

# Read frames
ret_thermal, thermal_frame = manager.read_thermal()
ret_rgb, rgb_frame = manager.read_rgb()

# Get info
info = manager.get_info()
print(info)
# {
#   'thermal': {'backend': 'OpenCV DirectShow', 'bit_depth': 8, ...},
#   'rgb': {'backend': 'PySpin', 'bit_depth': 8, ...}
# }
```

### Example 2: Runtime Backend Switching

```python
# Start with OpenCV (8-bit)
manager.initialize_thermal(mode='opencv')

# Capture for a while...
for i in range(100):
    ret, frame = manager.read_thermal()
    # Process 8-bit thermal...

# User wants radiometric data - switch to USB
print("Switching to 16-bit radiometric mode...")
if manager.switch_thermal_mode('usb'):
    # Now capturing true 16-bit
    ret, frame = manager.read_thermal()  # dtype=uint16
    temp_map = manager.get_thermal_temperature_map()  # Celsius
    print(f"Center temp: {temp_map[256, 320]:.1f}°C")
else:
    print("16-bit mode not available (need WinUSB driver)")
```

### Example 3: GUI with Backend Selection

```python
from PyQt6.QtWidgets import QComboBox, QPushButton

class ThermalControlPanel:
    def __init__(self, camera_manager):
        self.manager = camera_manager

        # Backend selector
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(['8-bit OpenCV', '16-bit USB'])
        self.backend_combo.currentTextChanged.connect(self.on_backend_changed)

        # Apply button
        self.apply_btn = QPushButton("Apply Backend")
        self.apply_btn.clicked.connect(self.apply_backend)

    def on_backend_changed(self, text):
        """Called when user selects different backend."""
        if '8-bit' in text:
            self.selected_mode = 'opencv'
        else:
            self.selected_mode = 'usb'

    def apply_backend(self):
        """Apply selected backend."""
        success = self.manager.switch_thermal_mode(self.selected_mode)

        if success:
            info = self.manager.get_info()['thermal']
            QMessageBox.information(
                self,
                "Backend Changed",
                f"Now using: {info['backend']}\n"
                f"Bit depth: {info['bit_depth']}\n"
                f"Radiometric: {info['radiometric']}"
            )
        else:
            QMessageBox.warning(
                self,
                "Backend Failed",
                f"Could not initialize {self.selected_mode} backend.\n"
                f"Check drivers and connections."
            )
```

---

## Frontend Integration

### GUI Layout

```
┌─────────────────────────────────────────────────────────┐
│  Thermal Inspection - Camera Control                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Thermal Camera:                                        │
│  ┌─────────────────────┐  ┌──────────┐                │
│  │ Backend: [v]        │  │  Apply   │                │
│  │  • 8-bit OpenCV     │  └──────────┘                │
│  │  • 16-bit USB       │                               │
│  └─────────────────────┘                               │
│                                                          │
│  Status: [OK] OpenCV DirectShow (8-bit, T-Linear)      │
│  Radiometric: No                                        │
│                                                          │
│  ────────────────────────────────────────────────────   │
│                                                          │
│  RGB Camera:                                            │
│  Status: [OK] PySpin Firefly (1440x1080)               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Implementation Sketch

```python
# In inspection_gui_qt.py

class CameraBackendWidget(QWidget):
    backend_changed = pyqtSignal(str)  # 'opencv' or 'usb'

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()

        # Backend selector
        self.backend_group = QGroupBox("Thermal Camera Backend")
        backend_layout = QVBoxLayout()

        self.opencv_radio = QRadioButton("8-bit OpenCV (T-Linear)")
        self.opencv_radio.setChecked(True)
        self.opencv_radio.setToolTip(
            "8-bit thermal capture with T-Linear processing\n"
            "• Works on Windows 11\n"
            "• No absolute temperatures\n"
            "• Excellent for visual inspection"
        )

        self.usb_radio = QRadioButton("16-bit USB (Radiometric)")
        self.usb_radio.setToolTip(
            "True 16-bit radiometric capture\n"
            "• Requires WinUSB driver\n"
            "• Absolute temperatures (±2°C)\n"
            "• 65,536 gray levels"
        )

        backend_layout.addWidget(self.opencv_radio)
        backend_layout.addWidget(self.usb_radio)

        self.apply_btn = QPushButton("Apply Backend Change")
        self.apply_btn.clicked.connect(self.apply_backend)
        backend_layout.addWidget(self.apply_btn)

        self.backend_group.setLayout(backend_layout)
        layout.addWidget(self.backend_group)

        # Status display
        self.status_label = QLabel("Status: Not initialized")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def apply_backend(self):
        """Apply selected backend."""
        if self.opencv_radio.isChecked():
            mode = 'opencv'
        else:
            mode = 'usb'

        self.backend_changed.emit(mode)
```

---

## Advantages of This Architecture

### 1. Flexibility ✅
- Choose backend based on needs
- Switch at runtime without restart
- Add new backends easily

### 2. Backwards Compatible ✅
- OpenCV backend works NOW on Windows 11
- USB backend ready when you need it
- Gradual migration path

### 3. Future-Proof ✅
- Easy to add new cameras
- Easy to add new backends
- Modular design

### 4. User-Friendly ✅
- GUI dropdown for backend selection
- Clear status indicators
- No manual configuration files

### 5. Production Ready ✅
- Start with working 8-bit solution
- Add 16-bit when needed
- Automatic fallback if backend unavailable

---

## Implementation Steps

### Phase 1: Core Architecture (2 hours)
1. Create abstract base classes
2. Implement OpenCV thermal backend (from existing code)
3. Implement PySpin RGB backend (from existing code)
4. Create CameraManager

### Phase 2: GUI Integration (1 hour)
1. Add backend selector widget
2. Connect to CameraManager
3. Add status displays

### Phase 3: USB Backend (3 hours)
1. Implement PyUSB thermal backend
2. Test with WinUSB driver
3. Verify 16-bit capture

### Phase 4: Testing (1 hour)
1. Test backend switching
2. Test both cameras simultaneously
3. Verify temperature data

**Total**: ~7 hours for complete system

---

## Would You Like Me To Implement This?

I can create this architecture for you with:
- ✅ All backend classes
- ✅ CameraManager orchestration
- ✅ GUI integration
- ✅ Full documentation

This gives you the **best of all worlds**:
- 8-bit working NOW
- 16-bit when you implement USB
- Both cameras unified
- Runtime switching
- Future extensibility

**Ready to proceed?**
