# Thermal Inspection Fusion Tool

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Jetson-blue)]()
[![Python](https://img.shields.io/badge/python-3.8+-green)]()
[![OpenCV](https://img.shields.io/badge/opencv-4.5+-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()

Professional-grade thermal imaging application combining FLIR Boson/Lepton thermal cameras with RGB imaging for comprehensive visual inspection and radiometric temperature analysis.

---

## Overview

**Thermal Inspection Fusion Tool** is a production-ready Python application designed for thermal imaging professionals, engineers, and technicians performing:

- **Circuit Board Inspection** - Component temperature monitoring, thermal runaway detection, pre/post-repair thermal profiling
- **Building & HVAC Inspection** - Thermal leaks, insulation defects, moisture detection, energy audits
- **Equipment Diagnostics** - Hot spot identification, bearing analysis, electrical panel inspection
- **Research & Development** - Thermal characterization, heat dissipation studies, material testing

Built on Qt6 with a modern dark-themed GUI, the application provides real-time thermal/RGB fusion, radiometric temperature measurement, automatic ROI detection, and comprehensive thermal analysis tools.

---

## Key Features

### 🔥 Advanced Thermal-RGB Fusion

**9 Fusion Algorithms**:
- **Alpha Blend** - Weighted overlay of thermal and RGB images
- **Detail Inject** - FLIR MSX-style grayscale detail overlay from RGB onto thermal
- **Relief Fusion** - 3D bas-relief embossed effect for enhanced depth perception
- **Edge Enhanced** - Thermal base with RGB edge overlays for structural context
- **Thermal Overlay** - Thermal colormap overlaid on RGB base with adjustable transparency
- **Side-by-Side** - Synchronized dual view for direct comparison
- **Picture-in-Picture** - Thermal inset on RGB (or vice versa)
- **Max Intensity** - Pixel-wise maximum intensity fusion
- **Feature Weighted** - Adaptive blending based on edge strength and content

**Real-time fusion controls**: Live mode switching, alpha blending (0-100%), edge color/intensity adjustment, detail strength tuning.

### 🌡️ Radiometric Temperature Measurement

**Dual Backend System**:
- **OpenCV Backend** - 8-bit thermal capture with pseudo-radiometric estimation (±5°C)
- **Flirpy Backend** - 16-bit Y16 radiometric capture with true absolute temperatures (±2°C)

**Temperature Measurement Features**:
- Spot temperature metering (click anywhere on thermal image)
- Multiple concurrent spot meters with customizable labels
- ROI-based area temperature statistics (min/max/mean/median)
- Hot/cold spot detection and tracking
- Temperature gradient analysis
- Isotherm highlighting (temperature range visualization)
- °C/°F/K unit selection
- 3-tier measurement fallback: 16-bit radiometric → 8-bit estimation → raw values

### 🎨 Multi-Palette System

**45 Thermal Color Palettes** organized by category:
- **Grayscale** (7): white_hot, black_hot, grayscale, inverted variants
- **Rainbow** (8): rainbow, rainbow_hc, jet, turbo, hsv variants
- **Iron/Fire** (6): ironbow, lava, hot, copper, fire variants
- **Arctic/Cool** (5): arctic, ice, ocean, cool, winter variants
- **Medical** (5): medical, viridis, inferno, plasma, cividis
- **Industrial** (8): metal, sepia, autumn, bone, specialized variants
- **High Contrast** (6): Enhanced versions of popular palettes

**Palette Features**:
- Global palette applied to entire thermal image
- Per-ROI palette override for multi-palette composite views
- Live palette switching with auto-contrast
- Gamma correction (0.1-3.0)
- Custom palette import support

### 🎯 Intelligent ROI Management

**Automatic Detection** (4 algorithms):
- **Temperature Threshold** - Detect hot/cold regions above/below user-defined thresholds
- **Temperature Gradient** - Identify areas with high thermal gradients (potential defects)
- **Motion-Triggered** - Create ROIs around detected motion in thermal scene
- **Edge Clustering** - Detect regions with dense edge activity

**Smart ROI Features**:
- Non-Maximum Suppression (NMS) to eliminate overlapping detections
- Containment checking to remove redundant nested boxes
- Priority system: Manual > Temperature > Gradient > Motion > Edge
- Configurable sensitivity for each detector

**Manual Creation Tools**:
- Rectangle, polygon, ellipse, circle drawing tools
- Point-and-click polygon creation
- ROI labeling and annotation
- Save/load ROI sets to JSON
- Per-ROI palette assignment
- Right-click context menu for quick actions

### 🔬 Comprehensive Thermal Analysis

**Real-Time Analysis**:
- **Hot/Cold Spot Detection** - Automatic identification of temperature extremes
- **Temperature Trends** - Track temperature changes over time with rate-of-change prediction
- **Anomaly Detection** - Detect rapid changes, gradient anomalies, statistical outliers
- **Temperature Gradients** - Sobel-based gradient magnitude and direction
- **Histogram Analysis** - Temperature distribution visualization

**Per-ROI Statistics**:
- Min/max/mean/median/std dev temperatures
- Temperature range and gradient strength
- ROI area and center coordinates
- Color-coded visualization

### 📹 Media Recording & Playback

**Recording Features**:
- Video recording (MP4, H.264 codec)
- Snapshot capture (PNG, JPEG)
- Configurable output directories
- Filename templates with timestamps
- Recording status overlay

**Playback Features**:
- Load recorded videos for post-analysis
- Frame-by-frame stepping
- Playback speed control
- Apply ROI and analysis to recorded media

### 📷 Universal Camera Plugin Architecture

The application features a modular, role-based camera plugin architecture with auto-discovery and generic hardware command dispatch.

#### Supported Camera Plugins:

| Plugin | Role | Interface / Protocol | Resolutions | Key Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **FLIR Boson** | Thermal | USB UVC + COM Port (921600 baud CCI) | 640×512, 320×256 | FFC, Gain Modes (High/Low/Auto), AGC Tuning, Shutter, T-Linear 16-bit Radiometry, FPA Telemetry |
| **FLIR Tau 2** | Thermal | USB Y16 DirectShow/V4L2 + COM Port (57600 baud CCI) | 640×512, 336×256, 324×256, 160×128 | 14-bit Radiometric Frame Ingestion, T-Linear Temperature Map Decoding, Shutter Control, FPA Temp |
| **FLIR Lepton** | Thermal | SPI / VoSPI / UVC Telemetry | 160×120, 80×60 | Telemetry Ingestion, Radiometric Conversion, FFC |
| **FLIR Firefly RGB** | RGB | Spinnaker SDK / GenICam USB3 Vision | 1440×1080, 1920×1080 | Microsecond Exposure, Gain (dB), White Balance R/B Ratios, Software/Hardware Trigger, Gamma |
| **Generic USB Webcam** | RGB | DirectShow (Windows) / V4L2 (Linux) | 640×480, 720p, 1080p, 2K, 4K | Dedicated Webcam Panel: Resolution Presets, Brightness, Contrast, Saturation, Sharpness, Auto/Manual Exposure, Focus |
| **GigE Vision** | RGB / Thermal | GVCP UDP Port 3956 Broadcast + GenICam / RTSP | 1920×1080, 640×512, Custom | Pure-Python GVCP Discovery across all NICs, ForceIP Subnet Rescue Tool, MTU Jumbo Frames (9000), Software Trigger |
| **Intel RealSense** | RGB + Depth | `pyrealsense2` (librealsense) over USB3 | Device-native (e.g. 1920×1080 on L515, generic across D415/D435/D435i/D455/D457/L515) | Real (not estimated) hardware depth for Parallax Compensation and the 3D Fusion tab's live point-cloud view, depth post-processing filters (spatial/temporal/hole-filling), auto visual-preset naming per product line (D400 vs L500). **L515 note:** see [Troubleshooting](#realsense-l515-not-detected) - `pip install pyrealsense2` alone will NOT work for an L515. |

#### Core Architecture Highlights:
- **`CameraPluginHost`**: Unified runtime host managing active cameras per role (`thermal`, `rgb`) with synchronized dual-threaded capture.
- **Generic Hardware Dispatch**: All GUI panels interact with hardware through generic event bus signals (`camera_command_requested` / `camera_command_result`), eliminating vendor-specific coupling.
- **Dynamic Hot-Plugging**: Background device monitoring automatically detects connected hardware and activates matching plugins.


### 🧮 Parallax Compensation

**Three depth methods, selectable per session**:
- **Intel RealSense (hardware depth)** - real per-pixel depth from a connected RealSense camera (D400 or L500/L515 series), hardware-aligned to RealSense's own color stream - the most accurate option when the hardware is present, and what also powers the 3D Fusion tab's live point-cloud/relief view
- **ML-powered monocular depth** - **DepthAnything V2** depth estimation from the RGB image alone, no depth camera required. 3 model sizes: Small (CPU-friendly), Base (balanced), Large (GPU-optimized). Lazy model loading (downloads on first use, ~100-350MB cached)
- **Simplified geometric** - fast, dependency-free heuristic fallback; manual offset adjustment (X/Y pixel shifts) and image-based auto-alignment (phase-correlation shift/scale search across sampled frame pairs)

**Shared features**: depth-based pixel displacement calculation for accurate thermal-RGB alignment, adaptive alignment for objects at varying distances, configurable camera baseline distance (separation between thermal and RGB cameras), depth map visualization for debugging.

### ⚙️ Environmental Compensation

**Material Properties**:
- Emissivity adjustment (0.1-1.0) for different materials
- Material presets (aluminum, copper, steel, plastic, glass, etc.)
- Per-ROI emissivity override

**Atmospheric Compensation**:
- Atmospheric temperature input
- Atmospheric transmission coefficient
- Distance-based correction

Emissivity, atmospheric temperature, and transmission are applied directly to displayed temperatures via `RadiometricConverter.apply_environmental_compensation()` — no SDK-side radiometry module is required.

### 🎨 Customizable UI

**Professional Qt6 Interface**:
- Modern dark theme with high contrast
- Windows XP classic theme (nostalgic option)
- Tabbed panel layout for organized controls
- Resizable video display with aspect ratio preservation
- Real-time performance monitoring (FPS, processing time)

**Panel Organization**:
- **🧬 Fusion** - 9 fusion modes, alpha/intensity/edge controls
- **🎨 Palettes** - 45 palettes, per-ROI overrides, gamma correction
- **🎯 ROI Tools** - Manual drawing, auto-detection settings, ROI list
- **📊 Analysis** - Hot/cold spots, temperature trends, anomaly detection
- **🌡️ Radiometric** - Backend selector, temperature units, spot metering
- **📷 Cameras** - Boson SDK controls, Firefly controls, camera status
- **🔬 Advanced** - Parallax compensation, environmental settings, calibration
- **⚙️ Settings** - Storage paths, performance tuning, backend configuration

### ⚡ Performance Optimization

**Multi-threaded Architecture**:
- Separate threads for thermal and RGB capture
- Parallel processing of fusion and analysis
- Non-blocking UI updates

**Hardware Acceleration**:
- OpenCV GPU acceleration (CUDA support)
- NumPy vectorized operations
- VPI acceleration on NVIDIA Jetson

**Configurable Performance**:
- Parallel processing toggle
- Worker thread count adjustment
- Frame skip options for low-power devices

---

## Quick Start

### Installation

#### Prerequisites
- Python 3.8+ (3.10 recommended)
- OpenCV 4.5+ with Python bindings
- Qt6 (PyQt6)
- FLIR Boson or Lepton thermal camera
- (Optional) FLIR Firefly RGB camera with Spinnaker SDK
- (Optional) Intel RealSense D400 or L500/L515-series camera for hardware depth

#### Install Dependencies

```bash
# Clone repository
git clone https://github.com/yourusername/Thermal-Inspection.git
cd Thermal-Inspection

# Install Python dependencies
pip install -r requirements.txt

# Install PyQt6 (if not in requirements.txt)
pip install PyQt6

# Install flirpy for 16-bit radiometric mode (optional)
pip install flirpy
# flirpy imports pkg_resources, which setuptools 81+ no longer ships -
# if you hit `ModuleNotFoundError: No module named 'pkg_resources'` on
# startup, pin setuptools below that:
pip install "setuptools<81"

# Install PySpin for FLIR Firefly support (optional)
# Download from: https://www.flir.com/products/spinnaker-sdk/

# Intel RealSense support (optional) - D400-series (D415/D435/D435i/D455/D457):
pip install pyrealsense2>=2.54.0
# Intel RealSense L515 specifically: the plain pip install above does NOT
# work - librealsense dropped L515 support upstream in pyrealsense2 v2.55+
# and PyPI no longer publishes any older wheel. Use the build-from-source
# script instead (Windows):
scripts\install_windows.bat --with-realsense-l515
# See requirements.txt's RealSense section and
# scripts/install_realsense_l515.ps1 for details.
```

### Basic Usage

```bash
# Run with default settings (auto-detect cameras)
python -m thermal_inspection

# Enable Boson SDK for radiometric mode
python -m thermal_inspection --enable-boson-sdk --boson-com-port COM7

# Specify thermal camera device ID
python -m thermal_inspection --thermal-device 2

# Use 16-bit radiometric backend (requires flirpy)
# Select "Flirpy 16-bit" in Settings > Backend Selector

# Run with specific fusion mode and palette
python -m thermal_inspection --fusion-mode detail_inject --palette ironbow

# Enable automatic ROI detection
python -m thermal_inspection --auto-roi

# Disable RGB camera (thermal-only mode)
python -m thermal_inspection --disable-rgb
```

### First Run Tips

1. **Camera Detection**: Application auto-detects thermal and RGB cameras. If detection fails, manually specify device IDs.
2. **Backend Selection**: Start with OpenCV backend (8-bit). Switch to Flirpy backend for 16-bit radiometric if you have a Boson camera.
3. **COM Port**: Check Windows Device Manager for correct COM port (usually COM6 or COM7 for Boson).
4. **Fusion Mode**: Try `detail_inject` or `edge_enhanced` for best thermal-RGB fusion quality.
5. **Palette**: `ironbow`, `rainbow_hc`, or `hot` are good starting palettes.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `f` | Trigger FFC (Flat Field Correction) |
| `t` | Show FPA temperature |
| `r` | Toggle recording |
| `s` | Capture snapshot |
| `p` | Cycle palettes |
| `m` | Cycle fusion modes |
| `q` / `Esc` | Quit application |
| `Space` | Pause/resume |
| `+` / `-` | Adjust alpha blend |
| `[` / `]` | Adjust gamma |

---

## Command-Line Options

```
usage: python -m thermal_inspection [-h] [--thermal-device THERMAL_DEVICE]
                          [--width WIDTH] [--height HEIGHT]
                          [--disable-rgb] [--enable-boson-sdk]
                          [--boson-com-port BOSON_COM_PORT]
                          [--device {cuda,cpu}] [--palette PALETTE]
                          [--fusion-mode FUSION_MODE]
                          [--fusion-alpha FUSION_ALPHA]
                          [--calibration-file CALIBRATION_FILE]
                          [--mode {realtime,playback}]
                          [--auto-roi] [--use-opencv-gui] [--headless]

optional arguments:
  -h, --help            Show this help message and exit

Camera Settings:
  --thermal-device THERMAL_DEVICE
                        Thermal camera device ID (default: auto-detect)
  --width WIDTH         Thermal camera width (default: 640)
  --height HEIGHT       Thermal camera height (default: 512)
  --disable-rgb         Disable RGB camera (thermal-only mode)

Boson SDK Settings:
  --enable-boson-sdk    Enable FLIR Boson SDK for serial control
  --boson-com-port BOSON_COM_PORT
                        Boson COM port (default: COM7)

Processing Settings:
  --device {cuda,cpu}   Processing device (default: auto-detect)
  --palette PALETTE     Default thermal palette (default: ironbow)

Fusion Settings:
  --fusion-mode FUSION_MODE
                        Fusion algorithm (default: alpha_blend)
  --fusion-alpha FUSION_ALPHA
                        Alpha for alpha_blend (default: 0.5)
  --calibration-file CALIBRATION_FILE
                        Camera calibration file (JSON)

Inspection Settings:
  --mode {realtime,playback}
                        Operating mode (default: realtime)
  --auto-roi            Enable automatic ROI detection

GUI Settings:
  --use-opencv-gui      Use simple OpenCV GUI (no Qt)
  --headless            Run without GUI (for testing)
```

---

## Hardware Requirements

### Minimum Configuration
- **CPU**: Intel Core i5 (6th gen) / AMD Ryzen 5 / ARM Cortex-A57
- **RAM**: 8 GB
- **Storage**: 500 MB for application + storage for recordings
- **Camera**: FLIR Boson/Lepton thermal camera (USB UVC)
- **OS**: Windows 10/11, Ubuntu 20.04+, NVIDIA Jetson JetPack 5.0+

### Recommended Configuration
- **CPU**: Intel Core i7 (8th gen+) / AMD Ryzen 7 / NVIDIA Jetson Orin
- **RAM**: 16 GB+
- **Storage**: SSD with 10+ GB free space
- **Camera**: FLIR Boson 640 + FLIR Firefly RGB
- **GPU**: NVIDIA GPU with CUDA 11.0+ (optional, for parallax and ML features)
- **OS**: Windows 11 / Ubuntu 22.04 / NVIDIA Jetson Orin with JetPack 6.0

### Tested Platforms
- **Windows 11** (x86-64) - Primary development platform
- **Windows 10** (x86-64) - Fully supported
- **Ubuntu 22.04 LTS** (x86-64) - Tested
- **NVIDIA Jetson Orin Nano** - Hardware-accelerated fusion and VPI support

### Tested Hardware
- **FLIR Boson 640** (radiometric -R and non-radiometric) and **FLIR Tau 2** (video-only so far)
- **Intel RealSense D455** and **L515** - both confirmed live end-to-end (color + real metric depth)
- Generic UVC webcams, GigE Vision cameras

---

## Project Structure

```
Thermal-Inspection/
├── README.md, CHANGELOG.md, requirements.txt
├── launch.bat
├── scripts/                         # install/repair/quick-launch scripts
│
├── thermal_inspection/              # Main application package
│   ├── app.py                       # ThermalInspectionApp coordinator
│   ├── cli.py                       # Argument parsing
│   ├── __main__.py                  # `python -m thermal_inspection` entry point
│   │
│   ├── cameras/
│   │   ├── plugin/                  # Plugin base framework (CameraPlugin, CameraPluginHost, CameraPluginRegistry)
│   │   └── plugins/                 # Vendor plugin implementations
│   │       ├── boson/, tau2/, lepton/   # Thermal cameras
│   │       └── firefly/, uvc/, gige/    # RGB / network cameras
│   │
│   ├── core/                        # Controllers & managers
│   │   ├── fusion_controller.py, roi_controller.py, radiometric_controller.py
│   │   ├── media_manager.py, calibration_manager.py
│   │   ├── threshold_manager.py, isotherm_manager.py
│   │   └── event_bus.py             # GUI <-> backend signal broker
│   │
│   ├── processing/                  # Fusion, palettes, ROI/thermal analysis, gradients
│   ├── sdk/                         # FLIR Boson/Lepton/Tau2 serial protocols, GigE GVCP
│   ├── gui/
│   │   ├── main_window.py           # InspectionAppWindow
│   │   ├── panels/                  # Fusion, radiometric, ROI, isotherm, parallax, etc.
│   │   ├── camera_control/          # Per-plugin control panels
│   │   └── widgets/, themes/
│   └── utils/                       # Config, presets, media recording, exceptions
│
└── tests/unit/                      # pytest suite
```

---

## Use Cases

### 1. Circuit Board Inspection
**Problem**: Identify overheating components on PCBs during operation.

**Solution**:
1. Mount Boson thermal camera above PCB workbench
2. Enable 16-bit radiometric mode for accurate temperature measurements
3. Use `temperature_threshold` auto-ROI to detect components above 80°C
4. Apply `ironbow` or `hot` palette for clear hot spot visualization
5. Use spot metering to measure specific IC temperatures
6. Record thermal video during power-up sequence
7. Export ROI temperature statistics for documentation

**Typical Settings**:
- Fusion: `thermal_overlay` (thermal on RGB PCB image)
- Palette: `ironbow` or `lava`
- Auto-ROI: Temperature threshold (75°C+)
- Backend: Flirpy 16-bit radiometric

### 2. Building Energy Audit
**Problem**: Find thermal leaks and insulation defects in residential/commercial buildings.

**Solution**:
1. Walk through building with handheld Boson + RGB camera
2. Use `side_by_side` or `picture_in_picture` fusion for documentation
3. Apply `arctic` or `rainbow` palette for intuitive cold spot identification
4. Mark ROIs on windows, doors, walls, and attic access
5. Export annotated images for audit report
6. Compare before/after insulation improvements

**Typical Settings**:
- Fusion: `side_by_side` or `alpha_blend`
- Palette: `arctic` (blue = cold leaks) or `rainbow_hc`
- Manual ROIs: Rectangle tool for windows/doors
- Backend: OpenCV 8-bit (sufficient for relative temperature)

### 3. Electrical Panel Inspection
**Problem**: Detect loose connections and failing breakers before they cause fires.

**Solution**:
1. Capture thermal image of electrical panel under load
2. Use `temperature_gradient` auto-ROI to detect high thermal gradients (loose connections)
3. Enable hot spot detection to automatically flag dangerous components
4. Measure spot temperatures of each breaker
5. Apply `hot` or `medical` palette for clear visualization
6. Save snapshot and ROI data for maintenance records

**Typical Settings**:
- Fusion: `thermal_overlay`
- Palette: `hot` or `medical`
- Auto-ROI: Gradient detection
- Hot spot threshold: 60°C+

### 4. HVAC System Diagnostics
**Problem**: Identify airflow issues, duct leaks, and inefficient components.

**Solution**:
1. Scan HVAC ducts, vents, and equipment with thermal camera
2. Use `edge_enhanced` fusion to see duct structure with thermal overlay
3. Apply `arctic` palette to visualize cool air distribution
4. Mark ROIs on supply/return vents and measure temperature differentials
5. Record video of system startup thermal transient
6. Generate temperature trend graphs for performance analysis

**Typical Settings**:
- Fusion: `edge_enhanced` or `detail_inject`
- Palette: `arctic` (cooling) or `hot` (heating)
- Temperature trends enabled
- Backend: Either (8-bit or 16-bit)

---

## Advanced Features

### Parallax Compensation

When thermal and RGB cameras are physically separated, parallax errors cause misalignment. This tool provides ML-powered depth estimation to correct for parallax.

**Enable Parallax Compensation**:
1. Go to Advanced > Parallax Compensation
2. Enable "Use Parallax Compensation"
3. Select model size (Small for CPU, Large for GPU)
4. Set camera baseline (distance between thermal and RGB lenses in cm)
5. Model downloads automatically on first use (~100-350MB)

**Models**:
- **Small** - Fastest, CPU-friendly, good accuracy
- **Base** - Balanced speed and accuracy
- **Large** - Best accuracy, requires GPU

### Custom Palettes

Create custom color palettes for specialized applications.

**Format**: 256-row x 3-column NumPy array (BGR values 0-255)

```python
import numpy as np

# Create custom palette (example: red-to-yellow gradient)
custom_palette = np.zeros((256, 3), dtype=np.uint8)
custom_palette[:, 0] = 0  # Blue channel
custom_palette[:, 1] = np.linspace(0, 255, 256)  # Green channel
custom_palette[:, 2] = 255  # Red channel (constant)

# Save palette
np.save('custom_palette.npy', custom_palette)
```

Load in application: Palettes > Import Palette > Select `custom_palette.npy`

### Preset Management

Save and load complete application states (fusion mode, palette, ROIs, settings).

**Save Preset**:
1. Configure application (fusion mode, palette, ROIs, camera settings)
2. Settings > Save Preset
3. Enter preset name (e.g., "PCB_Inspection")

**Load Preset**:
1. Settings > Load Preset
2. Select preset from dropdown
3. All settings restored instantly

### ROI Export/Import

Export ROI sets for reuse across sessions.

**Export**:
1. Create ROIs (manual or auto-detection)
2. ROI Tools > Export ROIs
3. Save as JSON file

**Import**:
1. ROI Tools > Import ROIs
2. Select JSON file
3. ROIs restored with labels and palettes

### Temperature Data Export

Export temperature measurements for external analysis.

**Export Formats**:
- CSV - Spot meter temperatures, ROI statistics
- JSON - Complete thermal data with timestamps
- PNG - Annotated thermal images with overlays

**Export Data**:
1. Analysis > Export Data
2. Select format and destination
3. Data saved with timestamp

---

## Troubleshooting

### Camera Not Detected

**Problem**: Application shows "Camera not found" or uses placeholder frames.

**Solutions**:
1. Check USB connections (try different USB ports)
2. Verify camera is recognized in Windows Device Manager / Linux `lsusb`
3. Close other applications that might be using the camera
4. Manually specify device ID: `--thermal-device 0` (increment to try 1, 2, 3, etc.)
5. For Boson: Check if UVC video interface is enabled (use Boson SDK test tool)
6. For Firefly: Install Spinnaker SDK and verify with SpinView application

### Boson SDK Not Found

**Problem**: Startup log shows `Boson SDK not found` and the camera runs in video-only mode (image works, but FFC/AGC/palette-LUT/radiometric SDK control don't).

**Solution**: This only applies to a **non-radiometric** Boson (no `-R` in the part number, 8-bit AGC path). A **radiometric (-R)** Boson doesn't need the vendor SDK at all for control - `thermal_inspection/sdk/boson_flirpy_ext.py` implements FFC, gain mode, palette, T-Linear mode, and environmental compensation natively over the same connection flirpy already uses for video. For a non-radiometric unit, the vendor SDK is FLIR's proprietary software and isn't bundled with this repo — download it from FLIR and extract it into `boson_sdk/` at the project root. See [`boson_sdk/README.md`](boson_sdk/README.md) for exactly where to get it and what the extracted folder should look like.

### Boson SDK Connection Failed

**Problem**: SDK connection fails with error 255 or "Cannot connect to camera" (the SDK files ARE present, but the camera itself won't connect).

If this is a **radiometric (-R)** Boson: as of v3.7.0 this shouldn't happen anymore - the control panel now shares the same connection flirpy uses for video instead of opening a second, competing one (which is what error 255 meant: the port was already open elsewhere). If you still see it, that's a regression, not a known limitation.

**Solutions** (non-radiometric Boson, or anything else still hitting this):
1. **Check COM Port**: Open Device Manager > Ports, find "FLIR Control" device. The app auto-detects this port at startup — `--boson-com-port` only needs to be passed to override it.
2. Verify no other application is using the COM port (close FLIR tools)
3. Try unplugging/replugging USB cable
4. Check baud rate (default 921600 works for most Bosons)

### 16-bit Radiometric Mode Not Working

**Problem**: Switching to Flirpy backend shows "Backend not available" or stays in 8-bit mode.

**Solutions**:
1. Install flirpy: `pip install flirpy`
2. Verify Boson camera is connected (not Lepton or other thermal cameras)
3. Check SDK connection (T-Linear mode requires SDK)
4. Specify COM port if not auto-detected
5. Check logs for detailed error messages
6. Fallback: Use OpenCV backend with 8-bit temperature estimation

### Fusion Quality Poor

**Problem**: Thermal and RGB images don't align properly or fusion looks blurry.

**Solutions**:
1. **Parallax Misalignment**: Enable parallax compensation (Advanced > Parallax)
2. **Resolution Mismatch**: Check if RGB camera resolution matches thermal (640x512 recommended)
3. **Calibration**: Run camera calibration and save calibration file
4. **Fusion Mode**: Try different modes (`detail_inject`, `edge_enhanced` are most forgiving)
5. **Manual Offset**: Use parallax panel geometric mode to manually adjust X/Y offset

### Low Frame Rate

**Problem**: Application runs slow (< 15 FPS) or UI is unresponsive.

**Solutions**:
1. **Disable Auto-ROI**: Auto-detection is CPU-intensive
2. **Reduce Workers**: Settings > Performance > Set worker count to 2
3. **Disable Parallax**: DepthAnything model is GPU-intensive
4. **Lower Resolution**: Use 320x256 Boson instead of 640x512
5. **GPU Acceleration**: Ensure CUDA is installed and detected (`--device cuda`)
6. **Close Other Apps**: Free up system resources

### Intel RealSense L515 Not Detected
<a id="realsense-l515-not-detected"></a>

**Problem**: An L515 shows up fine in Windows Device Manager and Intel's own RealSense Viewer, but the app never lists it (or `pyrealsense2.context().query_devices()` returns an empty list in a Python shell).

**Cause**: librealsense/pyrealsense2 permanently dropped L515 (L500-series) enumeration on Windows starting at v2.55.0 - this is an upstream EOL removal by Intel/realsenseai, not a bug that will be fixed in a later release, and PyPI does not publish any pre-2.55 wheel for any Python version. A plain `pip install pyrealsense2` (any version you ask for) simply cannot see an L515, ever.

**Solution**: build pyrealsense2 from source at the last L515-supporting release (v2.54.2) for your exact Python interpreter. Automated via:
```bash
scripts\install_windows.bat --with-realsense-l515
```
This needs git, CMake, and a Visual Studio install with the C++ ATL component (`atlcomcli.h`) - the script checks for all three and tells you what's missing. Takes 10-30+ minutes (it's compiling librealsense's full C++ core). D400-series cameras are unaffected by any of this - use the normal `pip install pyrealsense2` for those.

### Temperature Readings Incorrect

**Problem**: Temperature measurements don't match handheld thermal camera or expected values.

**Solutions**:
1. **Check Backend**: Use Flirpy 16-bit for accurate measurements (±2°C)
2. **Emissivity**: Adjust material emissivity (Advanced > Environmental > Emissivity)
3. **Calibration**: Run radiometric calibration with reference temperatures
4. **T-Linear Mode**: Verify SDK is connected and T-Linear mode is enabled (Boson SDK panel)
5. **FFC**: Trigger FFC to recalibrate camera (press `F` or Boson SDK > Trigger FFC)
6. **Reflected Temperature**: Account for atmospheric/reflected temperature in environmental settings

---

## Documentation

- **README.md** - Project overview, quick start, features (this file)
- **CHANGELOG.md** - Version history, major changes, implementation details

---

## Development

### Architecture

**Multi-threaded Camera Capture**:
- Separate threads for thermal and RGB cameras prevent blocking
- Frame queues for asynchronous processing
- Timeout protection prevents initialization hangs

**Processing Pipeline**:
1. Capture thermal and RGB frames (parallel threads)
2. Apply thermal processing (palette, normalization, edge detection)
3. Align RGB to thermal (homography transform or parallax compensation)
4. Fuse thermal and RGB (selected fusion algorithm)
5. Run thermal analysis (ROI detection, temperature measurement, anomaly detection)
6. Update GUI (non-blocking UI thread)
7. Record to disk if enabled

**Plugin Architecture**:
- `CameraPluginRegistry` singleton for registering and discovering hardware plugins
- `CameraPluginHost` managing runtime lifecycle and unified capture
- `CameraRole.THERMAL` and `CameraRole.RGB` role abstractions
- Direct hardware plugins: `FLIR Boson`, `FLIR Tau 2`, `FLIR Lepton`, `FLIR Firefly RGB`, `Generic UVC Webcam`, `GigE Vision`
- Dynamic hot-plug detection and runtime plugin switching without restart

### Adding Custom Fusion Algorithms

1. Edit `fusion_processor.py`
2. Add new method `_my_fusion(self, thermal, rgb)`
3. Register in `set_mode()` valid_modes list
4. Add to fusion dropdown in `fusion_panel.py`

Example:
```python
def _my_fusion(self, thermal: np.ndarray, rgb: np.ndarray) -> np.ndarray:
    """My custom fusion algorithm."""
    # Ensure both are 3-channel
    if len(thermal.shape) == 2:
        thermal = cv2.cvtColor(thermal, cv2.COLOR_GRAY2BGR)
    if len(rgb.shape) == 2:
        rgb = cv2.cvtColor(rgb, cv2.COLOR_GRAY2BGR)

    # Your fusion logic here
    result = thermal * 0.7 + rgb * 0.3

    return result.astype(np.uint8)
```

### Adding Custom Palettes

1. Create 256x3 NumPy array (BGR values)
2. Save as `.npy` file in project root
3. Import via Palettes > Import Palette
4. Or add to `palette_manager.py` for permanent inclusion

### Running Tests

```bash
# Run full test suite (600+ tests)
pytest tests/ -v

# Run camera plugin and driver tests
pytest tests/unit/test_camera_plugin_system.py tests/unit/test_uvc_and_gige_plugins.py -v

# Run core manager and device scanner tests
pytest tests/unit/test_core_managers.py tests/unit/test_device_scanner.py -v
```

### Linting

```bash
# Lint the package (config in pyproject.toml)
ruff check thermal_inspection/ tests/
```

---

## Contributing

Contributions welcome! Please open an issue or pull request on GitHub.

**Areas for Contribution**:
- Additional fusion algorithms
- Custom thermal palettes
- Camera backend support (Seek Thermal, etc.)
- Performance optimizations
- Documentation improvements
- Bug reports and fixes

---

## License

MIT License - See LICENSE file for details.

---

## Acknowledgments

- **FLIR Systems** - Boson/Lepton SDK, thermal camera hardware
- **OpenCV** - Image processing and computer vision
- **flirpy** - Python interface for FLIR cameras
- **DepthAnything V2** - Monocular depth estimation for parallax compensation
- **Qt / PyQt6** - Professional cross-platform GUI framework
- **NVIDIA** - VPI acceleration on Jetson platforms

---

## Version

**Version**: 3.7.0
**Status**: Production-ready with full radiometric support, runtime mode switching, ML + hardware depth estimation, universal camera plugin architecture
**Last Updated**: 2026-09-18
**Tested**: Windows 11, FLIR Boson 640 (radiometric + non-radiometric), Intel RealSense D455 & L515, FLIR Firefly RGB

---

## Contact & Support

- **Issues**: Report bugs and feature requests on GitHub Issues
- **Documentation**: See README.md and CHANGELOG.md
- **Community**: Discussions on GitHub Discussions

---

**Built for thermal imaging professionals. Engineered for reliability.**
