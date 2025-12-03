# flirpy Backend + SDK Control - Usage Guide

## Quick Answer

**YES**, you can configure the camera while using flirpy!

The Boson has TWO separate USB interfaces:
- **Video Interface (UVC)** → flirpy uses this for 16-bit Y16 capture
- **Serial Interface (COM port)** → SDK uses this for control

They work **independently** and should work **simultaneously**.

---

## How to Use flirpy Backend with SDK Control

### Step 1: Launch Application with SDK Enabled

```bash
python inspection_main.py --enable-boson-sdk --boson-com-port COM6
```

**Important Flags**:
- `--enable-boson-sdk` - Enables Boson SDK connection
- `--boson-com-port COM6` - COM port (check Device Manager if unsure)

### Step 2: Select flirpy Backend in GUI

1. Open the application
2. Go to: **Analysis Tab** → **Radiometric Panel**
3. Scroll to: **Camera Backend** section
4. Select: **"16-bit flirpy (Best of Both)"**
5. Click: **"Apply Backend Change"**

The camera will restart and begin capturing 16-bit Y16 frames.

### Step 3: Use SDK Controls

While flirpy is capturing, you can use SDK controls:

**Go to: Cameras Tab → Boson SDK Panel**

Available controls:
- **FFC Trigger** - Force flat field correction
- **AGC Mode** - Set automatic gain control
- **Gain Mode** - Set gain (HIGH/LOW/AUTO)
- **FPA Temperature** - Read sensor temperature
- **Camera Info** - Serial number, firmware version

All of these work via COM port while flirpy captures via UVC!

---

## Troubleshooting COM Port Issues

If SDK connection fails with "error 255":

### 1. Check Correct COM Port

**Windows Device Manager**:
1. Open Device Manager
2. Expand "Ports (COM & LPT)"
3. Look for "USB Serial Device" or "FLIR Boson"
4. Note the COM port number (e.g., COM6, COM7)

### 2. Check if COM Port is in Use

```bash
# Check if another application is using the COM port
# Close any running instances of:
- FLIR ResearchIR
- FLIR Thermal Studio
- Other Python scripts using BosonSDK
```

### 3. Try Different COM Port

```bash
# Try COM7 if COM6 doesn't work
python inspection_main.py --enable-boson-sdk --boson-com-port COM7
```

### 4. Check USB Cable

- Ensure using USB cable with **data lines** (not just power)
- Try different USB port on computer
- USB 3.0 ports recommended

---

## Alternative: Pre-Configure Camera

If simultaneous access doesn't work reliably, you can pre-configure:

### Configure First, Then Capture

```python
# 1. Configure camera (short script)
from boson_sdk_wrapper import BosonSDK

sdk = BosonSDK(com_port='COM6')
if sdk.open():
    sdk.set_agc_mode('LINEAR')  # Set T-Linear mode
    sdk.trigger_ffc()            # Do FFC
    sdk.close()

# 2. Now launch application with flirpy
# Settings persist until power cycle
```

Then run application normally - flirpy will capture with configured settings.

---

## Best Practices

### 1. Always Enable SDK

Even with flirpy, enable SDK for full control:
```bash
python inspection_main.py --enable-boson-sdk
```

### 2. Do FFC Before Important Captures

Flat field correction improves image quality:
1. Cover lens with uniform temperature surface
2. Click "Trigger FFC" in Boson SDK panel
3. Wait for FFC to complete (~2 seconds)
4. Resume normal operation

### 3. Monitor FPA Temperature

High FPA temperature can affect accuracy:
- Check "FPA Temperature" in Boson SDK panel
- Normal range: 20-40°C
- If >45°C, consider cooling/airflow

### 4. Use Correct AGC Mode for Your Camera

**Non-Radiometric Boson** (60Hz):
- Use "LINEAR" or "AUTO" AGC mode
- Best visual quality with AGC

**Radiometric Boson** (9Hz):
- Use "LINEAR" for T-Linear output
- flirpy gets true radiometric Y16 regardless of AGC

---

## Technical Details

### Why Both Work Together

**Boson USB Interfaces**:
```
USB Device (VID:09CB, PID:4007)
├── Interface 0: UVC Video Class (0x0E)
│   └── Used by: flirpy, OpenCV
│   └── Provides: Video frames (Y16, I420)
│
└── Interface 1: CDC Serial Class (0x02)
    └── Used by: BosonSDK (COM port)
    └── Provides: Commands, telemetry
```

**These are independent!**
- flirpy → UVC → Video frames
- SDK → COM → Camera control

### Verification Test

To verify both work simultaneously:
```bash
python test_flirpy_sdk_simultaneous.py
```

This will:
1. Open SDK (COM port)
2. Open flirpy (UVC video)
3. Capture frames while sending SDK commands
4. Verify both work together

---

## FAQ

### Q: Can I change AGC mode while capturing?

**A:** Yes! Use the Boson SDK panel while flirpy is capturing.
- Changes apply immediately
- No need to restart capture

### Q: Does flirpy work with AGC off?

**A:** Yes! flirpy always gets 16-bit Y16 radiometric data, regardless of AGC mode. AGC only affects the 8-bit video output (not used by flirpy).

### Q: What if SDK connection fails?

**A:** flirpy still works! You just won't have SDK control.
- You can still capture 16-bit Y16 frames
- Just can't trigger FFC or change AGC remotely

### Q: Can I switch backends while running?

**A:** Yes! Use the backend selector in radiometric panel:
- OpenCV → flirpy: Switch to get 16-bit
- flirpy → OpenCV: Switch back to 8-bit AGC
- Camera restarts automatically

### Q: Does this work on both Boson cameras?

**A:**
- **Non-radiometric (60Hz)**: flirpy gets Y16 but not truly radiometric
- **Radiometric (9Hz)**: flirpy gets TRUE radiometric Y16 ✓

Both work, but only radiometric gives absolute temperatures.

---

## Summary

✅ **flirpy** provides 16-bit Y16 radiometric capture
✅ **SDK** provides camera control (FFC, AGC, telemetry)
✅ **Both work simultaneously** via different USB interfaces
✅ **Easy to use** in the application GUI

**Recommended workflow**:
1. Launch with `--enable-boson-sdk`
2. Select flirpy backend in GUI
3. Use SDK controls as needed
4. Capture 16-bit radiometric frames

---

**Status**: Ready for production use
**Backend**: flirpy + SDK (best of both worlds)
**Driver**: Default UVC (no Zadig needed)
