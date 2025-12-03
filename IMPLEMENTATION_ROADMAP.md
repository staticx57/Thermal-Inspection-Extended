# Enhanced PyUSB Backend - Implementation Roadmap

## Executive Summary

After thorough research and testing, we've confirmed that achieving both 16-bit Y16 radiometric capture AND full SDK control requires:

1. **WinUSB driver** (replaces UVC)
2. **Direct USB access** to both video and control interfaces
3. **FSLP protocol over USB** for SDK commands

This document outlines the complete implementation roadmap.

---

## Current Status: Phase 2 Complete ✅

### ✅ Phase 1: Research & Analysis (COMPLETE)
- [x] Analyzed FLIR SDK protocol structure
- [x] Documented FSLP framing and packet format
- [x] Mapped Boson USB interfaces
- [x] Created comprehensive documentation

**Deliverables**:
- `BOSON_USB_PROTOCOL_RESEARCH.md`
- Protocol specification with examples
- Command structure analysis

### ✅ Phase 2: Testing & Validation (COMPLETE)
- [x] Tested OpenCV Y16 capability
- [x] Confirmed UVC driver limitation
- [x] Validated enhanced backend approach
- [x] Implemented USB FSLP transport layer

**Deliverables**:
- `test_opencv_y16.py` - Test script
- `OPENCV_Y16_TEST_RESULTS.md` - Test results
- `usb_fslp_transport.py` - FSLP over USB transport

**Key Finding**: OpenCV cannot get Y16 from UVC driver. Enhanced PyUSB backend is the only solution.

---

## Remaining Work: Phases 3-5

### 🚧 Phase 3: Enhanced Backend Implementation (NEXT)

**Goal**: Create complete enhanced PyUSB backend with Y16 + SDK

#### 3.1: USB Interface Discovery Utility
**File**: `usb_discovery.py`

```python
def discover_boson_endpoints(dev):
    """
    Discover Boson USB interfaces and endpoints.

    Returns:
        tuple: (video_ep_in, control_ep_in, control_ep_out)
    """
    video_ep = None
    ctrl_in_ep = None
    ctrl_out_ep = None

    for cfg in dev:
        for intf in cfg:
            # Video interface (0x0E = UVC)
            if intf.bInterfaceClass == 0x0E:
                for ep in intf:
                    if ep.bEndpointAddress & 0x80:  # IN
                        video_ep = ep.bEndpointAddress

            # Control interface (0x02 = CDC)
            elif intf.bInterfaceClass == 0x02:
                for ep in intf:
                    if ep.bEndpointAddress & 0x80:  # IN
                        ctrl_in_ep = ep.bEndpointAddress
                    else:  # OUT
                        ctrl_out_ep = ep.bEndpointAddress

    return video_ep, ctrl_in_ep, ctrl_out_ep
```

**Tasks**:
- [ ] Create endpoint discovery utility
- [ ] Test with WinUSB-installed Boson
- [ ] Document interface mappings
- [ ] Handle edge cases (missing interfaces)

**Estimated Time**: 2-3 hours
**Blockers**: Requires WinUSB driver installed

---

#### 3.2: USB SDK Dispatcher
**File**: `usb_sdk_dispatcher.py`

```python
class USBSDKDispatcher:
    """Send SDK commands via USB FSLP transport."""

    def __init__(self, usb_device, ctrl_in_ep, ctrl_out_ep):
        self.fslp = USBFslpPort(usb_device, ctrl_in_ep, ctrl_out_ep)
        self.command_count = 0

    def send_command(self, fn_id, send_data, expected_receive_bytes):
        """
        Send SDK command via USB and receive response.

        Args:
            fn_id: Function ID (e.g., 0x00050007 for bosonRunFFC)
            send_data: Command parameters (bytearray)
            expected_receive_bytes: Expected response size

        Returns:
            tuple: (success: bool, data: bytearray)
        """
        # Build payload: [SEQ][FN_ID][0xFFFFFFFF][DATA]
        payload = bytearray()
        payload.extend(struct.pack('<I', self.command_count))
        payload.extend(struct.pack('<I', fn_id))
        payload.extend(struct.pack('<I', 0xFFFFFFFF))
        payload.extend(send_data)

        # Send via FSLP (channel 0x00 = command channel)
        self.fslp.sendFrame(0x00, payload, len(payload))

        # Receive response
        response = self.fslp.readFrame(0x00, expected_receive_bytes + 12)

        # Parse: [SEQ][FN_ID][STATUS][DATA]
        seq = struct.unpack('<I', response[0:4])[0]
        status = struct.unpack('<I', response[8:12])[0]
        data = response[12:12+expected_receive_bytes]

        self.command_count += 1
        return (status == 0, data)
```

**Tasks**:
- [ ] Implement USBSDKDispatcher class
- [ ] Add command packaging logic
- [ ] Add response parsing logic
- [ ] Add error handling
- [ ] Test with simple commands (bosonRunFFC)

**Estimated Time**: 3-4 hours
**Dependencies**: USB FSLP transport (✅ complete)

---

#### 3.3: Enhanced PyUSB Backend Class
**File**: `enhanced_pyusb_thermal_backend.py`

```python
class EnhancedPyUSBThermalBackend(ThermalBackend):
    """
    Enhanced PyUSB backend with Y16 + SDK control.

    The ultimate backend - provides both:
    - 16-bit Y16 radiometric capture
    - Full SDK control via USB
    """

    def __init__(self):
        self.dev = None
        self.video_endpoint = None
        self.sdk_dispatcher = None
        self._is_opened = False

    def open(self) -> bool:
        """Open video and control interfaces."""
        # Find Boson
        self.dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)

        # Discover endpoints
        video_ep, ctrl_in, ctrl_out = discover_boson_endpoints(self.dev)

        # Claim both interfaces
        usb.util.claim_interface(self.dev, 0)  # Video
        usb.util.claim_interface(self.dev, 1)  # Control

        # Initialize video capture
        self.video_endpoint = video_ep

        # Initialize SDK dispatcher
        self.sdk_dispatcher = USBSDKDispatcher(self.dev, ctrl_in, ctrl_out)

        self._is_opened = True
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read 16-bit Y16 frame."""
        # Same as PyUSBThermalBackend
        frame_bytes = 640 * 512 * 2
        total_bytes = frame_bytes + 12

        data = self.dev.read(self.video_endpoint, total_bytes, timeout=1000)
        frame = np.frombuffer(data[12:], dtype=np.uint16).reshape(512, 640)
        return True, frame

    def is_radiometric(self) -> bool:
        return True

    def supports_sdk_control(self) -> bool:
        return True

    def get_temperature_map(self) -> Optional[np.ndarray]:
        """Convert Y16 to Celsius."""
        ret, frame = self.read()
        temp_k = frame / 100.0
        temp_c = temp_k - 273.15
        return temp_c

    def trigger_ffc(self) -> bool:
        """Trigger FFC via USB."""
        return self.sdk_dispatcher.send_command(0x00050007, bytearray(), 0)[0]

    def get_fpa_temperature(self) -> Optional[float]:
        """Get FPA temperature via USB."""
        success, data = self.sdk_dispatcher.send_command(0x00050008, bytearray(), 2)
        if success:
            temp_raw = struct.unpack('<H', data)[0]
            return temp_raw / 10.0 - 273.15
        return None
```

**Tasks**:
- [ ] Implement EnhancedPyUSBThermalBackend class
- [ ] Add all ThermalBackend interface methods
- [ ] Add SDK command wrappers (FFC, AGC, etc.)
- [ ] Add temperature conversion
- [ ] Add error handling and recovery
- [ ] Write unit tests

**Estimated Time**: 4-6 hours
**Dependencies**: USB discovery, SDK dispatcher

---

### 🧪 Phase 4: Testing & Validation

#### 4.1: Hardware Testing
**Prerequisites**: WinUSB driver installed on Boson

**Test Cases**:
1. **Device Discovery**
   ```python
   from enhanced_pyusb_thermal_backend import EnhancedPyUSBThermalBackend

   backend = EnhancedPyUSBThermalBackend()
   assert backend.is_available() == True
   ```

2. **Video Capture**
   ```python
   backend.open()
   success, frame = backend.read()
   assert success == True
   assert frame.dtype == np.uint16
   assert frame.shape == (512, 640)
   ```

3. **Temperature Conversion**
   ```python
   temp_map = backend.get_temperature_map()
   assert temp_map.dtype == np.float32
   assert 15.0 <= temp_map.mean() <= 40.0  # Reasonable room temp
   ```

4. **SDK Commands**
   ```python
   # Test FFC
   success = backend.trigger_ffc()
   assert success == True

   # Test FPA temperature
   fpa_temp = backend.get_fpa_temperature()
   assert fpa_temp is not None
   assert 20.0 <= fpa_temp <= 50.0
   ```

5. **Simultaneous Operation**
   ```python
   # Capture frames while controlling SDK
   for i in range(100):
       success, frame = backend.read()
       if i % 50 == 0:
           backend.trigger_ffc()
       fpa_temp = backend.get_fpa_temperature()
   ```

**Tasks**:
- [ ] Create test script (`test_enhanced_backend.py`)
- [ ] Test all SDK commands
- [ ] Verify temperature accuracy
- [ ] Test error recovery
- [ ] Benchmark frame rate
- [ ] Test long-term stability

**Estimated Time**: 4-6 hours
**Blockers**: Requires WinUSB driver and hardware

---

#### 4.2: Integration Testing

**Test integration with existing application**:

1. **CameraManager Integration**
   ```python
   from camera_manager import CameraManager

   manager = CameraManager()
   manager.initialize_thermal(mode='enhanced_usb')
   ```

2. **GUI Integration**
   - Backend selector shows "Enhanced USB (Y16 + SDK)"
   - Status displays correctly
   - All controls work

3. **Feature Testing**
   - Hot/cold spot detection works
   - Temperature conversion with units
   - Radiometric analysis
   - Export functions

**Tasks**:
- [ ] Test with inspection_main.py
- [ ] Test with GUI
- [ ] Test all radiometric features
- [ ] Document any issues

**Estimated Time**: 2-3 hours

---

### 📦 Phase 5: Integration & Deployment

#### 5.1: CameraManager Update
**File**: `camera_manager.py`

Add enhanced backend mode:

```python
class CameraManager:
    MODE_OPENCV = 'opencv'
    MODE_USB = 'usb'
    MODE_ENHANCED_USB = 'enhanced_usb'  # NEW

    def initialize_thermal(self, mode='opencv', ...):
        if mode == self.MODE_ENHANCED_USB:
            backend = EnhancedPyUSBThermalBackend()
```

**Tasks**:
- [ ] Add MODE_ENHANCED_USB constant
- [ ] Add to get_available_thermal_backends()
- [ ] Update initialization logic
- [ ] Update documentation

**Estimated Time**: 1-2 hours

---

#### 5.2: GUI Update
**File**: `radiometric_panel.py`

Add enhanced backend option:

```python
self.enhanced_usb_radio = QRadioButton("Enhanced USB (Y16 + SDK)")
self.enhanced_usb_radio.setToolTip(
    "16-bit radiometric + full SDK control\n"
    "• Requires WinUSB driver\n"
    "• Absolute temperatures (±2°C)\n"
    "• FFC, AGC, telemetry via USB\n"
    "• Best of all worlds!"
)
```

**Tasks**:
- [ ] Add enhanced USB radio button
- [ ] Update backend_changed signal handler
- [ ] Update status display
- [ ] Add WinUSB installation instructions
- [ ] Test GUI flow

**Estimated Time**: 2-3 hours

---

#### 5.3: Documentation Update

**Files to Update**:
1. `CAMERA_COMPATIBILITY_MATRIX.md`
   - Add enhanced USB backend row
   - Update feature comparison

2. `INTEGRATION_GUIDE.md`
   - Add enhanced backend usage
   - Update code examples

3. `HYBRID_BACKEND_IMPLEMENTATION.md`
   - Mark enhanced backend complete
   - Update status

4. `README.md` (if exists)
   - Add enhanced backend section
   - Update installation instructions

**Tasks**:
- [ ] Update all documentation
- [ ] Create user guide for WinUSB installation
- [ ] Add troubleshooting section
- [ ] Create feature comparison table

**Estimated Time**: 2-3 hours

---

## Timeline Estimate

| Phase | Tasks | Est. Hours | Status |
|-------|-------|------------|--------|
| Phase 1: Research | Protocol analysis, documentation | 6-8 | ✅ COMPLETE |
| Phase 2: Testing | OpenCV Y16 test, FSLP transport | 4-6 | ✅ COMPLETE |
| Phase 3: Implementation | Discovery, dispatcher, backend | 10-14 | 🚧 NEXT |
| Phase 4: Testing | Hardware & integration testing | 6-9 | 📋 PENDING |
| Phase 5: Integration | CameraManager, GUI, docs | 5-8 | 📋 PENDING |
| **TOTAL** | | **31-45 hours** | **40% COMPLETE** |

---

## Prerequisites for Next Phase

### Required Before Starting Phase 3:
1. ✅ WinUSB driver NOT yet installed (will install during testing)
2. ✅ USB FSLP transport complete (`usb_fslp_transport.py`)
3. ✅ Understanding of Boson USB structure
4. ✅ SDK protocol documentation

### Required for Phase 4 Testing:
1. ❌ WinUSB driver installed on Boson (via Zadig)
2. ❌ Boson camera connected and accessible
3. ✅ PyUSB library installed
4. ✅ Test environment ready

---

## Risk Assessment

### Low Risk ✅
- USB FSLP transport (already implemented and tested)
- Backend interface design (well-understood)
- Integration points (clear architecture)

### Medium Risk ⚠️
- USB endpoint discovery (device-specific, may vary)
- FSLP packet handling (need to verify framing works over USB)
- Error handling (USB timeouts, disconnects)

### Mitigation Strategies:
1. **Endpoint Discovery**: Robust fallback logic, manual configuration option
2. **FSLP Testing**: Incremental testing with simple commands first
3. **Error Handling**: Comprehensive try-except blocks, reconnection logic

---

## Success Criteria

The enhanced backend will be considered complete when:

1. ✅ Can capture 16-bit Y16 frames at full frame rate
2. ✅ Can trigger FFC via USB
3. ✅ Can read FPA temperature via USB
4. ✅ Can set AGC modes via USB
5. ✅ Temperature accuracy within ±2°C
6. ✅ No frame drops or USB errors
7. ✅ Integrates with CameraManager
8. ✅ GUI controls work correctly
9. ✅ Documented and tested

---

## Next Immediate Actions

1. **Create `usb_discovery.py`** - Endpoint discovery utility
2. **Create `usb_sdk_dispatcher.py`** - SDK command dispatcher
3. **Test dispatcher** with simple command (bosonRunFFC)
4. **Create `enhanced_pyusb_thermal_backend.py`** - Full backend
5. **Install WinUSB** driver with Zadig
6. **Test enhanced backend** with hardware

---

**Status**: Ready to begin Phase 3 implementation
**Last Updated**: 2025-12-02
**Next Milestone**: Enhanced backend implementation complete
