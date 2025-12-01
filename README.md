# Thermal Inspection Fusion Tool

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Jetson-blue)]()
[![Python](https://img.shields.io/badge/python-3.8+-green)]()
[![OpenCV](https://img.shields.io/badge/opencv-4.5+-green.svg)]()

Professional thermal imaging system combining FLIR Boson thermal cameras with RGB imaging for comprehensive inspection and analysis.

---

## Overview

**Thermal Inspection Fusion Tool** provides advanced thermal/RGB fusion capabilities for:

- 🔬 **Circuit Board Inspection** - Component temperature monitoring, thermal runaway detection
- 🏠 **Building Inspection** - Thermal leaks, insulation problems, moisture detection
- 🔍 **Equipment Analysis** - Hot/cold spot identification, temperature trend tracking

### Core Capabilities

- **7 Fusion Algorithms**: Alpha blend, edge enhanced, thermal overlay, side-by-side, picture-in-picture, max intensity, feature weighted
- **45 Thermal Palettes**: Comprehensive color mapping from grayscale to specialized medical/industrial palettes
- **Smart ROI Management**: Automatic detection (temperature threshold, gradient, motion, edge clustering) and manual creation
- **FLIR Boson SDK Integration**: Direct camera control, FFC triggering, radiometric temperature measurement
- **Radiometric Analysis**: Absolute temperature measurement with calibrated thermal data

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/ThermalInspectionFusion.git
cd ThermalInspectionFusion

# Install dependencies
pip install -r requirements.txt

# Run the application
python inspection_main.py
```

### Basic Usage

```bash
# Run with automatic ROI detection
python inspection_main.py --auto-roi

# Run with specific fusion mode and palette
python inspection_main.py --fusion-mode thermal_overlay --palette ironbow

# Run with Boson SDK for radiometric temperature
python inspection_main.py --enable-boson-sdk --boson-com-port COM6
```

### Keyboard Shortcuts

- `f` - Trigger FFC (Flat Field Correction)
- `t` - Show FPA temperature
- `r` - Toggle recording
- `s` - Capture snapshot
- `q` - Quit

---

## Features

### Thermal/RGB Fusion Engine

**7 Fusion Algorithms:**
- Alpha Blend - Weighted overlay of thermal and RGB
- Detail Injection - FLIR MSX-style grayscale detail overlay from RGB
- Relief Fusion - 3D bas-relief embossed effect
- Edge Enhanced - RGB edges with thermal color
- Thermal Overlay - Thermal colormap over RGB base
- Side-by-Side - Synchronized dual view
- Picture-in-Picture - Thermal inset on RGB
- Max Intensity - Combine brightest pixels
- Feature Weighted - Adaptive fusion based on content

Hardware-accelerated alignment and blending for real-time performance.

### Multi-Palette System

**45 Thermal Palettes** organized by category:
- **Grayscale** (7): white_hot, black_hot, grayscale variants
- **Rainbow** (8): rainbow, rainbow_hc, jet, turbo variants
- **Iron/Fire** (6): ironbow, lava, hot, copper variants
- **Arctic/Cool** (5): arctic, ice, ocean, cool variants
- **Medical** (5): medical, viridis, inferno, plasma, cividis
- **Industrial** (8): metal, sepia, autumn, bone, and specialized variants
- **High Contrast** (6): Enhanced versions of popular palettes

Features:
- Global palette or per-ROI override
- Auto-contrast and gamma correction
- Live palette switching
- Custom palette import

### ROI Management

**Automatic Detection:**
- Temperature threshold - Hot/cold regions above/below threshold
- Temperature gradient - Areas with high thermal gradients
- Motion-triggered - ROIs around detected motion
- Edge clustering - Dense edge regions

**Manual Creation:**
- Rectangle, polygon, ellipse, circle tools
- Label and track individual ROIs
- Save/load ROI sets to JSON
- Per-ROI palette assignment

### Thermal Analysis

- **Temperature Measurement**: Absolute (°C/°F) and relative analysis
- **Hot/Cold Spot Detection**: Automatic identification and tracking
- **Temperature Trends**: Track changes over time with rate prediction
- **Anomaly Detection**: Rapid changes, gradient anomalies, statistical outliers
- **Temperature Gradients**: Sobel-based gradient computation

### FLIR Boson SDK Integration

**Direct Camera Control:**
- FFC (Flat Field Correction) triggering
- Gain modes: HIGH, LOW, AUTO, MANUAL
- Color LUT selection (10+ palettes)
- FPA temperature monitoring
- Camera info: serial number, software version, part numbers

**Radiometric Support:**
- 16-bit absolute temperature data
- Kelvin to Celsius/Fahrenheit conversion
- Temperature range mapping
- Spot temperature measurement
- Area temperature statistics

See `BOSON_SDK_STATUS.md` in archive for implementation details.

### Advanced Camera Management

**Robust Auto-Detection:**
- Automatically identifies thermal and RGB cameras
- Frame-based thermal camera identification (resolution + saturation)
- Priority-based selection: Spinnaker > External USB > Built-in webcam
- Timeout protection prevents initialization hangs

**FLIR Firefly RGB Support:**
- Spinnaker SDK integration
- Advanced controls: exposure, gain, white balance, trigger
- Image enhancement: gamma, sharpness
- Max resolution auto-detection
- Connection status display

**Camera Registry:**
- Persistent camera assignments across sessions
- Automatic reconnection
- Device ID tracking

### Parallax Compensation (New v3.3.0)

**ML-Powered Depth Estimation:**
- **DepthAnything V2** integration - State-of-the-art monocular depth estimation
- 3 model sizes: Small (CPU-friendly), Base (balanced), Large (GPU recommended)
- 10x faster inference than diffusion-based methods
- Superior accuracy for thermal-RGB alignment

**Automatic Parallax Correction:**
- Depth-based pixel displacement calculation
- Adaptive alignment for objects at varying distances
- Configurable camera baseline distance
- Simplified geometric mode (fallback, no ML dependencies)

**Features:**
- Lazy model loading (first-use download, ~100-350MB cached)
- Auto device detection (CUDA/CPU)
- Depth map visualization for debugging
- Disabled by default (optional, can enable per-session)

---

## Hardware Requirements

### Minimum
- **CPU**: Intel i5 / AMD Ryzen 5 or equivalent
- **RAM**: 8GB (16GB recommended)
- **Camera**: FLIR Boson thermal camera (640x512 or 320x256)
- **GPU**: Optional (CPU mode supported)

### Recommended
- **CPU**: Intel i7 / AMD Ryzen 7 or NVIDIA Jetson
- **RAM**: 16GB+
- **Camera**: FLIR Boson + RGB camera (webcam or FLIR Firefly)
- **GPU**: NVIDIA GPU with CUDA support

---

## Command-Line Options

```bash
# Camera settings
--thermal-device 0          # Thermal camera device ID
--width 640                 # Thermal camera width
--height 512                # Thermal camera height
--disable-rgb               # Disable RGB camera

# Boson SDK settings
--enable-boson-sdk          # Enable FLIR Boson SDK for serial control
--boson-com-port COM6       # Boson COM port (default: COM6)

# Processing settings
--device cuda               # Processing device (cuda/cpu)
--palette ironbow           # Default thermal palette

# Fusion settings
--fusion-mode thermal_overlay   # Fusion algorithm
--fusion-alpha 0.5             # Alpha for alpha_blend
--calibration-file cal.json    # Camera calibration

# Inspection settings
--mode realtime             # realtime or playback
--auto-roi                  # Enable automatic ROI detection

# GUI settings
--use-opencv-gui            # Use simple OpenCV GUI
--headless                  # Run without GUI
```

---

## Project Structure

### Core Modules

**thermal_analyzer.py** - Temperature analysis engine
Temperature measurement, hot/cold spot detection, gradient analysis, anomaly detection, trend tracking

**roi_manager.py** - ROI management system
Automatic detection, manual creation, persistence, visualization

**palette_manager.py** - Multi-palette system
45 thermal palettes, global + per-ROI override, composite rendering

**thermal_processor.py** - Thermal processing
Motion detection, edge detection, palette application

**fusion_processor.py** - Fusion engine
7 fusion algorithms, hardware-accelerated alignment, priority control

**radiometric_converter.py** - Radiometric temperature conversion
16-bit to Kelvin conversion, temperature range mapping, calibration

**boson_sdk_wrapper.py** - FLIR Boson SDK interface
Serial communication, camera control, radiometric data extraction

**camera_detector.py** - Camera detection
Spinnaker SDK support, frame-based thermal ID, priority selection

**camera_initializer.py** - Thread-safe initialization
Timeout protection, graceful failure handling

**parallax_compensator.py** - Parallax compensation (NEW v3.3.0)
ML depth estimation (DepthAnything V2), depth-based alignment, geometric fallback

**firefly_control_panel.py** - Firefly camera controls
Exposure, gain, white balance, trigger, image enhancement

**inspection_gui_qt.py** - Qt-based GUI
Professional interface, ROI visualization, thermal analysis display

**inspection_main.py** - Main application
Integration of all components, command-line interface

---

## Use Cases

### Circuit Board Inspection
- Detect overheating ICs and components
- Track component temperature trends during operation
- Identify thermal runaway conditions before failure
- Compare thermal profiles before/after repair

### Building Inspection
- Find thermal leaks around windows and doors
- Identify insulation problems in walls and attics
- Detect moisture in walls (appears as cold spots)
- Inspect HVAC system performance

### Equipment Monitoring
- Monitor critical components during stress tests
- Track temperature trends over extended operation
- Alert on anomalies and rapid temperature changes
- Generate inspection reports with thermal data

---

## Documentation

- **README.md** - This file - project overview and quick start
- **TODO.md** - Prioritized feature roadmap and development tasks
- **CHANGELOG.md** - Version history and major changes
- **archive/** - Historical documentation, session summaries, fix reports
- **archive/sdk-docs/** - Boson SDK integration documentation
- **archive/implementation-docs/** - Feature implementation guides

---

## Platform Support

- **Windows 10/11** (x86-64)
- **Linux** (x86-64 and ARM64)
- **NVIDIA Jetson** (Orin, Xavier, Nano) with GPU acceleration

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

- **FLIR Systems** - Boson thermal camera SDK
- **OpenCV** - Image processing
- **NVIDIA** - VPI acceleration on Jetson

---

**Version**: 3.3.1
**Status**: Production-ready thermal inspection system with full radiometric support, ML depth estimation, and hardware-accelerated spotmeter
**Last Updated**: 2025-11-30
