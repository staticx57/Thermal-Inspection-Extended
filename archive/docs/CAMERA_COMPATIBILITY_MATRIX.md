# Camera Backend Compatibility Matrix

## Overview

This matrix shows which camera combinations work together with different driver configurations.

---

## Quick Reference

| FLIR Boson Driver | Boson Backend | Firefly Works? | Boson Radiometric | Both Cameras Work? |
|-------------------|---------------|----------------|-------------------|-------------------|
| **UVC (default)** | OpenCV 8-bit | ✅ **Yes** | ❌ No | ✅ **YES** |
| **WinUSB (Zadig)** | PyUSB 16-bit | ✅ **Yes** | ✅ **Yes** | ✅ **YES** |

**Answer: All combinations work! The Firefly is never affected.**

---

## Detailed Compatibility Matrix

### Configuration 1: UVC Driver (Windows Default) ✅ RECOMMENDED

**FLIR Boson:**
- Driver: UVC (USB Video Class) - Windows default
- Backend: OpenCV 8-bit
- Bit Depth: 8-bit (0-255)
- Radiometric: No (AGC processed)
- SDK Control: ✅ Yes (via COM port)
- FPA Temperature: ✅ Yes
- Visual Quality: ✅ Excellent (T-Linear)

**Firefly RGB:**
- Driver: Spinnaker (PySpin)
- Backend: PySpin
- Status: ✅ **Completely unaffected**
- Works: ✅ **Yes**

**Both Cameras:**
- Work Together: ✅ **YES**
- Recommended: ✅ **YES** (works out of box)
- Use Case: Visual inspection, SDK control needed

---

### Configuration 2: WinUSB Driver (Zadig Install)

**FLIR Boson:**
- Driver: WinUSB (installed via Zadig)
- Backend: PyUSB 16-bit
- Bit Depth: 16-bit (0-65535)
- Radiometric: ✅ Yes (absolute temps ±2°C)
- SDK Control: ❌ No (direct USB only)
- FPA Temperature: ❌ No
- Visual Quality: ✅ Good (raw data)

**Firefly RGB:**
- Driver: Spinnaker (PySpin) - **unchanged**
- Backend: PySpin
- Status: ✅ **Completely unaffected**
- Works: ✅ **Yes**

**Both Cameras:**
- Work Together: ✅ **YES**
- Recommended: ✅ **YES** (for radiometric measurements)
- Use Case: Absolute temperature measurements

---

## Why Firefly is Never Affected

### 1. Different USB Device IDs

| Camera | Vendor ID | Product ID | Device |
|--------|-----------|------------|---------|
| FLIR Boson | 0x09CB | 0x4007 | Specific to Boson |
| Firefly FFY-U3-16S2C | 0x1E10 | Device-specific | FLIR machine vision |

**WinUSB is installed ONLY for VID:PID 09CB:4007 (Boson)**

### 2. Separate Driver Stacks

```
┌─────────────────────┐     ┌─────────────────────┐
│   FLIR Boson        │     │   Firefly RGB       │
│   VID:PID 09CB:4007 │     │   VID:PID 1E10:XXXX │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           │                           │
    ┌──────▼──────┐            ┌───────▼────────┐
    │ UVC Driver  │            │ Spinnaker      │
    │  or WinUSB  │            │ Driver (PySpin)│
    │  (Boson     │            │ (Never changes)│
    │   only)     │            │                │
    └─────────────┘            └────────────────┘
```

### 3. Independent Initialization

The cameras are initialized separately:

```python
# Thermal camera (Boson) - uses CameraManager
camera_manager.initialize_thermal(mode='opencv')  # or 'usb'

# RGB camera (Firefly) - completely independent
firefly_camera = FireflyCamera()  # Uses PySpin, unaffected
```

---

## Driver Installation Impact

### Installing WinUSB on Boson

**What Changes:**
- ✅ FLIR Boson driver: UVC → WinUSB
- ✅ Boson backend: OpenCV → PyUSB available
- ✅ Boson capabilities: 16-bit radiometric now available

**What Doesn't Change:**
- ✅ Firefly driver: Still Spinnaker/PySpin
- ✅ Firefly functionality: 100% unchanged
- ✅ Firefly initialization: Exactly the same

**Verification:**
```bash
# Check Firefly is still working
python -c "import PySpin; print(PySpin.System.GetInstance().GetCameras().GetSize())"
# Should still show 1 camera (Firefly)
```

---

## All Valid Camera Combinations

### Combination 1: Both Cameras, UVC Driver ✅

```
Thermal: FLIR Boson (UVC) → OpenCV 8-bit
RGB:     Firefly → PySpin
Status:  ✅ Works perfectly (default configuration)
```

### Combination 2: Both Cameras, WinUSB Driver ✅

```
Thermal: FLIR Boson (WinUSB) → PyUSB 16-bit
RGB:     Firefly → PySpin
Status:  ✅ Works perfectly (radiometric mode)
```

### Combination 3: Thermal Only, UVC ✅

```
Thermal: FLIR Boson (UVC) → OpenCV 8-bit
RGB:     None
Status:  ✅ Works (thermal-only mode)
```

### Combination 4: Thermal Only, WinUSB ✅

```
Thermal: FLIR Boson (WinUSB) → PyUSB 16-bit
RGB:     None
Status:  ✅ Works (radiometric thermal-only)
```

### Combination 5: RGB Only ✅

```
Thermal: None
RGB:     Firefly → PySpin
Status:  ✅ Works (RGB-only mode)
```

---

## Feature Compatibility Matrix

| Feature | UVC + OpenCV | WinUSB + PyUSB | Notes |
|---------|--------------|----------------|-------|
| **8-bit Thermal** | ✅ Yes | ❌ No | UVC provides AGC frames |
| **16-bit Radiometric** | ❌ No | ✅ Yes | WinUSB provides Y16 frames |
| **SDK Control** | ✅ Yes | ❌ No | COM port independent of video driver |
| **FFC Trigger** | ✅ Yes | ❌ No | Requires SDK |
| **AGC Modes** | ✅ Yes | ❌ No | Requires SDK |
| **FPA Temperature** | ✅ Yes | ❌ No | Requires SDK |
| **Absolute Temps** | ❌ No (estimate) | ✅ Yes (±2°C) | True radiometric |
| **Firefly RGB** | ✅ Yes | ✅ Yes | **Always works!** |
| **Runtime Switch** | ✅ Yes | ✅ Yes | Via CameraManager |

---

## Workflow Recommendations

### Workflow 1: Visual Inspection Priority

**Use:** UVC Driver (default)

**Cameras:**
- Thermal: OpenCV 8-bit (excellent visual quality)
- RGB: Firefly PySpin (high resolution)

**Best For:**
- Visual inspection tasks
- SDK control needed (FFC, AGC)
- Fusion overlay
- Real-time monitoring

### Workflow 2: Temperature Measurement Priority

**Use:** WinUSB Driver (Zadig)

**Cameras:**
- Thermal: PyUSB 16-bit (absolute temperatures)
- RGB: Firefly PySpin (high resolution)

**Best For:**
- Precise temperature measurements
- Quality control with specs
- Scientific measurements
- Compliance testing (±2°C accuracy)

### Workflow 3: Hybrid (Runtime Switching)

**Use:** Either driver, switch as needed

**Approach:**
1. Start with UVC (8-bit) for visual inspection
2. Install WinUSB when precision needed
3. Switch backends via GUI
4. Revert to UVC if SDK control needed

**Best For:**
- Development
- Research
- Flexibility
- Testing different modes

---

## Installation Commands

### Check Current Drivers

```bash
# Windows Device Manager
1. Open Device Manager
2. Look under "Cameras" or "Universal Serial Bus devices"
3. Find "FLIR Boson" - check driver details
```

### Install WinUSB (for 16-bit mode)

```bash
# Download Zadig: https://zadig.akeo.ie/
1. Run Zadig as Administrator
2. Options → List All Devices
3. Select "FLIR Boson" from dropdown
4. Target driver: WinUSB
5. Click "Replace Driver"
6. Wait for installation
7. Replug camera
```

### Restore UVC (for 8-bit + SDK mode)

```bash
# Via Device Manager
1. Device Manager → Universal Serial Bus devices
2. Right-click "FLIR Boson (WinUSB)"
3. Update Driver → Browse → Let me pick
4. Select "USB Video Device" (UVC)
5. Install
6. Replug camera
```

---

## Troubleshooting

### Problem: "Firefly not working after WinUSB install"

**Cause:** Misunderstanding - Firefly is never affected

**Verification:**
```python
import PySpin
system = PySpin.System.GetInstance()
cam_list = system.GetCameras()
print(f"Firefly cameras: {cam_list.GetSize()}")
# Should show 1 (Firefly is fine)
```

### Problem: "Can't switch to USB backend"

**Cause:** WinUSB driver not installed on Boson

**Solution:**
1. Install WinUSB with Zadig
2. Target only FLIR Boson (VID:PID 09CB:4007)
3. Do NOT install on Firefly!

### Problem: "Lost SDK control after WinUSB"

**Expected:** WinUSB mode doesn't support SDK

**Solutions:**
1. Switch back to UVC driver for SDK
2. Or: Use UVC backend via CameraManager
3. Backend switching allows both as needed

---

## Summary

### Key Points

1. **Firefly is NEVER affected by Boson driver changes**
   - Different USB device IDs
   - Separate driver stacks
   - Independent initialization

2. **All camera combinations work**
   - UVC + Firefly: ✅ Works
   - WinUSB + Firefly: ✅ Works
   - Either backend alone: ✅ Works

3. **Driver choice is ONLY for Boson**
   - UVC: 8-bit AGC + SDK control
   - WinUSB: 16-bit radiometric (no SDK)

4. **Hybrid backend enables flexibility**
   - Switch between 8-bit and 16-bit
   - Firefly always available
   - No manual driver juggling needed

---

## Quick Decision Chart

```
Do you need absolute temperatures (±2°C)?
│
├─ Yes → Install WinUSB on Boson only
│         Firefly: Unchanged ✅
│         Both work together ✅
│
└─ No → Keep UVC (default)
          SDK control available ✅
          Firefly: Works ✅
          Both work together ✅

Either way: Firefly is NEVER affected! ✅
```

---

## References

- **HYBRID_BACKEND_IMPLEMENTATION.md** - Backend architecture details
- **INTEGRATION_GUIDE.md** - Implementation steps
- **DIRECT_USB_CAPTURE_GUIDE.md** - WinUSB installation details
- [Zadig Tool](https://zadig.akeo.ie/) - WinUSB driver installer
