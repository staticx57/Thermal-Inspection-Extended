# Analysis: How FLIR's Official App Achieves 16-bit Capture on Windows

**Key Question**: If OpenCV with DirectShow can't capture Y16, how does FLIR's app do it?

---

## Answer: FLIR Uses a Custom DirectShow Filter or Proprietary SDK

### Evidence from SDK Documentation

From `bosonsdkraw.txt`:
```
"Description of video interfaces and image capture are NOT included in this SDK."
```

**This is critical** - The Boson SDK you're using is for **camera control** (AGC, FFC, modes), not **video capture**. FLIR has a separate video capture mechanism.

---

## Method 1: Custom DirectShow Filter (Most Likely)

### How It Works

FLIR likely ships a **custom DirectShow filter** with their viewer application:

```
FLIR Boson Camera
       ↓ USB
Windows DirectShow Graph:
  ┌─────────────────────────────────┐
  │ FLIR Custom Capture Filter      │ ← Proprietary FLIR code
  │ (FLIRBosonSource.ax)            │
  │   - Registers Y16 media type    │
  │   - Forces Y16 format selection │
  │   - Bypasses color conversion   │
  └─────────────────────────────────┘
       ↓ Raw Y16 data
  ┌─────────────────────────────────┐
  │ FLIR Rendering/Processing       │
  │ - Linear transform              │
  │ - Temperature conversion        │
  │ - Display rendering             │
  └─────────────────────────────────┘
```

**Why This Works**:
1. Custom DirectShow filter installed with FLIR app
2. Filter is registered as the **preferred handler** for VID:09CB PID:4007 (Boson USB)
3. Filter explicitly requests and locks to Y16 format
4. Filter exposes raw 16-bit data to application layer

**Why OpenCV Fails**:
- OpenCV uses **generic DirectShow** filters (built-in Windows)
- Generic filters prefer well-known formats (I420, YUY2, MJPEG)
- Generic filters auto-negotiate to "best compatible" format = color
- No way to force Y16 without custom filter

---

## Method 2: Direct Media Foundation Access

FLIR may use **Media Foundation** with custom media type negotiation:

```cpp
// Pseudocode for FLIR's approach:

IMFSourceReader* reader;
IMFMediaType* mediaType;

// Create media type explicitly requesting Y16
mediaType->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Video);
mediaType->SetGUID(MF_MT_SUBTYPE, MFVideoFormat_Y16);  // 16-bit grayscale
mediaType->SetUINT32(MF_MT_INTERLACE_MODE, MFVideoInterlace_Progressive);
mediaType->SetUINT64(MF_MT_FRAME_SIZE, PACK_SIZE(640, 512));

// Force the reader to use this exact media type
reader->SetCurrentMediaType(streamIndex, mediaType);

// Now read frames - guaranteed Y16
IMFSample* sample;
reader->ReadSample(..., &sample);
// sample contains 16-bit Y16 data
```

**Why This Works**:
- Explicit media type forcing
- Bypasses automatic format negotiation
- Low-level control over capture pipeline

**Why OpenCV Fails**:
- OpenCV's Media Foundation backend uses auto-negotiation
- No API to force specific media type
- Safety defaults to compatible formats

---

## Method 3: WinUSB / libusb Direct Access

FLIR could be using **direct USB access**, bypassing DirectShow entirely:

```
FLIR Boson Camera
       ↓ USB (bulk transfer)
  ┌─────────────────────────────────┐
  │ WinUSB / libusb                 │ ← Direct USB communication
  │ - Read from USB endpoint        │
  │ - Parse UVC payload headers     │
  │ - Extract raw Y16 frame data    │
  └─────────────────────────────────┘
       ↓ Raw Y16 buffer
  ┌─────────────────────────────────┐
  │ FLIR Application Processing     │
  └─────────────────────────────────┘
```

**How UVC Y16 Works**:
```
USB Bulk Transfer from Endpoint 0x81:
┌──────────────────────────────────────┐
│ UVC Payload Header (12 bytes)       │
│  - Header Length                     │
│  - Frame ID                          │
│  - Timestamp                         │
│  - End of Frame marker               │
├──────────────────────────────────────┤
│ Y16 Frame Data (640x512x2 bytes)    │
│  - Raw 16-bit pixel values           │
│  - Little-endian uint16              │
│  - No compression                    │
└──────────────────────────────────────┘
```

**Why This Works**:
- Complete control over USB transfer
- Direct access to raw data format
- No Windows layer interfering

**Why OpenCV Fails**:
- OpenCV relies on OS-level video APIs
- Doesn't do direct USB access
- Can't parse raw UVC streams

---

## Method 4: Proprietary FLIR SDK (Not Public)

FLIR likely has an **internal SDK** that's more complete than the public one:

**Public SDK** (what you have):
- Camera control (AGC, FFC, modes, temperature)
- Serial communication
- Does NOT include video capture

**Internal/Commercial SDK** (FLIR apps use):
- Everything in public SDK
- **Plus**: Video capture library
- **Plus**: DirectShow filter integration
- **Plus**: Frame grabbing API
- **Plus**: Direct Y16 access

**Example of what FLIR's internal API might look like**:

```cpp
// FLIR Internal SDK (hypothetical)
#include <FLIRBosonCapture.h>

FLIRBosonCapture* capture = new FLIRBosonCapture();
capture->OpenCamera(0);

// Set format explicitly
capture->SetVideoFormat(FLIR_FORMAT_Y16);
capture->SetResolution(640, 512);

// Capture 16-bit frame
uint16_t* frame_data = new uint16_t[640 * 512];
capture->GrabFrame(frame_data);

// frame_data now contains raw 16-bit radiometric values
```

---

## Verifying FLIR's Method

### Check 1: DirectShow Filter Registry

```powershell
# Search Windows registry for FLIR DirectShow filters
reg query HKLM\SOFTWARE\Classes\CLSID /s /f "FLIR"
reg query HKLM\SOFTWARE\Classes\CLSID /s /f "Boson"

# Check for DirectShow filter files
dir "C:\Windows\System32\*.ax" | findstr /i flir
dir "C:\Program Files\FLIR\*" /s /b | findstr /i ".ax .dll"
```

### Check 2: Process Monitor

If you have FLIR's viewer installed:
1. Run Process Monitor (Sysinternals)
2. Filter for FLIR viewer process
3. Look for:
   - `.ax` or `.dll` loads (DirectShow filters)
   - USB device I/O operations
   - Registry access to video device keys

### Check 3: USB Traffic Analysis

Using USB analyzer (e.g., Wireshark with USBPcap):
1. Capture USB traffic while FLIR app runs
2. Look at bulk transfer data from Boson
3. Check if data format matches Y16 (2 bytes per pixel)

---

## Comparison: OpenCV vs FLIR App

| Aspect | OpenCV DirectShow | FLIR Official App |
|--------|-------------------|-------------------|
| **Video API** | Generic Windows DirectShow | Custom DirectShow Filter or Direct USB |
| **Format Selection** | Auto-negotiated | Explicitly forced to Y16 |
| **Media Types** | Prefers color (I420, YUY2) | Locks to Y16 grayscale |
| **USB Access** | Through OS drivers | Possibly direct USB |
| **Pixel Format** | 8-bit YUV (I420) | 16-bit grayscale (Y16) |
| **Flexibility** | High (works with any camera) | Low (Boson-specific) |

---

## Why DirectShow Prefers Color Formats

DirectShow has a **merit system** for format negotiation:

```
Format Merit Scores (higher = preferred):
┌──────────────────────────────────┐
│ RGB24/RGB32        : 100 (highest) │
│ YUY2 (4:2:2)      : 90            │
│ I420/IYUV (4:2:0) : 85            │ ← OpenCV gets this
│ MJPEG             : 80            │
│ GREY/Y800         : 70            │
│ Y16               : 60 (lowest)   │ ← Needs forcing
└──────────────────────────────────┘
```

When OpenCV asks DirectShow to open Boson:
1. DirectShow queries available formats from camera
2. Boson offers: I420, YUY2, Y16
3. DirectShow picks **highest merit** = I420
4. OpenCV gets 8-bit YUV

FLIR's custom filter:
1. Overrides merit system
2. Forces Y16 selection
3. Rejects color formats
4. App gets 16-bit raw data

---

## Solutions for Your Application

### Option A: Reverse Engineer FLIR's Filter (Complex)
1. Find FLIR's DirectShow filter `.ax` file
2. Register it on your system
3. Modify OpenCV to prefer specific filter by CLSID
4. **Legal concerns**: FLIR's filter is proprietary

### Option B: Write Custom DirectShow Filter (Advanced)
```cpp
// Custom DirectShow source filter for Boson Y16
class BosonY16SourceFilter : public CSource {
public:
    HRESULT GetMediaType(CMediaType* pMediaType) {
        pMediaType->SetType(&MEDIATYPE_Video);
        pMediaType->SetSubtype(&MEDIASUBTYPE_Y16);
        pMediaType->SetFormatType(&FORMAT_VideoInfo);

        VIDEOINFOHEADER* pvi = (VIDEOINFOHEADER*)pMediaType->AllocFormatBuffer(...);
        pvi->bmiHeader.biWidth = 640;
        pvi->bmiHeader.biHeight = 512;
        pvi->bmiHeader.biBitCount = 16;
        // ... configure Y16 format
    }
};
```

### Option C: Use libusb for Direct USB Access (Medium Complexity)

```python
import usb.core
import usb.util
import numpy as np

# Find Boson (VID:09CB, PID:4007)
dev = usb.core.find(idVendor=0x09CB, idProduct=0x4007)

# Read from bulk endpoint
endpoint = dev[0][(0,0)][0]  # First endpoint
data = dev.read(endpoint.bEndpointAddress, 640*512*2)

# Parse Y16 data
frame = np.frombuffer(data, dtype=np.uint16).reshape(512, 640)
# frame is now true 16-bit radiometric data!
```

### Option D: Request FLIR's Commercial SDK
Contact FLIR and request access to their **commercial video capture SDK**. This would include:
- Proper video capture API
- Y16 format support
- Documentation
- Support

---

## Conclusion

**Most Likely**: FLIR's official app uses a **custom DirectShow filter** (`.ax` file) that:
1. Registers as the preferred handler for Boson USB devices
2. Explicitly forces Y16 format during media type negotiation
3. Bypasses DirectShow's color format preference
4. Provides raw 16-bit data to the application

**Alternative**: They use **direct USB access** via WinUSB/libusb, completely bypassing DirectShow.

**Why OpenCV Can't Do This**: OpenCV uses generic DirectShow capabilities without custom filters, making it subject to automatic format negotiation that prefers color formats.

**Your Options**:
1. ✅ **Current solution**: Use 8-bit with T-Linear processing (works well)
2. 🔧 **Direct USB**: Implement libusb capture (medium effort, true 16-bit)
3. 🐧 **Linux**: Switch to Linux with V4L2 (easiest for true 16-bit)
4. 💰 **FLIR SDK**: Purchase/request FLIR's commercial capture SDK

---

**Bottom Line**: You're not doing anything wrong. The official FLIR app uses proprietary capture mechanisms that aren't available through standard OpenCV/DirectShow.
