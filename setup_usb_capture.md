# Setting Up Direct USB Capture for FLIR Boson

This guide will help you set up direct USB capture to get TRUE 16-bit Y16 data on Windows.

## Prerequisites

### 1. Install PyUSB
```bash
pip install pyusb
```

### 2. Install libusb Backend

Download and install **libusb** (Windows):

**Option A: Using Zadig (Recommended)**
1. Download Zadig: https://zadig.akeo.ie/
2. Run Zadig as Administrator
3. Options → List All Devices
4. Find "FLIR Boson" or device with VID:09CB PID:4007
5. Select **WinUSB** driver
6. Click "Replace Driver" or "Install Driver"

**WARNING**: This will replace the UVC driver! The camera will no longer work with OpenCV/DirectShow until you reinstall the original driver.

**Option B: Using libusb-win32**
1. Download: https://sourceforge.net/projects/libusb-win32/
2. Extract and run install-filter-win.exe as Administrator
3. Install the filter for FLIR Boson device

### 3. Verify Installation

Run this test:
```python
import usb.core
import usb.util

# Find Boson
dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)

if dev is None:
    print("Boson not found! Check:")
    print("  1. Camera is connected")
    print("  2. WinUSB driver is installed (Zadig)")
    print("  3. Device shows in Device Manager")
else:
    print(f"Found Boson: {dev}")
    print(f"Manufacturer: {usb.util.get_string(dev, dev.iManufacturer)}")
    print(f"Product: {usb.util.get_string(dev, dev.iProduct)}")
```

## Important Notes

1. **Driver Swap**: Installing WinUSB will break OpenCV/DirectShow access
   - To restore: Device Manager → Update Driver → Browse → Let Windows pick
   - Or keep both: Use USB hub, one port WinUSB, one port UVC

2. **Linux Alternative**: On Linux, no driver changes needed! PyUSB works alongside V4L2

3. **Backup**: Before changing drivers, note current driver version for restoration

## Next Steps

After setup, we'll create `boson_usb_capture.py` that will:
- Detect USB endpoints
- Read bulk transfer data
- Parse UVC payload headers
- Extract 16-bit Y16 frames
- Provide numpy arrays with dtype=uint16

Ready to proceed?
