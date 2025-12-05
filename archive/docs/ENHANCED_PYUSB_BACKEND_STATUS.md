# Enhanced PyUSB Backend Implementation Status

## Goal
Create a thermal camera backend that provides BOTH:
- ✅ 16-bit Y16 radiometric capture (absolute temperatures ±2°C)
- ✅ Full SDK control (FFC, AGC, telemetry, etc.)

This matches the FLIR app capabilities and eliminates the need to choose between radiometric data and SDK control.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│          Enhanced PyUSB Thermal Backend                       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Video Capture              SDK Control                      │
│  ┌────────────┐             ┌────────────┐                  │
│  │ USB Bulk   │             │ USB FSLP   │                  │
│  │ IN (0x81)  │             │ Dispatcher │                  │
│  │            │             │            │                  │
│  │ Y16 Frames │             │ Commands   │                  │
│  │ 640×512    │             │ via USB    │                  │
│  │ 16-bit     │             │ Bulk I/O   │                  │
│  └────────────┘             └────────────┘                  │
│       ▲                            ▲                          │
│       │                            │                          │
└───────┼────────────────────────────┼──────────────────────────┘
        │                            │
        │                            │
   ┌────┴────────────────────────────┴─────┐
   │     FLIR Boson (VID:PID 09CB:4007)    │
   │                                        │
   │  Interface 0: Video (UVC)              │
   │    Endpoint 0x81: Bulk IN (Y16)        │
   │                                        │
   │  Interface 1: Control (CDC/ACM)        │
   │    Endpoint 0x82: Bulk IN (responses)  │
   │    Endpoint 0x02: Bulk OUT (commands)  │
   └────────────────────────────────────────┘
```

---

## Implementation Progress

### Phase 1: ✅ COMPLETE - Research & Documentation
- [x] Analyzed FLIR SDK protocol structure
- [x] Documented FSLP framing and CRC
- [x] Mapped Boson USB interfaces
- [x] Created `BOSON_USB_PROTOCOL_RESEARCH.md`

**Key Findings**:
- SDK uses FSLP (FLIR Serial Link Protocol)
- Currently sends via COM port (USB CDC virtual serial)
- Same protocol can be sent over direct USB bulk transfers
- Boson has TWO USB interfaces: Video (Y16) and Control (SDK)

### Phase 2: ✅ COMPLETE - USB FSLP Transport
- [x] Created `usb_fslp_transport.py`
- [x] Implemented `USBFslpTransport` class
- [x] FSLP framing (START 0x8E, END 0xAE, ESCAPE 0x9E)
- [x] Byte escaping logic
- [x] CRC-16-CCITT calculation
- [x] USB bulk IN/OUT transfers
- [x] `USBFslpPort` wrapper for SDK compatibility

**Code Structure**:
```python
class USBFslpTransport:
    """FSLP over USB bulk endpoints."""

    def sendFrame(channelID, data, dataSize):
        # Build frame: [START][CHANNEL][DATA][CRC][END]
        # Escape special bytes
        # Send via USB bulk OUT

    def readFrame(channelID, expectedReceiveBytes):
        # Read from USB bulk IN
        # Unescape bytes
        # Verify CRC and channel
        # Return data
```

### Phase 3: 🚧 IN PROGRESS - Enhanced Backend
**Status**: Architecture designed, ready for implementation

**Components Needed**:
1. **USB Endpoint Discovery** - Identify video (0x81) and control (0x82, 0x02) endpoints
2. **SDK Dispatcher** - Send SDK commands via USB FSLP
3. **Enhanced Backend Class** - Combine Y16 capture + SDK control
4. **Integration** - Add to CameraManager

**Next File**: `enhanced_pyusb_thermal_backend.py`

---

## Implementation Plan

### Step 1: USB Interface Discovery
Create utility to identify Boson interfaces and endpoints when WinUSB installed:

```python
def discover_boson_usb():
    """Find Boson and identify video/control interfaces."""
    dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)

    video_intf = None
    video_ep_in = None
    control_intf = None
    control_ep_in = None
    control_ep_out = None

    for cfg in dev:
        for intf in cfg:
            if intf.bInterfaceClass == 0x0E:  # Video
                video_intf = intf.bInterfaceNumber
                for ep in intf:
                    if ep.bEndpointAddress & 0x80:  # IN
                        video_ep_in = ep.bEndpointAddress
            elif intf.bInterfaceClass == 0x02:  # CDC
                control_intf = intf.bInterfaceNumber
                for ep in intf:
                    if ep.bEndpointAddress & 0x80:  # IN
                        control_ep_in = ep.bEndpointAddress
                    else:  # OUT
                        control_ep_out = ep.bEndpointAddress

    return video_ep_in, control_ep_in, control_ep_out
```

### Step 2: SDK Command Dispatcher
Wrap FSLP transport to match SDK's dispatcher interface:

```python
from usb_fslp_transport import USBFslpPort

class USBSDKDispatcher:
    """Send SDK commands via USB instead of serial."""

    def __init__(self, usb_device, ctrl_in_ep, ctrl_out_ep):
        self.fslp = USBFslpPort(usb_device, ctrl_in_ep, ctrl_out_ep)
        self.command_count = 0

    def send_command(self, fn_id, send_data, expected_receive_bytes):
        """Send SDK command and receive response."""
        # Build payload: [SEQ][FN_ID][0xFFFFFFFF][DATA]
        payload = bytearray()
        payload.extend(struct.pack('<I', self.command_count))
        payload.extend(struct.pack('<I', fn_id))
        payload.extend(struct.pack('<I', 0xFFFFFFFF))
        payload.extend(send_data)

        # Send via FSLP
        self.fslp.sendFrame(0x00, payload, len(payload))

        # Receive response
        response = self.fslp.readFrame(0x00, expected_receive_bytes + 12)

        # Parse response: [SEQ][FN_ID][STATUS][DATA]
        seq = struct.unpack('<I', response[0:4])[0]
        fn_id_echo = struct.unpack('<I', response[4:8])[0]
        status = struct.unpack('<I', response[8:12])[0]
        data = response[12:]

        self.command_count += 1
        return status == 0, data
```

### Step 3: Enhanced PyUSB Backend
Combine Y16 capture with SDK control:

```python
from camera_backends import ThermalBackend
from pyusb_thermal_backend import PyUSBThermalBackend
from usb_fslp_transport import USBFslpPort
import usb.core
import usb.util

class EnhancedPyUSBThermalBackend(ThermalBackend):
    """
    Enhanced PyUSB backend with both Y16 radiometric AND SDK control.

    Features:
    - 16-bit Y16 radiometric capture (via video interface)
    - Full SDK control via USB (via control interface)
    - FFC trigger
    - AGC mode control
    - FPA temperature reading
    - Runtime mode switching
    """

    VENDOR_ID = 0x09CB
    PRODUCT_ID_BOSON_640 = 0x4007
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 512

    def __init__(self):
        self.dev = None
        self.video_endpoint = None
        self.sdk_dispatcher = None
        self._is_opened = False

    def is_available(self) -> bool:
        """Check if Boson with WinUSB driver is available."""
        try:
            dev = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PRODUCT_ID_BOSON_640)
            return dev is not None
        except:
            return False

    def open(self) -> bool:
        """Open both video and control interfaces."""
        try:
            # Find device
            self.dev = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PRODUCT_ID_BOSON_640)
            if self.dev is None:
                return False

            # Discover endpoints
            video_ep, ctrl_in_ep, ctrl_out_ep = self._discover_endpoints()

            # Claim interfaces
            usb.util.claim_interface(self.dev, 0)  # Video
            usb.util.claim_interface(self.dev, 1)  # Control

            self.video_endpoint = video_ep

            # Initialize SDK dispatcher
            self.sdk_dispatcher = USBSDKDispatcher(self.dev, ctrl_in_ep, ctrl_out_ep)

            self._is_opened = True
            return True

        except Exception as e:
            logger.error(f"Failed to open enhanced PyUSB backend: {e}")
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read 16-bit Y16 frame from video interface."""
        if not self._is_opened:
            return False, None

        # Same as PyUSBThermalBackend
        frame_bytes = self.FRAME_WIDTH * self.FRAME_HEIGHT * 2
        total_bytes = frame_bytes + 12  # UVC header

        try:
            data = self.dev.read(self.video_endpoint, total_bytes, timeout=1000)
            frame_data = data[12:]  # Skip UVC header
            frame = np.frombuffer(frame_data, dtype=np.uint16)
            frame = frame.reshape(self.FRAME_HEIGHT, self.FRAME_WIDTH)
            return True, frame
        except Exception as e:
            logger.error(f"USB read error: {e}")
            return False, None

    def is_radiometric(self) -> bool:
        """Returns True - this backend provides true radiometric data."""
        return True

    def supports_sdk_control(self) -> bool:
        """Returns True - this backend supports SDK control via USB."""
        return True

    def get_temperature_map(self) -> Optional[np.ndarray]:
        """Convert 16-bit Y16 to temperature in Celsius."""
        ret, frame = self.read()
        if not ret:
            return None
        temp_k = frame.astype(np.float32) / 100.0
        temp_c = temp_k - 273.15
        return temp_c

    def trigger_ffc(self) -> bool:
        """Trigger FFC via USB SDK command."""
        if not self.sdk_dispatcher:
            return False

        # Function ID for bosonRunFFC: 0x00050007
        success, _ = self.sdk_dispatcher.send_command(
            fn_id=0x00050007,
            send_data=bytearray(),
            expected_receive_bytes=0
        )
        return success

    def get_fpa_temperature(self) -> Optional[float]:
        """Get FPA temperature via USB SDK command."""
        if not self.sdk_dispatcher:
            return None

        # Function ID for bosonGetFPATemperature: 0x00050008
        success, data = self.sdk_dispatcher.send_command(
            fn_id=0x00050008,
            send_data=bytearray(),
            expected_receive_bytes=2
        )

        if success and len(data) == 2:
            temp_raw = int.from_bytes(data, 'little')
            return temp_raw / 10.0 - 273.15  # Convert to Celsius
        return None

    def set_agc_roi(self, row_start, row_end, col_start, col_end) -> bool:
        """Set AGC region of interest via USB SDK command."""
        if not self.sdk_dispatcher:
            return False

        # Function ID for agcSetROI: 0x00090003
        # Parameters: FLR_ROI_T struct (4 × UINT_16)
        send_data = bytearray()
        send_data.extend(struct.pack('<H', row_start))
        send_data.extend(struct.pack('<H', row_end))
        send_data.extend(struct.pack('<H', col_start))
        send_data.extend(struct.pack('<H', col_end))

        success, _ = self.sdk_dispatcher.send_command(
            fn_id=0x00090003,
            send_data=send_data,
            expected_receive_bytes=0
        )
        return success
```

---

## Testing Strategy

### Prerequisites
1. Install WinUSB driver on Boson using Zadig
2. Verify PyUSB can detect device
3. Enumerate interfaces and endpoints

### Test Phase 1: USB Discovery
```python
# Test endpoint discovery
import usb.core
dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)
print(f"Device: {dev}")
for cfg in dev:
    for intf in cfg:
        print(f"Interface {intf.bInterfaceNumber}: Class {hex(intf.bInterfaceClass)}")
        for ep in intf:
            print(f"  Endpoint {hex(ep.bEndpointAddress)}")
```

### Test Phase 2: FSLP Transport
```python
# Test sending a simple command
from usb_fslp_transport import USBFslpPort
from enhanced_pyusb_thermal_backend import EnhancedPyUSBThermalBackend

backend = EnhancedPyUSBThermalBackend()
if backend.open():
    # Try triggering FFC
    success = backend.trigger_ffc()
    print(f"FFC triggered: {success}")

    # Try reading FPA temperature
    fpa_temp = backend.get_fpa_temperature()
    print(f"FPA temperature: {fpa_temp}°C")
```

### Test Phase 3: Simultaneous Y16 + SDK
```python
# Capture frames while controlling SDK
for i in range(100):
    # Read Y16 frame
    success, frame = backend.read()
    temp_map = backend.get_temperature_map()

    # Every 50 frames, trigger FFC
    if i % 50 == 0:
        backend.trigger_ffc()

    # Check FPA temperature
    fpa_temp = backend.get_fpa_temperature()
    print(f"Frame {i}: FPA={fpa_temp:.1f}°C, Center={temp_map[256, 320]:.1f}°C")
```

---

## Current Status

### ✅ Complete
1. Research and protocol documentation
2. USB FSLP transport layer (`usb_fslp_transport.py`)
3. Architecture design

### 🚧 In Progress
4. SDK dispatcher implementation
5. Enhanced backend class

### 📋 Next Steps
6. USB interface discovery utility
7. Full enhanced backend implementation
8. Integration with CameraManager
9. GUI backend selector update
10. Testing with actual hardware

---

## Benefits

### vs. Current OpenCV Backend
- ✅ Gains: True 16-bit radiometric (±2°C accuracy)
- ✅ Keeps: All SDK control (FFC, AGC, etc.)
- ⚠️ Requires: WinUSB driver installation

### vs. Current PyUSB Backend
- ✅ Gains: Full SDK control via USB
- ✅ Keeps: 16-bit Y16 radiometric
- ⚠️ Requires: Control interface implementation

### Overall
- **Best of both worlds**: 16-bit radiometric + SDK control
- **Matches FLIR app**: Same capabilities as official software
- **Single backend**: No need to switch between OpenCV and PyUSB
- **Production ready**: Once tested, this becomes the recommended backend

---

## Files Created

1. `BOSON_USB_PROTOCOL_RESEARCH.md` - Protocol research and documentation
2. `usb_fslp_transport.py` - FSLP over USB implementation
3. `ENHANCED_PYUSB_BACKEND_STATUS.md` - This status document

## Files To Create

4. `enhanced_pyusb_thermal_backend.py` - Enhanced backend class
5. `test_enhanced_backend.py` - Test script for validation

## Files To Modify

6. `camera_manager.py` - Add enhanced backend option
7. `radiometric_panel.py` - Add GUI selector for enhanced backend
8. `CAMERA_COMPATIBILITY_MATRIX.md` - Update with enhanced backend info

---

**Last Updated**: 2025-12-02

**Status**: Phase 2 Complete, Phase 3 Ready to Start
