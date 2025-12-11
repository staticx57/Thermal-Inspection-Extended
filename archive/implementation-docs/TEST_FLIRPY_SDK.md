# Flirpy SDK Control - Test Instructions

## Overview

This directory contains a **proof-of-concept test script** to validate whether Boson SDK commands can be sent through flirpy's serial connection without breaking video capture.

## Test Script

**File:** `test_flirpy_sdk_concept.py`

**What it tests:**
1. ✅ Basic flirpy connection and video capture
2. ✅ FFC trigger command (native flirpy method)
3. 🔍 Serial port access inspection
4. 📊 Camera info queries (read-only)

**Safety:** This script only performs safe, read-only operations and FFC triggers. No destructive commands.

## How to Run

### Prerequisites
- FLIR Boson camera connected via USB
- `flirpy` library installed (`pip install flirpy`)
- Python 3.7+

### Execution

```bash
cd c:\Users\stati\Desktop\Projects\Thermal-Inspection
python test_flirpy_sdk_concept.py
```

**You will be prompted for:**
- COM port (default: COM7)

### Expected Output

The script will run 4 tests and report:
- ✓ PASS or ✗ FAIL for each test
- Detailed logs of serial port capabilities
- Recommendations for next steps

### Troubleshooting

**"Cannot find camera"**
→ Check COM port number in Device Manager

**"Permission denied"**
→ Close any other applications using the camera

**"flirpy not found"**
→ Run: `pip install flirpy`

## Next Steps

### If all tests PASS:
1. Implement `flirpy_sdk_bridge.py` based on discovered serial access methods
2. Run advanced tests with actual SDK command packets
3. Integrate into `FlirpyThermalBackend`

### If serial access test FAILS:
1. Consider alternative: Mutex-based COM port sharing between camera capture and SDK
2. Or investigate forking flirpy to add native SDK command support

## Related Files

- **Implementation Plan:** `C:\Users\stati\.gemini\antigravity\brain\...\implementation_plan.md`
- **Task Breakdown:** `C:\Users\stati\.gemini\antigravity\brain\...\task.md`
- **Backend File:** `flirpy_thermal_backend.py`
