# Thermal Inspection Fusion Tool

[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20Jetson-blue)]()
[![Python](https://img.shields.io/badge/python-3.10+-green)]()
[![OpenCV](https://img.shields.io/badge/opencv-4.5+-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-blue.svg)]()

Professional-grade thermal imaging application combining FLIR Boson/Lepton thermal cameras with RGB imaging for comprehensive visual inspection and radiometric temperature analysis.

---

## Overview

**Thermal Inspection Fusion Tool** is a Python application designed for thermal imaging professionals, engineers, and technicians performing:

- **Circuit Board Inspection** - Component temperature monitoring, thermal runaway detection, pre/post-repair thermal profiling
- **Building & HVAC Inspection** - Thermal leaks, insulation defects, moisture detection, energy audits
- **Equipment Diagnostics** - Hot spot identification, bearing analysis, electrical panel inspection
- **Research & Development** - Thermal characterization, heat dissipation studies, material testing

Built on Qt6 with a themeable GUI (10 themes, including one that follows your system's light/dark setting), the application provides real-time thermal/RGB fusion, radiometric temperature measurement, automatic ROI detection, and comprehensive thermal analysis tools.

---

## Key Features

### 🔥 Advanced Thermal-RGB Fusion

**13 Fusion Modes** (2D Fusion tab, or `--fusion-mode`):
- **Alpha Blend** - Weighted overlay of thermal and RGB images
- **Detail Injection** (`detail_inject`) - FLIR MSX-style grayscale detail overlay from RGB onto thermal
- **Relief Fusion** - 3D bas-relief embossed effect for enhanced depth perception
- **Edge Enhanced** - Thermal base with RGB edge overlays for structural context
- **Thermal Overlay** (default) - Thermal colormap overlaid on RGB base with adjustable transparency
- **Side by Side** - Dual view for direct comparison
- **Picture in Picture** - Thermal inset on RGB (or vice versa). Composed on a larger canvas when the inset has more detail than its slot, so the inset stays sharp
- **Max Intensity** - Pixel-wise maximum intensity fusion
- **Feature Weighted** - Adaptive blending based on edge strength and content
- **Thermal Contours** - Isotherm-style contour lines over the RGB image, optionally labelled with temperatures in the selected unit
- **Laplacian Pyramid** - Multi-scale blending of thermal and RGB at each frequency band (GPU path when available)
- **PCA Fusion** - Weights thermal and RGB intensities along their principal component
- **Guided Filter Fusion** - Saliency-weighted blend using guided filtering

**Real-time fusion controls**: Live mode switching, alpha blending (0-100%), edge color/intensity adjustment, detail strength tuning.

### 🌡️ Radiometric Temperature Measurement

**Measurement sources** (chosen automatically per camera plugin):
- **Radiometric cameras** (e.g. a radiometric `-R` Boson) - 16-bit Y16 capture with true absolute temperatures (±2°C)
- **Non-radiometric cameras** - 8-bit AGC frames: optional temperature *estimation* (±5-10°C, referenced to the FPA temperature; enable it in Analysis > Radiometric) or raw AGC counts. Estimates are never presented as measured temperatures, and the gradient and line-profile tools show `AGC` counts instead of degrees on these cameras

**Temperature Measurement Features**:
- Spot temperature metering (click anywhere on the thermal image): multiple concurrent spots with labels, history graph, per-spot alerts (threshold with sound/flash), CSV/JSON export
- **Line profile** - drag a line across the image, plot the temperature along it, export to CSV
- ROI-based area temperature statistics (min/max/mean/median/std)
- Hot/cold spot detection and tracking
- **Isotherm highlighting** - a single range or multiple bands, with a choice of highlight colour
- **Gradient overlay** (Detection tab) - highlights where temperature changes quickly
- **Units** - °C, °F, K or raw Y16 (Kelvin × 100). Readouts, thresholds, presets, histogram, line profiles and exports follow the selected unit
- 3-tier measurement fallback: 16-bit radiometric → 8-bit estimation → raw AGC counts

### 🎨 Multi-Palette System

**115 Thermal Color Palettes** in 10 categories, each previewed inline as a strip of colour swatches
(see the full [Palette Reference](#palette-reference) for what every palette looks like and what it is best for):
- **Grayscale** (11): White Hot, Black Hot, Sepia, plus low-glare night-vision monochromes (green, red, cyan, blue)
- **Iron / Fire** (18): Ironbow, Lava, Graded Fire, Inferno, Hot Metal and other heat ramps
- **Rainbow** (13): Rainbow High Contrast, Smooth Rainbow, Turbo-style and full-spectrum maps
- **Cold / Arctic** (13): Arctic, Ice, Ocean and other cold-emphasis ramps
- **Scientific** (16): perceptually uniform / colorblind-safe (Viridis, Cividis, Batlow, colorcet, ...)
- **Diverging** (18): for temperature *difference* from a reference (Blue - Red, Vik, Seismic, ...)
- **Sequential** (7), **Single-Hue** (9), **Specialized** (8)
- **Banded** (2): flat colour steps for threshold screening

**Palette Features**:
- Global palette applied to the entire thermal image (Analysis > General > Global Palette)
- Per-ROI palette override for multi-palette composite views (ROI Manager, or right-click an ROI)
- Inline swatch previews (4-8 swatches depending on width) and friendly names in every palette picker
- Live palette switching; `C` cycles palettes
- Per-palette auto-contrast, gamma and invert options (`PaletteConfig`)
- Add your own palettes in code - see [Adding Custom Palettes](#adding-custom-palettes)

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

**ROI Manager tab**:
- Live table per ROI: average / min / max, **peak hold**, trend (▲▼), area (pixels and % of frame) and alert state; the hottest ROI is highlighted. Values follow the app's temperature unit (estimated readings are marked `~`).
- **Rename, Lock, Hide/Show, Duplicate, Delete** (also on the right-click menu). A locked ROI can't be renamed or deleted; a hidden ROI isn't drawn or measured but stays in the list.
- **Threshold alerts** per ROI on the hottest pixel, average or coldest pixel (above/below, with an optional beep); alerts are saved with the ROI set.
- Select two ROIs for a difference readout; optional **history graph** with an average / hottest / coldest selector.
- **Save / Load ROI Set** (JSON) and **Export** to CSV or JSON (readings, peaks, area, alert state).

**Spot meters**: peak-hold shown next to the live reading (right-click → Reset Peak Hold), **rate-of-change alerts** (rises/falls faster than N per minute) alongside above/below alerts, "snap new spots to the hottest nearby pixel", and history/peak survive a °C/°F/K switch.

### 🔬 Comprehensive Thermal Analysis

**Real-Time Analysis**:
- **Hot/Cold Spot Detection** - Automatic identification of temperature extremes
- **Spot-Meter History** - History graph and trend readout for each spot meter
- **Anomaly Detection** - Rapid global and per-region temperature change, gradient regions and statistical outliers. Rates and gradients are in real degrees (°C/s, °C/px) on radiometric cameras and are shown in the selected unit
- **Gradient Overlay** (Detection > Gradient) - Sobel magnitude, X, Y or direction arrows, thresholded in °C/px
- **Line Profiles** - Temperature along a dragged line
- **Histogram Analysis** - Temperature distribution visualization

**Per-ROI Statistics**:
- Min/max/mean/median/std dev temperatures
- Temperature range
- ROI area and center coordinates
- Color-coded visualization

### 📹 Media Recording & Playback

**Recording Features**:
- Video recording to AVI (`mp4v` codec by default, configurable with `video_codec`). The fusion display is always recorded; separate thermal and RGB files are optional
- JSON metadata file alongside each recording (per-frame timestamps, ROIs, thermal statistics)
- Snapshots as PNG or JPEG, with metadata
- Frames are resized to the recording's size if the display size changes mid-recording (for example when switching to Picture-in-Picture), instead of being silently dropped
- Configurable output directories and filename templates with timestamps

**Playback Features**:
- Play FLIR radiometric recordings (`.seq` / `.fff`) as a live thermal source with exact per-pixel temperatures (`--playback-file rec.seq`, needs flirpy 0.6+; `.csq` must be exported to `.seq` in FLIR Tools). The app's own `.avi` recordings are not played back by this flag.

### 📷 Universal Camera Plugin Architecture

The application features a modular, role-based camera plugin architecture with auto-discovery and generic hardware command dispatch.

#### Supported Camera Plugins:

| Plugin | Role | Interface / Protocol | Resolutions | Key Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **FLIR Boson** | Thermal | USB UVC + COM Port (921600 baud CCI) | 640×512, 320×256 | FFC, Gain Modes (High/Low/Auto), AGC Tuning, Shutter, T-Linear 16-bit Radiometry, FPA Telemetry |
| **FLIR Tau 2** | Thermal | USB UVC video (DirectShow/V4L2) + COM Port (57600 baud CCI) when the board exposes one | 640×512, 336×256, 324×256, 160×128 | **Video Mode** (works without a control line): the camera's own colour picture, or the raw Y16 stream. With a control line: FFC, gain, palette (LUT), AGC type, shutter, T-Linear temperature map, FPA/housing temperature. **Video-only breakout boards** (no serial/CDC interface in Device Manager) get the video modes only - see [Tau 2 limits](#flir-tau-2-palette-stuck-or-not-radiometric) |
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
- **10 themes**: Dark, **OLED Black** (true black for OLED panels), Light, Solarized, Colorful, three Windows XP
  styles (Luna, Silver, Olive) and two hardware-inspired themes (**Classic IBM** - System/360 console & PC-era
  cream keycaps, blue label plates, amber lamps; **Classic HP** - 1970s-80s instrument/calculator look with
  charcoal keycaps, orange lit keys and LED readouts)
- **Auto theme follows your system's light/dark setting** and switches live when the OS changes (falls back to time of day
  if the OS setting can't be read); choose it from Settings > Theme or cycle with the theme button
- Buttons keep the same size in every theme
- Tabbed panel layout for organized controls
- Resizable video display with aspect ratio preservation
- Real-time performance monitoring (FPS, processing time)

**Panel Organization** (right-hand panel; `Ctrl+B` or View > Side panel shows or hides it):
- **📊 Analysis** - General (global palette, overlay toggles, detection results), Spot Meters, Overlays (grid), Radiometric (units, scene range, calibration, estimation), ROI Manager (per-ROI statistics, palettes, export), Environmental (emissivity and atmosphere), Isotherm, Line Profile
- **🔎 Detection** - Automatic and Manual anomaly detection, plus the **Gradient** overlay that highlights where temperature changes quickly (threshold in °C/px, optional direction arrows)
- **📷 Cameras** - Thermal and RGB panels per camera plugin (Boson, Tau 2, Lepton, Firefly, USB Webcam, GigE Vision, RealSense), plus Calibration and Parallax
- **🧬 2D Fusion** - 13 fusion modes, alpha/intensity/edge controls
- **🧊 3D Fusion** - RealSense depth point-cloud / relief settings and preview
- **🗺️ 3D Mapping** - World mapping with save/load
- **⚙️ Settings** - Compute device (CPU / CUDA / DirectML), theme, SDK COM port

### 🗺️ 3D Mapping (RealSense L515 / D4xx, requires `open3d`)
Scan a space once with a RealSense depth camera, then keep tracking the camera inside it.
- **Scan:** *Start Mapping* switches to the 3D Mapping view and builds a point-cloud world from RGB-D odometry (key-frame tracking, so a held-still camera does not drift). The IMU (L515, D435i, D455) gives the tracker a gyro rotation head-start and a gravity check.
- **Live tracking:** after *Finish Mapping* the world is frozen and the camera is tracked against it (multi-scale ICP, automatic re-localization if tracking is lost or after loading a saved world).
- **3D viewer (main view):** click a point for its position, distance from the camera and temperature (live / peak / change); *Measure* gives the distance between two points in metric and imperial; hotspot markers can be snapped to (toggle). Orbit, zoom and pan with the mouse.
- **Temperatures:** recorded per point only from an aligned, genuinely radiometric thermal camera (never from estimates). Texture and temperature colouring, a colour legend, hotspots and changes versus a previously saved world are available; temperatures follow the app's unit setting.
- **Save / Load / Export:** worlds save as `.ply` with a `.thermal.npz` sidecar; temperatures export to CSV.
- Snapshot and record in this mode capture the RGB feed.

Status: scanning, tracking, save/load and the viewer are verified on a real L515 with a held-still camera. Moving-camera scans and per-point thermal temperatures have not yet been verified on hardware.

### ⚡ Performance Optimization

**Multi-threaded Architecture**:
- Separate threads for thermal and RGB capture
- Parallel processing of fusion and analysis
- Non-blocking UI updates

**Hardware Acceleration**:
- OpenCV GPU acceleration (CUDA support)
- NumPy vectorized operations
- VPI acceleration on NVIDIA Jetson

**Overlay cost**:
- The gradient overlay only colours and blends the pixels above its threshold, reuses its result when the camera frame hasn't changed, and holds large-sensor frames to about 30 recomputes per second. Its output is identical to the plain per-pixel computation
- The Gradient panel shows the current scene's typical and strong gradient to help pick a threshold

**Configurable Performance**:
- Compute device: CPU, CUDA or DirectML (Settings tab, or `--device`)
- Parallel detection toggle and worker count (`--enable_parallel`, `--max_workers`)

---

## Quick Start

### Installation

#### Prerequisites
- Python 3.10+
- OpenCV 4.5+ with Python bindings
- Qt6 (PyQt6)
- FLIR Boson or Lepton thermal camera
- (Optional) FLIR Firefly RGB camera with Spinnaker SDK
- (Optional) Intel RealSense D400 or L500/L515-series camera for hardware depth

#### Install Dependencies

```bash
# Clone repository
git clone https://github.com/staticx57/Thermal-Inspection-Extended.git
cd Thermal-Inspection-Extended

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

# Radiometric (-R) Boson: 16-bit radiometry is used automatically (requires flirpy).
# The backend is chosen per camera plugin; --thermal-backend is deprecated and ignored.

# Run with specific fusion mode and palette
python -m thermal_inspection --fusion-mode detail_inject --palette ironbow

# Play back a recorded video
python -m thermal_inspection --playback-file recordings/inspection.seq

# Enable automatic ROI detection
python -m thermal_inspection --auto-roi

# Disable RGB camera (thermal-only mode)
python -m thermal_inspection --disable-rgb
```

### First Run Tips

1. **Camera Detection**: Application auto-detects thermal and RGB cameras. If detection fails, manually specify device IDs.
2. **Radiometry**: A radiometric (-R) Boson is used in 16-bit mode automatically. On a non-radiometric camera you'll see AGC counts unless you enable estimation (Analysis > Radiometric).
3. **COM Port**: Check Windows Device Manager for correct COM port (usually COM6 or COM7 for Boson).
4. **Fusion Mode**: The default is `thermal_overlay`; try `detail_inject` or `edge_enhanced` for best thermal-RGB fusion quality.
5. **Palette**: `ironbow`, `rainbow_hc`, or `lava` are good starting palettes. See the [Palette Reference](#palette-reference).
6. **Theme**: The default "Auto" follows your system's light/dark setting; pick another in Settings > Theme or press `T`.
7. **Status banner**: the box in the corner of the video shows `FPS` (frames the camera is delivering) and `Loop` (how fast the processing loop is running, usually far higher). Hide it with Analysis > General > *Show Status Banner*.
8. **Help > About** shows the version, your Python/Qt/OpenCV versions, which optional features are installed, where your settings live, and any camera problems since the app started.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `V` | Cycle view mode (thermal / RGB / fusion / ...) |
| `C` | Cycle palettes |
| `T` | Cycle themes |
| `R` | Toggle recording |
| `S` | Capture snapshot |
| `Space` | Freeze / unfreeze the display |
| `A` | Run automatic ROI detection |
| `Ctrl+B` | Show / hide the right-hand panel |
| `F1` | List the keyboard shortcuts |
| `Ctrl+Q` | Quit (asks first while recording; `Esc` / `Q` no longer quit) |

Mouse: with Spot Meter mode on, click the thermal image to add a spot; with "Enable Line Drawing Mode" on (Analysis > Line Profile), drag to draw a profile line; right-click an ROI for its context menu.

---

## Command-Line Options

```
usage: python -m thermal_inspection [-h] [--thermal-device THERMAL_DEVICE]
                   [--rgb-device RGB_DEVICE] [--auto-detect-cameras]
                   [--width WIDTH] [--height HEIGHT] [--disable-rgb]
                   [--enable-boson-sdk] [--boson-com-port BOSON_COM_PORT]
                   [--thermal-backend {opencv,flirpy}] [--device {cuda,cpu}]
                   [--palette PALETTE] [--radiometric]
                   [--fusion-mode {alpha_blend,detail_inject,relief_fusion,edge_enhanced,thermal_overlay,side_by_side,picture_in_picture,max_intensity,feature_weighted,thermal_contours,laplacian_pyramid,pca_fusion,guided_filter_fusion}]
                   [--fusion-alpha FUSION_ALPHA]
                   [--calibration-file CALIBRATION_FILE]
                   [--auto-cycle-fusion-modes SECONDS]
                   [--mode {realtime,playback}]
                   [--playback-file PLAYBACK_FILE] [--auto-roi]
                   [--gui {qt,opencv,headless}] [--use-opencv-gui]
                   [--headless] [--enable_parallel ENABLE_PARALLEL]
                   [--max_workers MAX_WORKERS]

Thermal + RGB Fusion Inspection Tool

options:
  -h, --help            show this help message and exit
  --thermal-device THERMAL_DEVICE
                        Thermal camera device ID (default: auto-detect)
  --rgb-device RGB_DEVICE
                        RGB camera device ID (default: auto-detect)
  --auto-detect-cameras
                        Auto-detect camera types (default: True)
  --width WIDTH         Thermal camera width (default: 640)
  --height HEIGHT       Thermal camera height (default: 512)
  --disable-rgb         Disable RGB camera
  --enable-boson-sdk    Enable FLIR Boson SDK for serial control (FFC, gain,
                        temperature)
  --boson-com-port BOSON_COM_PORT
                        Boson COM port for SDK control (default: COM7)
  --thermal-backend {opencv,flirpy}
                        Deprecated, ignored - backend selection is now
                        automatic per camera plugin
  --device {cuda,cpu}   Processing device (default: cuda)
  --palette PALETTE     Thermal palette name (default: ironbow)
  --radiometric         Enable radiometric temperature measurement (default:
                        False)
  --fusion-mode {alpha_blend,detail_inject,relief_fusion,edge_enhanced,thermal_overlay,side_by_side,picture_in_picture,max_intensity,feature_weighted,thermal_contours,laplacian_pyramid,pca_fusion,guided_filter_fusion}
                        Fusion mode (default: thermal_overlay)
  --fusion-alpha FUSION_ALPHA
                        Fusion alpha for alpha_blend mode (default: 0.5)
  --calibration-file CALIBRATION_FILE
                        Camera calibration file for alignment
  --auto-cycle-fusion-modes SECONDS
                        Self-drive through every fusion mode
                        (get_available_modes()), holding each for SECONDS,
                        then exit automatically. Switches to Fusion view mode
                        if not already. For automated performance testing
                        without manual UI clicking - not for normal use.
  --mode {realtime,playback}
                        Inspection mode (default: realtime)
  --playback-file PLAYBACK_FILE
                        FLIR radiometric recording (.seq or .fff) to play instead of a live thermal camera (implies --mode playback)
  --auto-roi            Enable automatic ROI detection
  --gui {qt,opencv,headless}
                        GUI type (default: qt)
  --use-opencv-gui      Use simple OpenCV GUI instead of Qt
  --headless            Run without GUI
  --enable_parallel ENABLE_PARALLEL
                        Enable parallel processing (default: True)
  --max_workers MAX_WORKERS
                        Maximum number of worker threads for parallel
                        detection (default: 5)
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Console log level (default: WARNING - INFO lines are
                        hidden unless you ask for them)
  --log-file PATH       Also write the log, with timestamps, to this file
  --reset-camera-cache  Forget the saved camera scan (rebuilt on the next
                        start), then exit. Use it if a camera is missing after
                        a crash or force-quit
```

---

## Palette Reference

The app ships **115 thermal palettes** in 10 categories. Pick one from **Analysis → General → Global Palette** (each row previews its colours as 4-8 swatches, cold → hot, and shows a friendly name), per-ROI from the **ROI Manager**, from the ROI right-click menu, cycle with `C`, or start with `--palette <id>`. The **ID** column is the name used in `config.json`, presets and the `--palette` flag.

**Choosing a palette**

- *General inspection / hot spots*: Ironbow, Lava, White Hot.
- *Cold leaks, insulation, moisture*: Arctic, Ice, Rainbow High Contrast.
- *Judging relative temperature by eye or publishing results*: Viridis, Inferno, Fire (Perceptual), Batlow, Cividis (colorblind-safe).
- *Differences from a reference*: a diverging palette (Blue – Red, Deep Blue–Red, Vik, Seismic).
- *Threshold screening*: Banded Heat or Banded Rainbow.
- *Dark rooms / preserving night vision*: Red Hot, Night Vision Green, Sepia.
- *Printing in black and white*: Black Hot, Greys, Cubehelix, Perceptual Spectrum, La Jolla.

> A few palettes share the same colours (kept so existing presets keep working): **Gray = White Hot**, **Hottest = Ironbow**, **Medical ≈ Lava**. The *Rain*, *Cyan Hot*, *Blue Hot* and *Banded* palettes are hand-built looks, not vendor LUTs. Palette colours are display-only; they do not change any measured temperature.

### Grayscale (11)

Single-tone ramps. Show structure best and are the safest choice when the thermal image is fused with RGB. The coloured monochromes (green, red, cyan, blue) are low-glare night-vision styles.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| White Hot | `white_hot` | black → dark gray → gray → light gray → white | The standard FLIR-style look. Most structural detail; best for finding targets, texture and general-purpose inspection. |
| Black Hot | `black_hot` | white → light gray → gray → dark gray → black | Same data inverted (hot = dark). Good for bright/outdoor scenes, dark silhouettes of hot objects, and ink-friendly printed reports. |
| Grayscale | `gray` | black → dark gray → gray → light gray → white | Identical to White Hot; kept so older configs/presets that name `gray` still work. |
| Sepia | `sepia` | black → dark orange → orange → light orange | Warm, low-glare monochrome for long sessions and report screenshots. |
| Night Vision Green | `green_hot` | black → dark green → green → light green → white | Night-vision phosphor look. Low glare for dark-adapted viewing. |
| Red Hot | `red_hot` | black → dark red → red → light red → white | Red-only ramp that preserves night vision. Dark-room and low-light use. |
| Copper | `copper` | black → dark orange → orange → light orange | Single-hue warm ramp. A calmer alternative to gray for long sessions. |
| Cyan Hot | `cyan_hot` | black → dark cyan → cyan → light cyan → white | Low-glare cool monochrome for dark rooms and clean report captures. |
| Blue Hot | `blue_hot` | black → dark blue → blue → light blue → white | Low-glare blue monochrome; like Cyan Hot with a deeper tint. |
| Bone (X-Ray) | `bone` | black → dark blue → blue → light cyan → white | X-ray/radiography look with a slight blue cast in the highlights. Good for fine detail on boards and small parts. |
| Pink | `pink` | black → red → light orange → light yellow → white | Soft pastel-tinted monochrome with warm highlights. Gentle gradients; low priority for measurement work. |

### Iron / Fire (18)

Black-to-white heat ramps through red/orange/yellow. The default family for hot-spot inspection (electrical, mechanical, electronics).

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Ironbow | `ironbow` | black → dark magenta → magenta → orange → yellow → white | The industry-standard thermal palette. Intuitive hot-spot finding for electrical, mechanical and general inspection. |
| Lava | `lava` | black → dark red → red → orange → yellow → white | Black to white through red/orange/yellow. Emphasizes heat intensity; good for electrical and mechanical hot spots. |
| Graded Fire | `gradedfire` | black → dark red → red → orange → yellow → white | Finer red/orange steps than Lava, so small differences in the hot range are easier to separate. |
| Hottest | `hottest` | black → dark magenta → magenta → orange → yellow → white | Identical to Ironbow (kept as an alias for older configs). |
| Amber | `amber` | black → dark orange → orange → yellow → white | Warm amber heat ramp with low blue content. Comfortable for prolonged hot-spot viewing and fire-service style use. |
| Inferno | `inferno` | black → dark purple → magenta → red → yellow → light yellow | Perceptually uniform fire ramp: equal steps look like equal changes, so it reads well for quantitative judgement and prints well. |
| Hot Metal | `afmhot` | black → dark red → orange → light yellow → white | Smooth black → red → white heat ramp ("hot metal"). Clean hot-spot emphasis with little color confusion. |
| Midnight Fire | `gnuplot2` | black → blue → purple → magenta → yellow → white | Wide-range fire ramp with blue/purple lows. Useful for scenes with a very large temperature span. |
| Sunrise | `ylorrd` | light yellow → orange → red → dark magenta | Pale yellow to orange to deep red/magenta (more heat = darker). Good on white backgrounds and in printed reports. |
| Fire (Perceptual) | `cc_fire` | black → dark red → red → orange → yellow → white | Kovesi's perceptually uniform "fire". Among the best ramps for judging relative temperature by eye. |
| La Jolla | `lajolla` | black → dark orange → red → orange → light yellow | Crameri's dark brown/red to cream-yellow ramp. Colorblind-safe and grayscale-safe; good for print. |
| Rocket | `rocket` | black → dark magenta → magenta → red → orange → light orange | seaborn's black → magenta → red → orange ramp. Smooth, dark-background friendly hot-spot view. |
| Flare | `flare` | orange → red → magenta → dark purple | seaborn's orange → red → purple ramp (the hot end is the dark purple). Soft, warm-toned palette. |
| Golden | `wistia` | light green → yellow → orange | Yellow-green to yellow to orange. High-visibility warm ramp for spotting small warm targets. |
| Autumn | `autumn` | red → orange → yellow | Two-tone red → yellow ramp with hot = yellow. Quick read of the hottest regions. |
| Gist Heat | `gist_heat` | black → dark red → red → orange → white | Black → red → yellow → white. A clean, conventional heat ramp. |
| Yellow–Orange–Brown | `ylorbr` | white → light yellow → orange → dark orange | Near-white to pale yellow to orange to brown. Muted sequential heat ramp for reports. |
| Orange–Red | `orrd` | white → light orange → red → dark red | Near-white to orange to deep red. Light-background heat map; good for printouts. |

### Rainbow (13)

Wide hue ranges for separating many temperature levels at once. Easy to read, but not perceptually uniform - prefer the perceptual variants (Smooth Rainbow, Turbo) when you need to judge relative temperature.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Rainbow | `rainbow` | red → orange → yellow → green → blue → purple | OpenCV's RAINBOW map. Note the cold end is RED and the hot end purple - unusual for thermal; kept for compatibility. Prefer Rainbow High Contrast for blue = cold. |
| Rainbow High Contrast | `rainbow_hc` | blue → cyan → green → yellow → orange → red | Blue (cold) to red (hot) through cyan/green/yellow. Many distinct bands; good for spotting any difference and for building/HVAC surveys. |
| Rainbow Reversed | `rainbow_rev` | red → orange → yellow → green → cyan → blue | Red at the cold end running to blue at the hot end - an inverted look, hot = blue. |
| Spectral | `spectral` | magenta → red → light orange → light green → cyan → blue | Magenta → orange → yellow → green → blue. Broad hue range for discriminating many levels (hot = blue). |
| Cool to Hot | `cool_hot` | dark blue → blue → cyan → yellow → orange → dark red | Classic JET-style blue → green → red ramp. Familiar general-purpose temperature map. |
| Full Spectrum | `nipy_spectral` | black → blue → green → orange → light gray | Black → purple → blue → green → yellow → red → gray. Very wide discrimination of many levels. |
| Rain | `rain` | black → blue → cyan → yellow → orange → white | Hand-built approximation of a FLIR-style "Rain" look: black → blue → cyan → green → yellow → red → white. Not the vendor's exact LUT. |
| Isoluminant Rainbow | `cc_isolum` | cyan → green → yellow → light orange | Isoluminant rainbow: constant lightness, so only hue changes. Best for judging color alone without brightness bias. |
| Smooth Rainbow | `cc_rainbow` | blue → cyan → green → yellow → orange → red | Kovesi's smooth, perceptually better rainbow. A safer rainbow when you want hue variety. |
| Hawaii | `hawaii` | dark magenta → red → yellow → green → light cyan | Crameri's colorful sequential ramp. Scientific-grade alternative to a rainbow. |
| Gist Rainbow | `gist_rainbow` | red → yellow → green → cyan → blue → magenta | Saturated full-hue sweep for maximum level separation (not perceptually uniform). |
| Stern | `gist_stern` | black → purple → blue → gray → yellow → white | Black → purple → blue → gray → yellow → white. A busy multi-hue map whose level steps are easy to see. |
| NCAR Spectrum | `gist_ncar` | dark blue → cyan → green → yellow → magenta → white | NCAR-style spectrum with many distinct hues; heavy discrimination of levels. |

### Cold / Arctic (13)

Blue/cyan-weighted ramps that emphasize the cold end: drafts, insulation gaps, moisture and refrigeration.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Arctic | `arctic` | dark blue → blue → cyan → light cyan → white | Dark blue to white through cyan. Highlights cold regions - cold-air leaks, insulation gaps, refrigeration. |
| Ice | `ice` | dark blue → blue → light blue → light cyan → white | Deep blue to near-white. Cold-emphasis palette for moisture and insulation surveys. |
| Winter | `winter` | dark blue → blue → cyan → green | Blue to green. Gentle cool-toned ramp for low-contrast scenes. |
| Ocean | `ocean` | black → dark blue → blue → cyan | Black to dark blue to cyan. Low-glare cold-emphasis palette. |
| Lagoon | `ylgnbu` | dark blue → blue → cyan → light green → light yellow | Deep blue → teal → pale yellow (hot = light). Clean cool-to-light ramp for reports. |
| Oslo | `oslo` | black → dark blue → blue → light blue → white | Crameri's black → blue → white sequential ramp. Colorblind-safe cold emphasis. |
| Mako | `mako` | black → dark purple → blue → cyan → light green | seaborn's black → blue → mint ramp. Smooth, dark-background friendly cool palette. |
| Crest | `crest` | green → cyan → blue | seaborn's green → blue-green → blue ramp. Soft cool palette for low-contrast scenes. |
| Cyan–Magenta | `cool` | cyan → blue → purple → magenta | Cyan to magenta. High-visibility cool-toned ramp. |
| Blue–Purple | `bupu` | white → light blue → purple → magenta → dark magenta | White → light blue → purple → magenta. Light-background cool-to-warm ramp. |
| Green–Blue | `gnbu` | white → light green → cyan → blue → dark blue | White → light green → blue. Light-background cool ramp. |
| Blue–Green | `bugn` | white → light cyan → cyan → green → dark green | White → light cyan → green. Light-background cool ramp. |
| Purple–Blue | `pubu` | white → light blue → blue → dark blue | White → light blue → deep blue. Light-background cool ramp. |

### Scientific (16)

Perceptually uniform (and mostly colorblind-safe) ramps from matplotlib, colorcet and the Scientific Colour Maps. Best when accuracy of visual comparison matters or the image will be published.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Viridis | `viridis` | dark purple → blue → cyan → green → yellow | Perceptually uniform and colorblind-friendly. A strong default for any quantitative reading. |
| Plasma | `plasma` | dark blue → purple → magenta → red → orange → light yellow | Perceptually uniform blue → purple → orange → yellow. Good contrast for measurement displays. |
| Magma | `magma` | black → dark purple → magenta → red → orange → light yellow | Perceptually uniform black → purple → orange → pale yellow. Dark-background heat maps. |
| Cividis (Colorblind-Safe) | `cividis` | dark blue → blue → gray → orange → yellow | Optimized for color-vision deficiency and still readable in grayscale. |
| Turbo | `turbo` | dark purple → blue → cyan → light green → yellow → red | Google's improved rainbow: smoother and more uniform than JET while keeping a wide hue range. |
| Perceptual Spectrum | `cmrmap` | black → blue → magenta → orange → yellow → white | Perceptual ramp designed to survive grayscale printing. Good for documents that may be printed in black and white. |
| Blue–Magenta–Yellow | `cc_bmy` | dark blue → purple → magenta → red → orange → yellow | Blue → magenta → yellow perceptual ramp (colorcet). Strong hue variety without rainbow artefacts. |
| Black–Blue–Cyan | `cc_kbc` | dark blue → blue → cyan → light cyan | Black → blue → cyan perceptual ramp (colorcet). Cool dark-background map. |
| Black–Green–Yellow | `cc_kgy` | black → dark green → green | Black → green → yellow perceptual ramp (colorcet). Natural-feeling single-path ramp. |
| Blue–Green–Yellow–White | `cc_bgyw` | dark blue → blue → cyan → green → yellow → white | Blue → green → yellow → white perceptual ramp (colorcet). Broad uniform range. |
| Batlow | `batlow` | dark blue → dark cyan → green → yellow → light orange → light magenta | Crameri's flagship multi-hue ramp. Colorblind-safe, grayscale-safe, perceptually uniform. |
| Lipari | `lipari` | black → blue → gray → red → orange → light yellow | Crameri's dark-to-light multi-hue ramp. Colorblind-safe. |
| Turku | `turku` | black → dark gray → yellow → orange → light red → white | Crameri's black/gray → olive-yellow → salmon → white ramp. Subtle, print-safe. |
| Twilight Shifted | `twilight_shifted` | dark purple → blue → light blue → light orange → red → dark purple | Cyclic map (ends meet), shifted so the dark end sits at the low values. For cyclic quantities; unusual for temperature. |
| Summer | `summer` | dark cyan → green → yellow | Green to yellow. Simple two-tone ramp for quick relative reading. |
| Spring | `spring` | magenta → orange → yellow | Magenta to yellow. High-visibility two-tone ramp. |

### Diverging (18)

Two hues meeting at a neutral centre. Use them for temperature difference from a reference (before/after, left/right, set-point), not for absolute temperature - centre the range on the reference first.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Blue – Red | `blue_red` | blue → light blue → light red → red | Blue → white → red. Temperature difference from a reference: centre (white) = no change. |
| Cool – Warm | `cool_warm` | blue → orange → red | Blue → gray → red. Softer diverging ramp for deviation from a reference. |
| Purple – Orange | `purple_orange` | dark magenta → magenta → light purple → light orange → orange | Purple → white → orange. Diverging ramp that remains distinguishable for most color-vision types. |
| Green – Red | `green_red` | green → light green → light red → red | Green → white → red. Pass/fail style deviation view. Avoid for red-green color-vision deficiency. |
| Blue – Yellow | `blue_yellow` | blue → light blue → light yellow → yellow | Blue → white → yellow. Diverging ramp that works well for color-vision deficiency. |
| Pink – Green | `pink_green` | magenta → light magenta → light green → green | Magenta → white → green. Diverging ramp, distinct from the blue/red family. |
| Seismic | `seismic` | dark blue → blue → light blue → light red → red → dark red | Dark blue → white → dark red. High-contrast diverging ramp for large deviations. |
| Cold to Hot (Blue-Yellow-Red) | `rdylbu` | blue → light cyan → light yellow → red | Blue → pale yellow → red, cold to hot. Gentle diverging ramp that doubles as a readable absolute-temperature map. |
| Brown – Teal | `brbg` | dark orange → orange → light yellow → light cyan → cyan → black | Brown → white → teal. Diverging ramp that avoids red/blue temperature associations (good for humidity/moisture deltas). |
| Roma | `roma` | blue → cyan → yellow → orange → dark red | Crameri's diverging ramp oriented cold = blue to hot = red. Colorblind-safe, perceptually uniform. |
| Vik | `vik` | dark blue → blue → light cyan → light orange → orange → dark red | Crameri's blue ↔ red diverging ramp. Colorblind-safe, perceptually uniform. |
| Berlin | `berlin` | light blue → cyan → dark blue → black → red → light red | Crameri's blue ↔ red diverging ramp with dark extremes. |
| Icefire | `icefire` | light cyan → blue → dark blue → dark red → red → light orange | seaborn's blue → black → red diverging ramp. Dark centre: good on dark backgrounds. |
| Deep Blue–Red | `rdbu` | dark blue → blue → light blue → light orange → red → dark magenta | Dark blue → white → dark red. Standard diverging ramp for temperature deltas. |
| Gray–Red | `rdgy` | black → gray → light gray → light orange → red → dark magenta | Gray → white → red. Diverging ramp emphasizing only the warm side. |
| Pink–Yellow–Green | `piyg` | dark magenta → magenta → light magenta → light green → green → dark green | Pink → white → green diverging ramp. |
| Purple–Green | `prgn` | dark magenta → purple → light magenta → light green → green → dark green | Purple → white → green diverging ramp. |
| Deep Purple–Orange | `puor` | dark purple → purple → light blue → light orange → orange → dark orange | Purple → white → orange diverging ramp (purple = cold side). |

### Sequential (7)

Smooth multi-hue sequential ramps with their own character.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Globow | `globow` | green → yellow → orange → red | Green → yellow → orange → red. Increasing-danger traffic-light feel for go/no-go screening. |
| Medical | `medical` | black → dark red → red → orange → yellow → white | Black → red → yellow → white (OpenCV HOT). Essentially the same look as Lava. |
| Thermal | `thermal` | black → dark blue → green → yellow → orange → white | Black → cyan → green → orange → white. Distinctive multi-hue sequential ramp. |
| Helix | `helix` | black → purple → cyan → green → orange → white | Black → blue → green → yellow → white. Sequential ramp winding through color space. |
| Cubehelix | `cubehelix` | black → dark blue → dark cyan → green → yellow → light red | Dark blue → cyan → green → pinkish. Designed to stay readable when printed in grayscale. |
| Twilight | `twilight` | light gray → blue → cyan → light yellow → light gray | Cyclic light gray → blue → yellow → light gray. For cyclic quantities; unusual for temperature. |
| Dusk | `dusk` | black → dark purple → magenta → red → orange → light yellow | Black → purple → magenta → orange → pale yellow. A warm sequential ramp similar to Magma. |

### Specialized (8)

Purpose-styled ramps (fusion overlays, flow, terrain, depth).

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Fusion | `fusion` | blue → purple → magenta → red | Blue → purple → magenta → red. Saturated hot/cold scheme that stands out against a grayscale or RGB background. |
| Prism | `prism` | red → yellow → green → cyan → purple → magenta | Red → yellow → green → blue → magenta. Multi-color sweep; emphasizes level boundaries rather than absolute temperature. |
| Alarm | `alarm` | blue → green → yellow → orange → red → magenta | Blue → green → yellow → red → magenta. Smooth ramp that ends in magenta for extremes (it is not a hard threshold). |
| Edge Enhance | `laplacian` | dark blue → blue → light blue → light orange → orange → dark red | Dark blue → blue → white → orange → dark red. Diverging, bright-centred ramp (despite the name it is a color map, not an edge filter). |
| Isotherm Bands | `isotherm` | dark blue → blue → green → orange → red | Dark blue → cyan → green → yellow → red. Smooth gradient (the discrete isotherm bands live in the Isotherm panel; see Banded palettes for stepped output). |
| Velocity | `velocity` | blue → cyan → green → orange → red | Blue → cyan → green → yellow → red. Flow/speed-style ramp. |
| Terrain | `terrain` | dark blue → cyan → green → orange → white | Dark blue → cyan → green → yellow → white. Elevation-style ramp. |
| Depth | `depth` | dark red → dark orange → orange → yellow → light yellow → white | Dark red → orange → pale yellow → white. Depth-perception style ramp (far = dark red). |

### Single-Hue (9)

One hue from light to dark (plus an earth-tone ramp). Understated and print-friendly; good for reports and slides.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Earth | `gist_earth` | black → blue → green → orange → white | Earth-tone ramp: dark blue → green → tan → white. Terrain-style colouring. |
| Blues | `blues` | white → light blue → blue → dark blue | Pale to dark blue. Clean single-hue ramp for reports. |
| Greens | `greens` | white → light green → green → dark green | Pale to dark green. Clean single-hue ramp for reports. |
| Oranges | `oranges` | white → light orange → orange → dark orange | Pale to dark orange. Warm single-hue ramp for reports. |
| Reds | `reds` | white → light orange → red → dark red | Pale to dark red. Warm single-hue ramp for reports. |
| Purples | `purples` | white → light blue → blue → purple → dark purple | Pale to dark purple. Single-hue ramp for reports. |
| Grays | `greys` | white → light gray → gray → dark gray → black | Light to dark gray (more = darker). Ink-friendly printed reports. |
| Purple–Red | `purd` | white → light purple → magenta → dark magenta | Pale purple to deep red. Two-hue warm-leaning ramp. |
| Red–Purple | `rdpu` | white → light red → light magenta → magenta → dark purple | Pale pink to deep purple. Two-hue ramp. |

### Banded (2)

Flat colour bands instead of a smooth gradient: a contour-map look that makes threshold crossings obvious.

| Palette | ID | Cold → hot | Best for |
|---|---|---|---|
| Banded Heat | `banded_heat` | black → dark purple → cyan → green → orange → red | Eight flat bands (black, indigo, blue, teal, green, yellow, orange, red). Reads like a contour map: every change of band is a real step; good for threshold screening. |
| Banded Rainbow (High Contrast) | `banded_rainbow` | purple → blue → green → yellow → red → white | Eight high-contrast flat bands (violet, blue, sky blue, green, yellow, orange, red, white). Maximum separation between adjacent levels for outdoor/bright-light viewing. |

Colour data for the additional palettes is sampled from matplotlib colormaps, ColorBrewer (Apache 2.0), colorcet (Peter Kovesi, CC BY 4.0), the Scientific Colour Maps (Fabio Crameri, MIT) and seaborn (BSD-3-Clause); only the sampled numbers are embedded (`processing/palette_stops.py`), so none of those packages are needed at runtime.

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
- **Windows 11** (x86-64) - the development and test platform
- **Linux and NVIDIA Jetson** - install and run scripts are provided in `scripts/` but are not regularly tested

### Tested Hardware
- **FLIR Boson 640** (radiometric -R and non-radiometric) and **FLIR Tau 2** (video only; serial control untested)
- **Intel RealSense D455** and **L515** - both confirmed live end-to-end (color + real metric depth)
- Generic UVC webcams, GigE Vision cameras

---

## Project Structure

```
Thermal-Inspection/
├── README.md, CHANGELOG.md, requirements.txt
├── launch.bat
├── scripts/                         # install/repair/quick-launch scripts
├── tools/                           # standalone helpers: tau2_xu_probe.py (read-only Tau 2 USB control probe), mapping_motion_test.py
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
│   │       └── firefly/, uvc/, gige/, realsense/   # RGB / network / depth cameras
│   │
│   ├── core/                        # Controllers & managers
│   │   ├── fusion_controller.py, roi_controller.py, radiometric_controller.py
│   │   ├── media_manager.py, calibration_manager.py, camera_state.py
│   │   ├── threshold_manager.py, isotherm_manager.py
│   │   └── event_bus.py             # GUI <-> backend signal broker
│   │
│   ├── processing/                  # Fusion, palettes (palette_manager.py + palette_stops.py), ROI/thermal analysis, gradients
│   ├── sdk/                         # FLIR Boson/Lepton/Tau2 serial protocols, GigE GVCP
│   ├── gui/
│   │   ├── main_window.py           # InspectionAppWindow
│   │   ├── panels/                  # Fusion, radiometric, ROI, isotherm, parallax, etc.
│   │   ├── camera_control/          # Per-plugin control panels
│   │   ├── widgets/                 # Video/overlay, palette_combo (swatch picker), paged_tabwidget, ...
│   │   └── themes/                  # Dark/Light/OLED/..., _retro.py (XP family), _instrument.py (IBM/HP)
│   └── utils/                       # Config, presets, media recording, temperature unit conversion, exceptions
│
└── tests/unit/                      # pytest suite
```

---

## Use Cases

### 1. Circuit Board Inspection
**Problem**: Identify overheating components on PCBs during operation.

**Solution**:
1. Mount Boson thermal camera above PCB workbench
2. Use a radiometric (-R) camera (16-bit) for accurate temperature measurements
3. Use `temperature_threshold` auto-ROI to detect components above 80°C
4. Apply `ironbow` or `lava` palette for clear hot spot visualization
5. Use spot metering to measure specific IC temperatures
6. Record thermal video during power-up sequence
7. Export ROI temperature statistics for documentation

**Typical Settings**:
- Fusion: `thermal_overlay` (thermal on RGB PCB image)
- Palette: `ironbow` or `lava`
- Auto-ROI: Temperature threshold (75°C+)
- Camera: radiometric (16-bit)

### 2. Building Energy Audit
**Problem**: Find thermal leaks and insulation defects in residential/commercial buildings.

**Solution**:
1. Walk through building with handheld Boson + RGB camera
2. Use `side_by_side` or `picture_in_picture` fusion for documentation
3. Apply `arctic` or `rainbow_hc` palette for intuitive cold spot identification
4. Mark ROIs on windows, doors, walls, and attic access
5. Export annotated images for audit report
6. Compare before/after insulation improvements

**Typical Settings**:
- Fusion: `side_by_side` or `alpha_blend`
- Palette: `arctic` (blue = cold leaks) or `rainbow_hc`
- Manual ROIs: Rectangle tool for windows/doors
- Camera: a non-radiometric (8-bit) camera is sufficient for relative temperature

### 3. Electrical Panel Inspection
**Problem**: Detect loose connections and failing breakers before they cause fires.

**Solution**:
1. Capture thermal image of electrical panel under load
2. Use `temperature_gradient` auto-ROI to detect high thermal gradients (loose connections)
3. Enable hot spot detection to automatically flag dangerous components
4. Measure spot temperatures of each breaker
5. Apply `lava` or `ironbow` palette for clear visualization
6. Save snapshot and ROI data for maintenance records

**Typical Settings**:
- Fusion: `thermal_overlay`
- Palette: `lava` or `ironbow`
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
- Palette: `arctic` (cooling) or `lava` (heating)
- Temperature trends enabled
- Camera: radiometric or not

---

## Advanced Features

### Parallax Compensation

When thermal and RGB cameras are physically separated, parallax errors cause misalignment. This tool provides ML-powered depth estimation to correct for parallax.

**Enable Parallax Compensation**:
1. Go to Cameras > Parallax
2. Enable "Use Parallax Compensation"
3. Select model size (Small for CPU, Large for GPU)
4. Set camera baseline (distance between thermal and RGB lenses in cm)
5. Model downloads automatically on first use (~100-350MB)

**Models**:
- **Small** - Fastest, CPU-friendly, good accuracy
- **Base** - Balanced speed and accuracy
- **Large** - Best accuracy, requires GPU

**Camera Calibration tab (Cameras > Camera Calibration; the temperature one is "Temp Calibration")**: everything that registers the thermal and RGB views, in one place. A strip at the top shows registration and parallax status, one shared scene distance (typed, or **Measure** from a depth camera), the alignment overlay, and **Check alignment** (measures the residual misregistration in pixels through all active corrections). Pages: **1 Register** (the fixed part: calibrate from the live feeds, load/save/clear, apply on/off, manual and auto fine-tune shift/zoom, crop), **2 Parallax** (the distance-dependent part: enable, correction target, depth method, depth/displacement views) and **3 Rig** (baseline, lens focal length/sensor width). The calibration is remembered across restarts (`alignment_calibration.json` next to `config.json`) and the strip tells you whether parallax correction is combined with it correctly.

**Using it with a calibration file** (`--calibration-file`): a calibration homography is exact for one plane, at the distance it was made; parallax correction handles every other distance. They work together only if the file records that distance, so create it with:

```
python -m thermal_inspection.cameras.camera_calibration --thermal t.png --rgb r.png --distance 2.0 --out calibration.json --preview check.png
```

(snapshots of the same flat scene taken at the same moment; `--method checkerboard` or `--edges` for thermal-vs-visible). With a distance recorded, the app subtracts the shift the homography already contains while parallax is on; for a file without one it logs a warning, because the baseline shift would otherwise be applied twice.

### FLIR Recordings and External Frame Sync (flirpy 0.6)

**Playback**: `--playback-file rec.seq` (or a single `.fff`) replaces the live thermal camera with the recording, looped at its frame rate. Temperatures come from each frame's own Planck calibration, emissivity and atmosphere stored in the file (flirpy's `raw2temp`), delivered in the same Kelvin x 100 form a radiometric Boson produces, so spot meters, ROIs, isotherms, statistics and snapshots work unchanged and no camera is needed. The whole `.seq` is read into memory. Camera serial/firmware are read directly because flirpy reads those two fields at the wrong offsets.

**External frame sync (Boson)**: Cameras > Thermal > FLIR Boson > *External Frame Sync* sets the camera to *Master* (outputs a sync pulse each frame), *Slave* (captures on an incoming pulse) or *Disabled*. Wire a master's sync output to a slave's sync input so two cameras (or a thermal and a global-shutter RGB camera) expose together; this removes the frame-time offset that otherwise shows up as misalignment when something moves.

### Custom Palettes

Palettes are defined in code. See [Adding Custom Palettes](#adding-custom-palettes) in the Development section.

### Presets and ROI Sets

- ROI sets (JSON) are saved and loaded from the **ROI Manager** tab (**Save ROI Set... / Load ROI Set...**), including each ROI's lock, visibility, palette and alert. There are no application-level settings presets yet.

### Temperature Data Export

Export temperature measurements for external analysis:
- **Spot Meters** tab - Export CSV / Export JSON (readings, statistics, history)
- **ROI Manager** tab - Export Data (per-ROI statistics)
- **Line Profile** tab - Export CSV of the selected line
- **Snapshots** (`S`) - PNG or JPEG of the current display, with a metadata file

Exported values use the unit selected in the Radiometric panel.

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

If this is a **radiometric (-R)** Boson: this shouldn't happen: the control panel shares the same connection flirpy uses for video instead of opening a second, competing one (error 255 meant: the port was already open elsewhere). If you still see it, please report it.

**Solutions** (non-radiometric Boson, or anything else still hitting this):
1. **Check COM Port**: Open Device Manager > Ports, find "FLIR Control" device. The app auto-detects this port at startup — `--boson-com-port` only needs to be passed to override it.
2. Verify no other application is using the COM port (close FLIR tools)
3. Try unplugging/replugging USB cable
4. Check baud rate (default 921600 works for most Bosons)

### 16-bit Radiometric Mode Not Working

**Problem**: Temperatures are shown as AGC counts or as estimates instead of true radiometric values.

**Solutions**:
1. Install flirpy: `pip install flirpy`
2. Verify the camera is a radiometric (-R) Boson (non-radiometric units only have 8-bit AGC output)
3. Check the SDK/CCI connection and that T-Linear mode is on (Cameras > FLIR Boson > Radiometric)
4. Specify the COM port if it isn't auto-detected
5. Check logs for detailed error messages
6. Fallback: enable 8-bit temperature estimation (Analysis > Radiometric) for approximate values

### Fusion Quality Poor

**Problem**: Thermal and RGB images don't align properly or fusion looks blurry.

**Solutions**:
1. **Parallax Misalignment**: Enable parallax compensation (Cameras > Parallax)
2. **Resolution Mismatch**: Check if RGB camera resolution matches thermal (640x512 recommended)
3. **Calibration**: Run camera calibration and save calibration file
4. **Fusion Mode**: Try different modes (`detail_inject`, `edge_enhanced` are most forgiving)
5. **Manual Offset**: Use parallax panel geometric mode to manually adjust X/Y offset

### Low Frame Rate

**Problem**: Application runs slow (< 15 FPS) or UI is unresponsive.

**Solutions**:
1. **Disable Auto-ROI**: Auto-detection is CPU-intensive
2. **Reduce Workers**: Start with `--max_workers 2`
3. **Disable Parallax**: DepthAnything model is GPU-intensive
4. **Lower Resolution**: Use 320x256 Boson instead of 640x512
5. **GPU Acceleration**: Ensure CUDA is installed and detected (`--device cuda`)
6. **Close Other Apps**: Free up system resources

### A Camera Won't Open, or Disappears After a Crash
<a id="camera-wont-open"></a>

**Problem**: A camera is missing, or the app shows a banner such as *"Could not open FLIR Tau 2 for the Thermal slot: ..."*.

**What the banner means**: it gives the reason, one of: the camera did not open within 10 s (a hung driver, or another program or a frozen copy of this app is holding it); the driver reported a specific error (quoted); or the device would not open (in use by another program, unplugged, or missing its driver). Help > About lists the recent problems.

**Solutions**:
1. Close other programs that use cameras, and any frozen copy of this app (Task Manager: end `python.exe`). **Closing the app normally is safe; force-ending it while it holds a camera can leave the camera busy.**
2. Forget the saved camera scan: launcher option **[9]**, `scripts\repair_windows.bat`, or `python -m thermal_inspection --reset-camera-cache`. A scan that ran while a camera was held can be remembered with a short device list.
3. Record what happened: launcher option **[8] Diagnostic Run** writes `logs\diagnostic.log` (or use `--log-level INFO --log-file debug.log`).
4. Vendor "virtual" DirectShow sources (Basler GenICam, Pleora eBUS) are deliberately never opened: they deliver no frames and opening one can crash the process.

### FLIR Tau 2: Palette Stuck or Not Radiometric
<a id="flir-tau-2-palette-stuck-or-not-radiometric"></a>

**Problem**: A Tau 2 breakout board is stuck on one palette and shows no temperatures.

**Cause**: Changing the palette, and the temperature (T-Linear) output, are camera commands sent over the Tau 2's serial control line (CCI). Many breakout boards expose only the USB video interface (Device Manager shows one camera and no COM/serial device), so the app cannot send them. The serial path is implemented from the Tau 2 IDD but has not been tested on real hardware. The control groups on the Tau 2 panel are greyed out in that case, with the reason.

**What works without a control line** (Cameras > FLIR Tau 2 > Controls > *Video Mode*):
- **Onboard colour picture** - the camera's own AGC and palette. Looks good; the palette cannot be changed.
- **Raw sensor data** - the app's palettes and contrast tools apply, so you can pick any of the 100+ palettes. On the boards tested this stream carries roughly 8 bits of picture detail (about 255 levels), not 14, and the values are **not temperatures**. Sparse levels are spread evenly so the picture does not look thresholded. Opening it can also give a slow (~1 fps) wide-range mode that degrades; switch modes to reopen.

Real temperatures and palette control need a control line: a board with a working serial/CDC or UVC-control path. `python tools/tau2_xu_probe.py` is a read-only helper that reports what vendor controls a board exposes over USB.

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
1. **Check the Source**: Use a radiometric (16-bit) camera for accurate measurements (±2°C); estimated 8-bit values are ±5-10°C
2. **Emissivity**: Adjust material emissivity (Analysis > Environmental)
3. **Calibration**: Run radiometric calibration with reference temperatures
4. **T-Linear Mode**: Verify T-Linear mode is enabled (Cameras > FLIR Boson > Radiometric)
5. **FFC**: Trigger FFC to recalibrate the camera (Cameras > FLIR Boson > Controls > Trigger FFC)
6. **Reflected Temperature**: Account for atmospheric/reflected temperature in environmental settings

---

## Documentation

- **README.md** - Project overview, quick start, features, palette reference (this file)
- **CHANGELOG.md** - Version history, major changes, implementation details
- **LAUNCHER_GUIDE.md** - Using `launch.bat` and its startup modes

---

## Development

### Architecture

**Multi-threaded Camera Capture**:
- Separate threads for thermal and RGB cameras prevent blocking
- Frame queues for asynchronous processing
- Timeout protection prevents initialization hangs

**Processing Pipeline**:
1. Capture thermal and RGB frames (parallel threads)
2. Apply thermal processing (palette, normalization, edge detection, isotherm / gradient / threshold overlays)
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

1. Edit `processing/fusion_processor.py` and add a method `_my_fusion(self, thermal, rgb)`
2. Add the mode name to `AVAILABLE_FUSION_MODES` and a display label to `FUSION_MODE_LABELS` (one list feeds the 2D Fusion dropdown, `--fusion-mode` and `set_mode()`)
3. Dispatch to your method where the other modes are chosen (the `elif self.fusion_mode == ...` chain)

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

Palettes are added in code (there is no palette-import menu). Keep the steps in this order; the tests check that every palette is complete:

1. Add a member to `PaletteType` in `processing/palette_manager.py` (its value is the ID used by config, presets and `--palette`)
2. Add its colour stops (BGR, cold to hot) to `processing/palette_stops.py` - `"gradient"` for a smooth ramp, or `"steps"` for flat bands
3. List it once in `PALETTE_CATEGORIES` and give it a unique friendly name in `PALETTE_DISPLAY_NAMES`
4. Run `pytest tests/unit/test_palette_picker.py`

A palette is a 256 x 3 array of BGR values (`uint8`); the stops are interpolated across those 256 entries.

### Running Tests

```bash
# Run full test suite (1400+ tests)
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

MIT License.

---

## Acknowledgments

- **FLIR Systems** - Boson/Lepton SDK, thermal camera hardware
- **OpenCV** - Image processing and computer vision
- **flirpy** - Python interface for FLIR cameras
- **DepthAnything V2** - Monocular depth estimation for parallax compensation
- **Qt / PyQt6** - Professional cross-platform GUI framework
- **NVIDIA** - VPI acceleration on Jetson platforms
- **matplotlib, ColorBrewer, colorcet (Peter Kovesi), Scientific Colour Maps (Fabio Crameri), seaborn** - colour data for the additional palettes (see the Palette Reference)

---

## Version

**Version**: 3.7.0 (see [CHANGELOG.md](CHANGELOG.md))
**Tested hardware**: FLIR Boson 640 (radiometric and non-radiometric), Intel RealSense D455 and L515. FLIR Tau 2 is video-only.

---

## Contact & Support

- **Issues**: https://github.com/staticx57/Thermal-Inspection-Extended/issues
- **Documentation**: this README, CHANGELOG.md and LAUNCHER_GUIDE.md

---

**Built for thermal imaging professionals. Engineered for reliability.**
