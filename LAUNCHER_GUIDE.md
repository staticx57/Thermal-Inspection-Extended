# Thermal Inspection Tool - Launcher Guide

## Quick Start

### Interactive Launcher (Recommended)
Double-click **`launch.bat`** to access the interactive menu with preset configurations.

### Quick Launch Shortcuts
For frequent tasks, use these one-click launchers:

- **`scripts/quick-thermal.bat`** - Thermal Priority Mode (radiometric analysis)
- **`scripts/quick-rgb.bat`** - RGB Priority Mode (visual inspection)
- **`scripts/quick-debug.bat`** - Debug Mode (DEBUG logging to the console and `thermal_inspection_debug.log`)

---

## Interactive Launcher Menu

The main `launch.bat` provides an interactive menu with 7 options:

### [1] Quick Start (Default Settings)
Launches with auto-detected cameras and default configuration.
- Auto-detect cameras (the backend is chosen per camera automatically)
- Ironbow palette
- Qt GUI

**Best for:** General purpose thermal inspection

---

### [2] Thermal Priority Mode
Optimized for radiometric temperature analysis.

**Features:**
- Boson serial control enabled (FFC, gain, temperature) via `--enable-boson-sdk`
- Ironbow palette (scientific)
- A radiometric Boson is detected automatically and uses 16-bit data; no backend flag is needed

**Device Options:**
1. Auto-detect cameras (recommended)
2. Manual: Thermal=2, RGB=0 (typical Boson setup)
3. Manual: Thermal=0, RGB=1 (alternative configuration)
4. Custom device IDs

**Prompts:**
- Boson COM port (default: COM7)

**Best for:**
- Accurate temperature measurement
- Scientific thermal analysis
- Electrical inspection
- Building diagnostics

---

### [3] RGB Priority Mode
Optimized for visual inspection with thermal overlay.

**Features:**
- Viridis palette (visual-friendly)
- RGB camera focus
- Option to disable thermal camera

**Best for:**
- General visual inspection
- Situations where thermal is supplementary
- When radiometric accuracy isn't required

---

### [4] Playback Mode
Analyze recorded thermal videos.

**Features:**
- Drag-and-drop video file support
- Full analysis tools available
- Frame-by-frame control

**Supported formats:**
- .mp4, .avi, .mov
- Thermal camera recordings
- Multi-spectral recordings

**Best for:**
- Offline analysis
- Report generation
- Training and review
- Archival inspection

---

### [5] Headless Mode
Run without GUI for automation and batch processing.

**Features:**
- No GUI overhead
- Scriptable operation
- Configurable output directory
- Suitable for remote operation

**Best for:**
- Automated inspection systems
- Server-side processing
- CI/CD integration
- Resource-constrained environments

---

### [6] Custom Arguments
Enter command-line arguments directly.

Type `help` to see all available options, or enter custom arguments like:
```
--thermal-device 2 --fusion-mode picture_in_picture --palette lava
```

**Best for:**
- Advanced users
- Testing specific configurations
- Non-standard setups

---

### [7] View Available Options
Displays comprehensive list of all command-line arguments.

**Categories:**
- Camera options (device IDs, auto-detection)
- Boson control and radiometric options
- Display (palettes, fusion modes)
- Processing (CUDA/CPU, ROI detection)
- Mode (realtime, playback)
- GUI (Qt, OpenCV, headless)

---

## Command-Line Arguments Reference

### Camera Configuration
```bat
--thermal-device ID          # Thermal camera device ID
--rgb-device ID              # RGB camera device ID
--auto-detect-cameras        # Auto-detect camera devices (default)
--disable-rgb                # Run without RGB camera
```

### Boson / Radiometric
```bat
--enable-boson-sdk           # Serial control of the Boson (FFC, gain, temperature)
--boson-com-port PORT        # COM port for Boson (default: COM7)
--radiometric                # Enable radiometric temperature measurement
--thermal-backend TYPE       # DEPRECATED and ignored: the backend is chosen per camera plugin
```

### Display
```bat
--palette ID                 # Palette id (115 palettes: ironbow, viridis, ... see the README
                             # palette table; the ID column is what this flag takes)
--fusion-mode MODE           # Fusion mode (python -m thermal_inspection --help lists them all:
                             # thermal_overlay, alpha_blend, ...)
--fusion-alpha VALUE         # Alpha for alpha_blend (0.0-1.0)
--calibration-file PATH      # Camera alignment calibration
```

### Processing
```bat
--device TYPE                # cuda or cpu (default: cuda)
--auto-roi                   # Enable automatic ROI detection
--width WIDTH                # Thermal frame width (default: 640)
--height HEIGHT              # Thermal frame height (default: 512)
--enable_parallel true|false # Parallel detection (default: true)
--max_workers N              # Worker threads for parallel detection (default: 5)
```

### Operation Mode
```bat
--mode TYPE                  # realtime or playback (default: realtime)
--playback-file PATH         # Video file for playback mode
```

### GUI
```bat
--gui TYPE                   # qt, opencv, or headless (default: qt)
--use-opencv-gui             # Simple OpenCV window instead of Qt
--headless                   # Run without GUI
```

### Diagnostics
```bat
--log-level LEVEL            # DEBUG, INFO, WARNING (default) or ERROR - the console only shows WARNING+
                             # unless you ask for more
--log-file PATH              # Also write the log (with timestamps) to this file
```

---

## Common Use Cases

### 1. Electrical Panel Inspection (High Precision)
```bat
launch.bat
[Select: 2 - Thermal Priority Mode]
[Device: 1 - Auto-detect]
[COM Port: COM7]
```
**Result:** 16-bit radiometric, accurate temperature readings

---

### 2. Building Thermal Leak Detection
```bat
scripts\quick-thermal.bat
```
**Result:** One-click launch optimized for thermal analysis

---

### 3. General Visual Inspection with Thermal Overlay
```bat
scripts\quick-rgb.bat
```
**Result:** RGB-focused with thermal supplementary data

---

### 4. Analyze Recorded Inspection
```bat
launch.bat
[Select: 4 - Playback Mode]
[Drag video file]
```

---

### 5. Remote/Automated Operation
```bat
python -m thermal_inspection --headless --thermal-device 2 --rgb-device 0
```

---

### 6. Custom PIP Configuration
```bat
python -m thermal_inspection --fusion-mode picture_in_picture
```
Then use fusion priority toggle in GUI to swap main/PIP views

---

## Troubleshooting

### Camera Not Detected
1. Use **Option 7** in launcher to verify camera connections
2. Try **Thermal Priority Mode > Manual device IDs**
3. Check camera connections and drivers
4. Run `scripts\quick-debug.bat` and review `thermal_inspection_debug.log`

### Wrong COM Port
1. Device Manager → Ports → Find Boson Serial
2. Launch → **Thermal Priority Mode**
3. Enter correct COM port when prompted

### Performance Issues
1. Try `--device cpu` if CUDA issues
2. Use lower resolution: `--width 320 --height 256`
3. Reduce processing: disable auto-ROI

### GUI Freezing
Ensure `auto_retry_sensors: false` in `config.json`

---

## Direct Command Line Usage

You can still use the traditional command-line approach:

```bat
# Direct launch with arguments
launch.bat --enable-boson-sdk --boson-com-port COM7

# Or call Python directly
python -m thermal_inspection [arguments]
```

The launcher will detect direct arguments and bypass the menu.

---

## Files Created

- **launch.bat** - Interactive launcher with menu
- **scripts/quick-thermal.bat** - One-click thermal priority
- **scripts/quick-rgb.bat** - One-click RGB priority
- **scripts/quick-debug.bat** - One-click debug mode (verbose log to `thermal_inspection_debug.log`)
- **scripts/install_windows.bat / install_linux.sh** - Installers (`--with-firefly`, `--with-3d-mapping`, `--with-realsense-l515` on Windows)
- **scripts/repair_windows.bat / repair_linux.sh** - Re-install/upgrade dependencies for an existing checkout
- **scripts/install_realsense_l515.ps1** - Builds pyrealsense2 for an Intel RealSense L515 (pip's wheels dropped it)
- **scripts/run_vpi.sh, run_with_gpu.sh, setup_jetson_gpu.sh** - Jetson / CUDA helpers
- **LAUNCHER_GUIDE.md** - This documentation

---

## Advanced Tips

### Creating Custom Quick-Launch Scripts
Copy any `scripts/quick-*.bat` file and modify the arguments:

```bat
@echo off
echo My Custom Configuration...
python -m thermal_inspection --your-custom-args
pause
```

### Chaining Commands
Use batch scripting to create workflows:

```bat
@echo off
echo Processing multiple files...
for %%f in (*.mp4) do (
    python -m thermal_inspection --mode playback --playback-file "%%f" --headless
)
pause
```

---

## Support

For issues or questions:
1. Use **scripts/quick-debug.bat** for verbose output (it writes `thermal_inspection_debug.log`)
2. Or add `--log-level DEBUG --log-file debug.log` to any launch command
3. Review this guide
4. Check main README.md for project documentation
