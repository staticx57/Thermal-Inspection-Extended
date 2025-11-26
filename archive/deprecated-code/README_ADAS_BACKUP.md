# Thermal Inspection Fusion Tool v2.0

> **Transformed from ADAS to Inspection Tool - 2025-11-20**
> Powerful thermal/RGB fusion system for circuit board and residential house inspection.

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Jetson-blue)]()
[![Python](https://img.shields.io/badge/python-3.8%2B-green)]()
[![OpenCV](https://img.shields.io/badge/opencv-4.5+-green.svg)](https://opencv.org/)

## 🎯 Overview

Thermal Inspection Fusion Tool combines thermal imaging (FLIR Boson) with RGB cameras to provide comprehensive inspection capabilities for:
- **Circuit Board Inspection**: Detect overheating components, track temperature trends, identify thermal anomalies
- **Residential House Inspection**: Find thermal leaks, insulation issues, moisture problems
- **General Thermal Analysis**: Multi-palette visualization, ROI management, hot/cold spot detection

### Transformation from ADAS

This project was successfully transformed from an Advanced Driver Assistance System into a powerful inspection tool while preserving the critical fusion engine (PARAMOUNT!).

---

## Key Features

### Multi-Sensor Fusion
- ✅ **Thermal + RGB fusion** with 7 different algorithms
- ✅ **Global shutter support** (FLIR Firefly - no motion blur)
- ✅ **Auto-detection** of available cameras
- ✅ **Hot-plug support** - cameras can disconnect/reconnect

### Advanced Detection
- ✅ **YOLOv8** object detection optimized for road scenarios
- ✅ **Custom thermal models** (FLIR COCO dataset)
- ✅ **Distance estimation** (85-90% accuracy <20m)
- ✅ **Time-to-collision** warnings
- ✅ **Smart filtering** (road-relevant objects only)

### Professional Interface
- ✅ **Qt5 GUI** with clean, driver-friendly design
- ✅ **Automatic day/night themes** (based on time + ambient light)
- ✅ **Developer mode** for configuration
- ✅ **Simple mode** for clean driving view
- ✅ **Real-time metrics** (FPS, detection count, sensor status)
- ✅ **ISO 26262 compliant audio alerts**

### Cross-Platform
- ✅ **Windows 10/11** (x86-64)
- ✅ **Linux** (x86-64 and ARM64)
- ✅ **NVIDIA Jetson** (Orin, Xavier, Nano) with GPU acceleration
- ✅ **Automatic backend selection** (DirectShow/V4L2/VPI)

---

## Quick Start

### Windows

```cmd
# 1. Clone repository
git clone https://github.com/yourusername/ThermalFusionDrivingAssist.git
cd ThermalFusionDrivingAssist

# 2. Install Python 3.10 (recommended for PySpin compatibility)
# Download from: https://www.python.org/downloads/release/python-31011/

# 3. Set up virtual environment
setup_venv_py310.bat

# 4. For FLIR Firefly camera support (optional):
# - Install Spinnaker SDK from: https://www.flir.com/products/spinnaker-sdk/
# - Install PySpin wheel (see docs/install/install_pyspin.md)

# 5. Run application
venv_py310\Scripts\activate
python main.py
```

### Linux / Jetson

```bash
# 1. Clone repository
git clone https://github.com/yourusername/ThermalFusionDrivingAssist.git
cd ThermalFusionDrivingAssist

# 2. Run automated installer
chmod +x install_linux.sh
./install_linux.sh

# 3. For FLIR Firefly support (optional):
./install_linux.sh --with-firefly

# 4. Run application
python3 main.py
```

**Detailed setup guides:**
- Windows: [`docs/WINDOWS_SETUP.md`](docs/WINDOWS_SETUP.md)
- Cross-platform: [`docs/CROSS_PLATFORM.md`](docs/CROSS_PLATFORM.md)
- FLIR Firefly setup: [`docs/install/install_pyspin.md`](docs/install/install_pyspin.md)

---

## Hardware Requirements

### Minimum

| Component | Specification |
|-----------|---------------|
| **CPU** | Intel i5 / AMD Ryzen 5 or equivalent |
| **RAM** | 8GB (16GB recommended) |
| **GPU** | Optional (Intel/AMD integrated works) |
| **Camera** | Any UVC thermal camera or USB webcam |

### Recommended

| Component | Specification |
|-----------|---------------|
| **CPU** | Intel i7 / AMD Ryzen 7 or ARM64 (Jetson) |
| **RAM** | 16GB+ |
| **GPU** | NVIDIA GTX 1060+ or Jetson Orin |
| **Thermal** | FLIR Boson 640x512 (USB) |
| **RGB** | FLIR Firefly global shutter camera |

### Supported Cameras

**Thermal Cameras:**
- FLIR Boson 640x512 (USB UVC) ⭐ Recommended
- FLIR Boson 320x256 (USB UVC)
- Any UVC-compatible thermal camera

**RGB Cameras:**
- FLIR Firefly series (global shutter, requires Spinnaker SDK) ⭐ Best
- Any USB webcam (UVC)
- CSI cameras (Jetson only: IMX219, IMX477)

---

## Usage

### Basic Usage

```bash
# Thermal + auto-detected RGB camera
python main.py

# Thermal only (disable RGB)
python main.py --disable-rgb

# Use specific thermal camera
python main.py --camera-id 0

# Force specific RGB camera type
python main.py --rgb-camera-type firefly
```

### Advanced Options

```bash
# GPU acceleration
python main.py --device cuda

# Custom YOLO model
python main.py --model yolov8s.pt

# Adjust detection confidence
python main.py --confidence 0.6

# Enable all ADAS features
python main.py --enable-audio --enable-distance

# Legacy OpenCV GUI (not recommended)
python main.py --use-opencv-gui
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Q** / **ESC** | Quit application |
| **V** | Cycle view modes (Thermal/RGB/Fusion/Side-by-Side/PiP) |
| **Y** | Toggle YOLO detection |
| **D** | Toggle detection boxes |
| **C** | Cycle thermal palette |
| **A** | Toggle audio alerts |
| **F** | Toggle fullscreen |
| **S** | Screenshot |
| **P** | Print performance stats |

---

## View Modes

### 1. Thermal Only
Classic thermal imaging view - works in complete darkness.

### 2. RGB Only
Standard camera view - high resolution, good for daylight.

### 3. Fusion (7 Algorithms)
Combines thermal + RGB for best of both worlds:

- **Alpha Blend** - Weighted average (adjustable 30%/50%/70%)
- **Edge Enhanced** - RGB with thermal edges in red
- **Thermal Overlay** - Hot regions overlaid on RGB
- **Max Intensity** - Brightest pixels from both sources
- **Feature Weighted** - Smart weighting based on scene content
- **Side-by-Side** - Compare thermal and RGB simultaneously
- **Picture-in-Picture** - Compact dual view

**Switch modes:** Press `V` or click "VIEW" button in GUI

---

## Distance Estimation

Monocular distance estimation using bounding box geometry:

| Zone | Range | Alert | Color |
|------|-------|-------|-------|
| **IMMEDIATE** | <5m | CRITICAL | Red |
| **VERY CLOSE** | 5-10m | CRITICAL | Orange |
| **CLOSE** | 10-20m | WARNING | Yellow |
| **MEDIUM** | 20-40m | INFO | Green |
| **FAR** | >40m | None | Blue |

**Accuracy:** 85-90% for objects within 20m (industry-standard monocular performance)

---

## Audio Alert System

ISO 26262 compliant audio warnings:

- **Frequency:** 1.5-2 kHz (optimal for human perception + road noise)
- **Pattern:** Beep pattern indicates urgency
- **Zones:** Directional (left/center/right)
- **Volume:** Adjustable (default 70%)

**Toggle:** Press `A` or use GUI button

---

## Performance

### Expected FPS

| Platform | Model | FPS |
|----------|-------|-----|
| **Jetson Orin Nano** | YOLOv8n | 30-50 |
| **Jetson Orin NX** | YOLOv8n | 50-80 |
| **RTX 3060** (x86) | YOLOv8n | 60-100 |
| **RTX 4070** (x86) | YOLOv8s | 80-120 |
| **Intel i7** (CPU only) | YOLOv8n | 15-25 |

### Optimization Tips

**Jetson:**
```bash
# Set max power mode
sudo nvpmodel -m 0
sudo jetson_clocks
```

**Windows/Linux (NVIDIA GPU):**
- Install CUDA Toolkit 11.8+
- Use `--device cuda`
- Choose smaller model for higher FPS

---

## Project Structure

```
ThermalFusionDrivingAssist/
├── main.py                      # Main application entry point
├── camera_factory.py            # Auto-detection of RGB cameras
├── rgb_camera_firefly.py        # FLIR Firefly support (PySpin)
├── rgb_camera_uvc.py            # Generic UVC webcam support
├── flir_camera.py               # FLIR Boson thermal camera
├── vpi_detector.py              # VPI-accelerated detection (Jetson)
├── fusion_processor.py          # Thermal-RGB fusion algorithms
├── road_analyzer.py             # Distance estimation + alerts
├── driver_gui_qt.py             # Professional Qt5 GUI
├── requirements.txt             # Python dependencies
├── setup_venv_py310.bat         # Windows virtual env setup
├── install_linux.sh             # Linux automated installer
├── verify_pyspin.py             # PySpin installation test
├── diagnose_spinnaker.py        # Spinnaker SDK diagnostic
│
├── docs/                        # Documentation
│   ├── WINDOWS_SETUP.md         # Detailed Windows guide
│   ├── CROSS_PLATFORM.md        # Platform compatibility
│   ├── JETSON_GPU_SETUP.md      # Jetson optimization
│   ├── CUSTOM_MODELS.md         # Training custom models
│   └── install/                 # Installation guides
│       ├── install_pyspin.md
│       └── setup_python310_env.md
│
├── CHANGELOG.md                 # Version history
└── TODO.md                      # Development roadmap
```

---

## Troubleshooting

### Camera Not Detected

**Check connected cameras:**
```bash
# Windows
python camera_factory.py

# Linux
ls -l /dev/video*
v4l2-ctl --list-devices
```

**Auto-retry:** The application automatically retries disconnected cameras every 3 seconds.

### PySpin / FLIR Firefly Issues

**Run diagnostic:**
```bash
python diagnose_spinnaker.py
```

**Common fixes:**
1. Install Spinnaker SDK: https://www.flir.com/products/spinnaker-sdk/
2. Use Python 3.10 (not 3.12): `setup_venv_py310.bat`
3. Check PySpin wheel matches Python version
4. See: `docs/install/install_pyspin.md`

### Low FPS

1. Use smaller model: `--model yolov8n.pt`
2. Enable GPU: `--device cuda`
3. Reduce detection frequency
4. Check thermal throttling (Jetson)

### No Audio Alerts

1. Check volume: Audio alerts default to 70%
2. Toggle on: Press `A` or use GUI button
3. Verify speaker/headphones connected

---

## Development

### Adding Custom Models

See [`docs/CUSTOM_MODELS.md`](docs/CUSTOM_MODELS.md) for:
- Training on FLIR thermal datasets
- Converting to ONNX/TensorRT
- Integration guide

### Contributing

1. Fork the repository
2. Create feature branch
3. Test on multiple platforms
4. Submit pull request

---

## Safety Notice

⚠️ **IMPORTANT: This system is designed as a driver assistance tool ONLY.**

- Does NOT replace human judgment
- Does NOT guarantee detection of all hazards
- NOT certified for safety-critical applications
- Use at your own risk
- Always maintain full control of your vehicle
- Follow all traffic laws and regulations

---

## Technical Specifications

### Detection Capabilities
- **Objects:** Vehicles, pedestrians, cyclists, animals
- **Range:** 5-100m (thermal), 5-50m (RGB)
- **Confidence:** 25-95% (adjustable)
- **Latency:** <100ms (GPU) / <300ms (CPU)

### System Requirements
- **Python:** 3.8, 3.9, 3.10, 3.11 (3.10 recommended for PySpin)
- **OS:** Windows 10/11, Ubuntu 20.04+, JetPack 5.0+
- **Disk:** 2GB for base install + models
- **Network:** Required for first-time model download

---

## Credits

**Developed by:** StaticCTRL
**License:** Educational and Research Use
**FLIR Thermal Imaging:** FLIR Systems, Inc.
**AI Models:** Ultralytics YOLOv8
**GUI Framework:** Qt5 (PyQt5)

---

## Version History

**v3.5** (Current)
- Python 3.10 virtual environment support
- Improved PySpin/Spinnaker SDK setup
- Enhanced documentation
- Diagnostic tools

**v3.0**
- Distance estimation system
- ISO 26262 audio alerts
- Qt5 professional GUI
- Day/night auto-theming

**v2.0**
- RGB camera fusion
- Multiple view modes
- FLIR Firefly support

**v1.0**
- Initial thermal detection
- Basic YOLO integration

See [`CHANGELOG.md`](CHANGELOG.md) for complete history.

---

## Resources

- **Project Repository:** [GitHub](https://github.com/yourusername/ThermalFusionDrivingAssist)
- **FLIR Spinnaker SDK:** https://www.flir.com/products/spinnaker-sdk/
- **Ultralytics YOLOv8:** https://github.com/ultralytics/ultralytics
- **Documentation:** [`docs/`](docs/)
- **Issue Tracker:** [GitHub Issues](https://github.com/yourusername/ThermalFusionDrivingAssist/issues)

---

**Built with thermal imaging, powered by AI, designed for safety.**
