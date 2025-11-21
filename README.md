# Thermal Inspection Fusion Tool v2.0

> **Transformed from ADAS to Inspection Tool - 2025-11-20**
> Powerful thermal/RGB fusion system for circuit board and residential house inspection.

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Jetson-blue)]()
[![Python](https://img.shields.io/badge/python-3.8+-green)]()
[![OpenCV](https://img.shields.io/badge/opencv-4.5+-green.svg)]()

---

## 🎯 Overview

**Thermal Inspection Fusion Tool** is a professional thermal imaging system designed for comprehensive inspection applications:

- 🔬 **Circuit Board Inspection** - Detect overheating components, track temperature trends, identify thermal anomalies
- 🏠 **Residential House Inspection** - Find thermal leaks, insulation issues, moisture problems
- 🔍 **General Thermal Analysis** - Multi-palette visualization, ROI management, hot/cold spot detection

### Key Differentiator

This tool combines **thermal + RGB fusion** (7 algorithms) with **smart ROI management** (4 auto-detection methods) and **comprehensive thermal analysis** to provide unmatched inspection capabilities.

---

## ✨ Key Features

### 🔥 Fusion Engine (PARAMOUNT!)
- ✅ **7 Fusion Algorithms**: Alpha blend, edge enhanced, thermal overlay, side-by-side, picture-in-picture, max intensity, feature weighted
- ✅ **Preserved 100%** from original ADAS system
- ✅ **Hardware-accelerated** alignment and blending

### 🎯 Smart ROI Management
- ✅ **4 Automatic Detection Methods**:
  - Temperature threshold (hot/cold regions)
  - Temperature gradient (thermal edges)
  - Motion-triggered (around detected motion)
  - Edge clustering (dense edge regions)
- ✅ **Manual ROI Creation**: Rectangle, polygon, ellipse, circle
- ✅ **ROI Persistence**: Save/load ROI sets to JSON

### 🌡️ Comprehensive Thermal Analysis
- ✅ **Temperature Measurement**: Absolute & relative analysis
- ✅ **Hot/Cold Spot Detection**: Automatic identification
- ✅ **Temperature Trends**: Track changes over time with prediction
- ✅ **Anomaly Detection**: Rapid changes, gradient anomalies, statistical outliers
- ✅ **Temperature Gradients**: Sobel-based gradient computation

### 🎨 Multi-Palette System
- ✅ **14 Thermal Palettes**: From white_hot to medical imaging
- ✅ **Global + Per-ROI**: Apply different palettes to different ROIs
- ✅ **Auto-Contrast**: Automatic range stretching
- ✅ **Gamma Correction**: Adjustable visualization

### 🎥 Motion & Edge Detection
- ✅ **Motion Detection**: Temporal differencing with persistence tracking
- ✅ **Edge Detection**: VPI hardware acceleration (Jetson) + OpenCV fallback
- ✅ **Edge Clustering**: Group dense edge regions

### 🖥️ Cross-Platform
- ✅ **Windows 10/11** (x86-64)
- ✅ **Linux** (x86-64 and ARM64)
- ✅ **NVIDIA Jetson** (Orin, Xavier, Nano) with GPU acceleration

### 🎛️ FLIR Boson SDK Integration (Phase 7 - NEW!)
- ✅ **Video + Serial Control**: Combined USB interface
- ✅ **FFC Trigger**: Manual flat field correction (press `f`)
- ✅ **Temperature Monitoring**: FPA sensor temperature (press `t`)
- ✅ **Gain Control**: HIGH, LOW, AUTO, MANUAL modes
- ✅ **Color LUT**: 10+ thermal color palettes
- ✅ **Camera Info**: Serial number, software version, part numbers
- ⏳ **Radiometric Support**: 16-bit absolute temperature (pending)

**Keyboard Shortcuts:**
- `f` - Trigger FFC (Flat Field Correction)
- `t` - Show FPA temperature
- `r` - Toggle recording
- `s` - Capture snapshot
- `q` - Quit

See [BOSON_SDK_USAGE.md](BOSON_SDK_USAGE.md) for complete documentation.

---

## 🚀 Quick Start

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

# Run without RGB camera
python inspection_main.py --disable-rgb

# Run with Boson SDK for advanced camera control (Phase 7 - NEW!)
python inspection_main.py --enable-boson-sdk --boson-com-port COM6 --use-opencv-gui
```

---

## 📖 Quick Example

### Circuit Board Inspection

```python
from thermal_analyzer import ThermalAnalyzer
from roi_manager import ROIManager
from palette_manager import PaletteManager, PaletteType

# Initialize
analyzer = ThermalAnalyzer({'hot_spot_threshold': 0.85})
roi_mgr = ROIManager({'auto_roi_min_area': 500})
palette_mgr = PaletteManager({'default_palette': 'ironbow'})

# Capture thermal frame
ret, thermal_frame = thermal_camera.read()

# Auto-detect hot spots
hot_spots = analyzer.detect_hot_spots(thermal_frame, threshold=80.0)
print(f"Found {len(hot_spots)} hot spots")

# Create ROI on overheating IC
ic_roi = roi_mgr.create_rectangle_roi(245, 180, 60, 60, label="IC U7")

# Apply white_hot palette for maximum contrast
palette_mgr.set_roi_palette(ic_roi.roi_id, PaletteType.WHITE_HOT)

# Track temperature over time
mask = ic_roi.get_mask(thermal_frame.shape)
stats = analyzer.analyze_frame(thermal_frame, mask)
analyzer.update_trend(ic_roi.roi_id, stats.mean_temp)

# Check trend after 60 seconds
trend = analyzer.get_trend(ic_roi.roi_id)
if trend.trend_direction == "increasing":
    print(f"WARNING: Temperature rising at {trend.rate_of_change}°C/s")
```

---

## 🎨 14 Thermal Palettes

| Palette | Best For | Description |
|---------|----------|-------------|
| WHITE_HOT | General | Hot=white, cold=black |
| BLACK_HOT | Surveillance | Inverted grayscale |
| IRONBOW | Circuit boards | Black→purple→red→orange→yellow→white |
| RAINBOW | General purpose | Standard rainbow |
| LAVA | Hot objects | Black→red→orange→yellow→white |
| ARCTIC | Cold objects | White→cyan→blue→dark blue |
| MEDICAL | Medical imaging | Viridis color scheme |
| + 7 more | Various | See docs for complete list |

---

## 📦 Core Modules

### 1. `thermal_analyzer.py` - Temperature Analysis Engine
- Temperature measurement (absolute & relative)
- Hot/cold spot detection
- Temperature gradient analysis
- Thermal anomaly detection
- Temperature trend tracking with prediction

### 2. `roi_manager.py` - ROI Management
- 4 automatic detection methods
- Manual ROI creation (rectangle, polygon, ellipse, circle)
- ROI persistence (save/load JSON)
- ROI visualization

### 3. `palette_manager.py` - Multi-Palette System
- 14 thermal palettes
- Global + per-ROI palette override
- Composite rendering
- Auto-contrast & gamma correction

### 4. `thermal_processor.py` - Thermal Processing
- Motion detection (preserved from ADAS)
- Edge detection (VPI accelerated)
- 14 thermal palette application

### 5. `fusion_processor.py` - Fusion Engine (PARAMOUNT!)
- 7 fusion algorithms
- Hardware-accelerated alignment
- Priority control (thermal/RGB base)
- **100% preserved from ADAS system**

---

## 🔍 Use Cases

### Circuit Board Inspection
```
✓ Detect overheating ICs
✓ Track component temperature trends
✓ Identify thermal runaway conditions
✓ Compare before/after repair
```

### Residential House Inspection
```
✓ Find thermal leaks around windows/doors
✓ Identify insulation problems
✓ Detect moisture in walls (cold spots)
✓ Inspect HVAC system performance
```

### Equipment Monitoring
```
✓ Monitor critical components during stress tests
✓ Track temperature trends over time
✓ Alert on anomalies and rapid changes
✓ Generate inspection reports
```

---

## 📊 Transformation from ADAS

This project was successfully transformed from an Advanced Driver Assistance System (ADAS) to an inspection tool.

### What Changed
- ❌ **Removed**: YOLO object detection, distance estimation, road analysis, audio alerts, LiDAR
- ✅ **Added**: Thermal analyzer, ROI manager, palette manager, inspection-focused processing
- ✅ **Preserved**: Fusion engine (100%), motion detection, edge detection, 14 thermal palettes

### Statistics
- **Files Deleted**: 6 (driving modules)
- **Files Created**: 5 (inspection modules)
- **Lines Removed**: ~1,442 (driving + YOLO)
- **Lines Added**: ~2,590 (inspection features)
- **Net Change**: +1,148 lines

See [CHANGELOG.md](CHANGELOG.md) for complete transformation details.

---

## 📚 Documentation

- **[CHANGELOG.md](CHANGELOG.md)** - Complete transformation changelog
- **[INSPECTION_TRANSFORMATION_PLAN.md](INSPECTION_TRANSFORMATION_PLAN.md)** - Transformation plan
- **[TRANSFORMATION_PROGRESS.md](TRANSFORMATION_PROGRESS.md)** - Progress report
- **[CROSS_PLATFORM.md](CROSS_PLATFORM.md)** - Platform support details (from ADAS)
- **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)** - Windows installation guide (from ADAS)

---

## 💻 Hardware Requirements

### Minimum
- **CPU**: Intel i5 / AMD Ryzen 5 or equivalent
- **RAM**: 8GB (16GB recommended)
- **Camera**: FLIR Boson thermal camera (640x512 or 320x256)
- **GPU**: Optional (CPU mode works)

### Recommended
- **CPU**: Intel i7 / AMD Ryzen 7 or NVIDIA Jetson
- **RAM**: 16GB+
- **Camera**: FLIR Boson + RGB camera (webcam or FLIR Firefly)
- **GPU**: NVIDIA GPU with CUDA support

---

## ⚙️ Command-Line Options

```bash
# Camera settings
--thermal-device 0          # Thermal camera device ID
--width 640                 # Thermal camera width
--height 512                # Thermal camera height
--disable-rgb               # Disable RGB camera

# Boson SDK settings (Phase 7 - NEW!)
--enable-boson-sdk          # Enable FLIR Boson SDK for serial control
--boson-com-port COM6       # Boson COM port (default: COM6)

# Processing settings
--device cuda               # Processing device (cuda/cpu)
--palette ironbow           # Default thermal palette

# Fusion settings (PARAMOUNT!)
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

## 🧪 Testing

```bash
# Test camera detection
python test_flir_detection.py

# Test all modules
python -c "from thermal_analyzer import ThermalAnalyzer; print('OK')"
python -c "from roi_manager import ROIManager; print('OK')"
python -c "from palette_manager import PaletteManager; print('OK')"
python -c "from thermal_processor import ThermalProcessor; print('OK')"
python -c "from fusion_processor import FusionProcessor; print('OK')"
```

---

## 🐛 Troubleshooting

### Thermal Camera Not Detected
```bash
# List all cameras
python test_flir_detection.py --list

# Check permissions (Linux)
sudo usermod -a -G video $USER
```

### VPI Not Available
```
This is expected on Windows/x86 Linux
- OpenCV fallback provides good performance
- All features work correctly
```

### Low FPS
```bash
# Use GPU acceleration
python inspection_main.py --device cuda

# Disable RGB if not needed
python inspection_main.py --disable-rgb
```

---

## 🔮 Roadmap

### ✅ Phase 1-3: Core Transformation (COMPLETE)
- Thermal analyzer, ROI manager, palette manager
- 14 thermal palettes
- Motion & edge detection
- Fusion engine preserved

### ✅ Phase 6: Media Recording (COMPLETE)
- Video recording with ROI metadata
- Snapshot capture
- Playback mode

### ✅ Phase 7: FLIR Boson SDK Integration (PARTIAL - Non-Radiometric Complete)
**Completed:**
- ✅ VPC (Video over USB) support
- ✅ Native communication via serial COM over USB
- ✅ Camera control (FFC, AGC, shutter, gain)
- ✅ FPA temperature monitoring
- ✅ Non-radiometric camera support tested and working
- ✅ Keyboard shortcuts (f=FFC trigger, t=temperature)

**Pending:**
- ⏳ Radiometric camera testing (16-bit absolute temperature)
- ⏳ Radiometric data extraction and calibration
- ⏳ GUI integration (Qt controls)

**See:** [BOSON_SDK_USAGE.md](BOSON_SDK_USAGE.md) for complete SDK documentation

### Phase 4 (Next): GUI Transformation
- Create inspection_gui_qt.py
- ROI drawing tools with SDK controls
- Thermal analysis display panel
- Multi-palette controls
- FFC trigger button, gain mode selector

### Phase 5: Configuration
- Update config.json for inspection
- Remove ADAS settings

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **Original ADAS System**: staticx57 + Claude
- **Transformation to Inspection Tool**: Claude Code (Anthropic) - 2025-11-20
- **FLIR Systems**: For Boson thermal camera SDK
- **OpenCV**: For image processing
- **NVIDIA**: For VPI acceleration on Jetson

---

## 📧 Contact

- **Issues**: [GitHub Issues](https://github.com/yourusername/ThermalInspectionFusion/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/ThermalInspectionFusion/discussions)

---

**Version**: 2.1.0
**Status**: Phase 1-3, 6, 7 (partial) Complete - Boson SDK integrated (non-radiometric tested)
**Last Updated**: 2025-11-21
