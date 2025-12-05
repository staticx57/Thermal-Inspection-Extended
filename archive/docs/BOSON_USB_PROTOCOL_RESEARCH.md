# Boson USB Protocol Research

## Current Understanding

### FLIR SDK Command Protocol (FSLP)

The FLIR Boson SDK uses a custom protocol called FSLP (FLIR Serial Link Protocol) for command/control.

#### Command Packet Structure

**Send Payload (12-byte header + data):**
```
Bytes 0-3:   Sequence Number (UINT_32, little-endian)
Bytes 4-7:   Function ID (UINT_32, little-endian)
Bytes 8-11:  Marker (0xFFFFFFFF)
Bytes 12+:   Command-specific data
```

**Receive Payload (12-byte header + data):**
```
Bytes 0-3:   Sequence Number Echo (UINT_32)
Bytes 4-7:   Function ID Echo (UINT_32)
Bytes 8-11:  Status/Return Code (UINT_32)
Bytes 12+:   Response data
```

#### Example Commands

| Command | Function ID | Send Bytes | Receive Bytes | Description |
|---------|-------------|------------|---------------|-------------|
| `bosonRunFFC()` | 0x00050007 | 0 | 0 | Trigger FFC |
| `bosonGetFPATemperature()` | 0x00050008 | 0 | 2 | Get FPA temp (UINT_16) |
| `TLinearSetControl()` | 0x003E0001 | 4 | 0 | Enable/disable T-Linear |
| `agcSetROI()` | 0x00090003 | 8 | 0 | Set AGC ROI |

### Current SDK Communication

The FLIR SDK currently sends these commands over:
1. **COM Port (USB CDC)** - Virtual serial port over USB
2. **C DLL Serial** - Native Windows serial interface
3. **Python Serial** - PySerial library
4. **I2C** - Direct I2C (for embedded systems)

The Boson exposes a CDC/ACM (Communications Device Class) virtual COM port for SDK commands.

### Boson USB Architecture

The FLIR Boson has **TWO logical USB interfaces**:

#### 1. Video Interface (UVC - USB Video Class)
- **Purpose**: Stream thermal video frames
- **Protocol**: UVC (USB Video Class) standard
- **Driver**: UVC (Windows default) OR WinUSB (for direct access)
- **Endpoint**: Bulk IN endpoint for frame data
- **Frame Format**:
  - UVC: 8-bit AGC frames (T-Linear processed)
  - Direct USB: 16-bit Y16 radiometric frames

#### 2. Control Interface (CDC/ACM)
- **Purpose**: SDK command/control
- **Protocol**: CDC/ACM (virtual serial port)
- **Driver**: USB Serial (usbser.sys)
- **Appears As**: COM port (e.g., COM6)
- **Endpoint**: Bulk IN/OUT for bidirectional communication
- **Commands**: FSLP protocol packets

### Why Current PyUSB Backend Lacks SDK Control

The current `pyusb_thermal_backend.py` implementation:
1. Uses Zadig to replace **entire USB driver** with WinUSB
2. This breaks BOTH interfaces:
   - Video interface: Works with PyUSB (16-bit Y16)
   - Control interface: **Broken** (COM port disappears)
3. No implementation of FSLP over direct USB

### Solution: Hybrid USB Access

**Option 1: LibUSB Filter Driver** ⭐ RECOMMENDED
- Install LibUSB **filter** driver (not replacement)
- Keeps UVC driver active for video
- Adds PyUSB access to control interface
- Both interfaces accessible simultaneously

**Option 2: Direct USB CDC Communication**
- Keep WinUSB driver
- Implement FSLP protocol over USB bulk endpoints
- Find control interface endpoints
- Send/receive FSLP packets via PyUSB control transfers

**Option 3: Dual Backend (Current Workaround)**
- Use OpenCV backend (UVC) for 8-bit + SDK
- Use PyUSB backend (WinUSB) for 16-bit (no SDK)
- Cannot have both simultaneously

## Implementation Plan: Enhanced PyUSB Backend

### Goal
Create `enhanced_pyusb_thermal_backend.py` with:
- ✅ 16-bit Y16 radiometric capture (via video interface)
- ✅ Full SDK control (via control interface over USB)
- ✅ Match FLIR app capabilities

### Approach

#### Step 1: USB Device Inspection
Create script to enumerate Boson USB interfaces when WinUSB installed:
```python
import usb.core
import usb.util

dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)

for cfg in dev:
    for intf in cfg:
        print(f"Interface {intf.bInterfaceNumber}")
        print(f"  Class: {intf.bInterfaceClass}")
        print(f"  Subclass: {intf.bInterfaceSubClass}")
        for ep in intf:
            print(f"  Endpoint: {hex(ep.bEndpointAddress)}")
            print(f"    Type: {ep.bmAttributes & 0x03}")
```

Expected output:
- Interface 0: Video (UVC) - Endpoint 0x81 (Bulk IN)
- Interface 1: Control (CDC) - Endpoints 0x82 (Bulk IN), 0x02 (Bulk OUT)

#### Step 2: FSLP over USB Implementation
Create USB transport layer for FSLP:
```python
class USBFslp:
    """FSLP over direct USB (not serial)."""

    def __init__(self, dev, ctrl_in_ep, ctrl_out_ep):
        self.dev = dev
        self.ctrl_in_ep = ctrl_in_ep
        self.ctrl_out_ep = ctrl_out_ep

    def sendFrame(self, channel, payload, length):
        """Send FSLP frame via USB bulk transfer."""
        # Add FSLP framing bytes (START, CHANNEL, LENGTH, CRC, STOP)
        frame = self._frame_payload(channel, payload, length)
        self.dev.write(self.ctrl_out_ep, frame, timeout=1000)

    def readFrame(self, channel, expected_length):
        """Read FSLP frame via USB bulk transfer."""
        data = self.dev.read(self.ctrl_in_ep, expected_length + 20, timeout=1000)
        return self._unframe_payload(data)
```

#### Step 3: Enhanced Backend Class
```python
class EnhancedPyUSBThermalBackend(ThermalBackend):
    """
    Enhanced PyUSB backend with both Y16 radiometric AND SDK control.

    Features:
    - 16-bit Y16 radiometric capture (video interface)
    - Full SDK control via USB (control interface)
    - FFC trigger
    - AGC mode control
    - FPA temperature reading
    - Runtime mode switching
    """

    def __init__(self):
        self.dev = None
        self.video_interface = None
        self.control_interface = None
        self.video_endpoint = None
        self.control_in_endpoint = None
        self.control_out_endpoint = None
        self.sdk_dispatcher = None
        self.sequence_number = 0

    def open(self) -> bool:
        # Find Boson device
        self.dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)

        # Claim video interface (Interface 0)
        self.video_interface = self.dev[0].interfaces()[0]
        usb.util.claim_interface(self.dev, self.video_interface)
        self.video_endpoint = self.video_interface[0]

        # Claim control interface (Interface 1)
        self.control_interface = self.dev[0].interfaces()[1]
        usb.util.claim_interface(self.dev, self.control_interface)
        self.control_in_endpoint = self.control_interface[0]
        self.control_out_endpoint = self.control_interface[1]

        # Initialize USB FSLP transport
        usb_fslp = USBFslp(self.dev, self.control_in_endpoint, self.control_out_endpoint)

        # Initialize SDK dispatcher
        from SDK_Dispatcher_USB import USBDispatcher
        self.sdk_dispatcher = USBDispatcher(usb_fslp)

        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read 16-bit Y16 frame from video interface."""
        # Same as current PyUSB backend
        # ...

    def trigger_ffc(self) -> bool:
        """Trigger FFC via USB SDK command."""
        return self.sdk_dispatcher.send_command(
            fn_id=0x00050007,
            send_data=bytearray(),
            expected_receive_bytes=0
        )

    def get_fpa_temperature(self) -> Optional[float]:
        """Get FPA temperature via USB SDK command."""
        success, data = self.sdk_dispatcher.send_command(
            fn_id=0x00050008,
            send_data=bytearray(),
            expected_receive_bytes=2
        )
        if success:
            temp_raw = int.from_bytes(data, 'little')
            return temp_raw / 10.0 - 273.15  # Convert to Celsius
        return None

    def is_radiometric(self) -> bool:
        return True

    def supports_sdk_control(self) -> bool:
        return True
```

## Testing Plan

### Phase 1: USB Inspection ✅
- [x] Document FSLP protocol structure
- [ ] Install WinUSB driver with Zadig
- [ ] Run USB device inspection script
- [ ] Identify video and control interface endpoints
- [ ] Capture USB traffic from FLIR app (Wireshark + USBPcap)

### Phase 2: FSLP over USB
- [ ] Implement USBFslp transport class
- [ ] Test sending/receiving raw FSLP frames
- [ ] Verify frame structure and CRC
- [ ] Test sequence number handling

### Phase 3: SDK Commands
- [ ] Implement USBDispatcher (SDK over USB)
- [ ] Test bosonRunFFC command
- [ ] Test bosonGetFPATemperature command
- [ ] Test agcSetROI command
- [ ] Test all critical SDK functions

### Phase 4: Enhanced Backend
- [ ] Create enhanced_pyusb_thermal_backend.py
- [ ] Integrate Y16 video capture
- [ ] Integrate USB SDK control
- [ ] Test simultaneous video + SDK
- [ ] Verify FFC, AGC, telemetry

### Phase 5: Integration
- [ ] Add enhanced backend to CameraManager
- [ ] Update GUI backend selector
- [ ] Test runtime switching
- [ ] Performance testing
- [ ] Documentation

## Challenges and Solutions

### Challenge 1: FSLP Framing
**Problem**: FSLP has framing bytes (START, STOP, CRC) for serial transport
**Solution**: Reverse-engineer framing from SDK source or USB captures

### Challenge 2: USB Interface Identification
**Problem**: Need to identify which interface is control vs video
**Solution**: Check bInterfaceClass (0x0E = Video, 0x02 = CDC)

### Challenge 3: Driver Conflicts
**Problem**: WinUSB replaces both interfaces, breaking CDC
**Solution**: Use LibUSB filter driver OR implement CDC over WinUSB

### Challenge 4: Endpoint Discovery
**Problem**: Endpoint addresses may vary
**Solution**: Programmatic discovery based on endpoint type (Bulk IN/OUT)

## References

- **bosonsdkraw.txt** - FLIR Boson SDK Interface Description Document
- **Client_API.py** - SDK high-level API wrapper
- **Client_Packager.py** - SDK command packaging
- **Client_Dispatcher.py** - FSLP protocol implementation
- **PyUSB Documentation** - https://github.com/pyusb/pyusb
- **USB Video Class Spec** - https://www.usb.org/document-library/video-class-v11-document-set
- **USB CDC Spec** - https://www.usb.org/document-library/class-definitions-communication-devices-12

## Next Steps

1. Install WinUSB driver (already know how via Zadig)
2. Run USB device inspection to map interfaces
3. Capture USB traffic from FLIR app to see actual FSLP frames
4. Implement USBFslp transport layer
5. Test SDK commands over USB
6. Create enhanced backend

---

**Status**: Research phase complete, ready for implementation

**Updated**: 2025-12-02
