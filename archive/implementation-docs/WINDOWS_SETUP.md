# ThermalFusionDrivingAssist - Windows Setup Guide

Complete setup guide for running ThermalFusionDrivingAssist on **Windows 10/11 (x86-64)**.

> **Other Platforms**: See [LINUX_SETUP.md](LINUX_SETUP.md) for Linux/Jetson | [MACOS_SETUP.md](MACOS_SETUP.md) for macOS | [CROSS_PLATFORM.md](CROSS_PLATFORM.md) for general info

## Supported Cameras

### Thermal Cameras
- **FLIR Boson 640x512** (USB UVC mode) - Recommended
- **FLIR Boson 320x256** (USB UVC mode)
- Any UVC-compatible thermal camera

### RGB Cameras (Optional - for sensor fusion)
- **FLIR Firefly** series (Global shutter, requires Spinnaker SDK)
- **Generic UVC webcams** (any USB webcam)

## Prerequisites

### 1. Python 3.8+ (64-bit)
Download from: https://www.python.org/downloads/

**Important**: Check "Add Python to PATH" during installation

Verify installation:
```cmd
python --version
python -m pip --version
```

### 2. Microsoft Visual C++ Redistributable
Required for some Python packages.

Download: https://aka.ms/vs/17/release/vc_redist.x64.exe

### 3. CUDA Toolkit (Optional - for GPU acceleration)
**Only if you have NVIDIA GPU and want GPU-accelerated detection:**

Download CUDA 11.8+: https://developer.nvidia.com/cuda-downloads

Verify CUDA:
```cmd
nvcc --version
```

## Installation

### Option 1: Automated Installation (Recommended)

```cmd
cd C:\Users\stati\Desktop\Projects\ThermalFusionDrivingAssist
install_windows.bat
```

This will:
1. Create Python virtual environment
2. Install all dependencies
3. Configure PyQt5 GUI
4. Test camera detection

### Option 2: Manual Installation

1. **Create virtual environment** (recommended):
```cmd
python -m venv venv
venv\Scripts\activate
```

2. **Upgrade pip**:
```cmd
python -m pip install --upgrade pip
```

3. **Install core dependencies**:
```cmd
pip install opencv-python numpy PyQt5 psutil Pillow
```

4. **Install YOLO (for object detection)**:
```cmd
pip install ultralytics
```

5. **Install PyTorch** (choose based on GPU):

**With CUDA (NVIDIA GPU)**:
```cmd
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**CPU-only (no NVIDIA GPU)**:
```cmd
pip install torch torchvision
```

6. **Install FLIR Firefly support** (optional):

Download Spinnaker SDK for Windows:
https://www.flir.com/products/spinnaker-sdk/

Install SDK, then:
```cmd
pip install spinnaker_python-*-win_amd64.whl
```

## Camera Setup

### FLIR Boson Thermal Camera

1. **Connect camera** via USB (UVC adapter required)

2. **Check Device Manager**:
   - Open Device Manager (Win + X → Device Manager)
   - Look for "Imaging devices" or "Cameras"
   - Should see "FLIR Boson" or generic "USB Camera"

3. **Test camera detection**:
```cmd
python test_flir_detection.py
```

This will:
- List all detected cameras
- Auto-detect FLIR Boson by resolution (640x512 or 320x256)
- Test frame capture
- Display live thermal preview

4. **If camera not detected**:
   - Try different USB port (USB 3.0 recommended)
   - Check camera is in UVC mode (consult FLIR documentation)
   - Close other apps using camera (Skype, Teams, etc.)
   - Restart computer

### RGB Camera (Optional)

**For generic webcam**:
- Plug in USB webcam
- Should auto-detect in Windows

**For FLIR Firefly**:
1. Install Spinnaker SDK (see above)
2. Connect Firefly via USB 3.0
3. Run Spinview software to verify camera works
4. Application will auto-detect Firefly

## Running the Application

### Quick Start

**Auto-detect all cameras**:
```cmd
python main.py
```

**Specify thermal camera**:
```cmd
python main.py --camera-id 0 --width 640 --height 512
```

**Thermal only (disable RGB fusion)**:
```cmd
python main.py --disable-rgb
```

**Use specific YOLO model**:
```cmd
python main.py --model yolov8s.pt
```

### Command Line Options

```
Camera Options:
  --camera-id N         Thermal camera device ID (auto-detect if omitted)
  --width W             Camera width (640 for Boson 640, 320 for Boson 320)
  --height H            Camera height (512 for Boson 640, 256 for Boson 320)
  --disable-rgb         Disable RGB camera (thermal only mode)

Detection Options:
  --model PATH          YOLO model (yolov8n.pt, yolov8s.pt, yolov8m.pt)
  --confidence FLOAT    Detection threshold (0.0-1.0, default: 0.25)
  --detection-mode MODE edge or model (default: model)
  --device DEVICE       cuda or cpu (default: cuda if available)

Display Options:
  --fullscreen          Start in fullscreen mode
  --scale FLOAT         Display scale factor (default: 2.0)
  --palette NAME        Thermal palette (ironbow, white_hot, etc.)

Fusion Options:
  --fusion-mode MODE    Fusion algorithm (alpha_blend, edge_enhanced, etc.)
  --fusion-alpha FLOAT  Blend ratio 0.0-1.0 (default: 0.5)
```

### Keyboard Controls

- **Q / ESC**: Quit application
- **F**: Toggle fullscreen
- **V**: Cycle view modes (Thermal, RGB, Fusion, Side-by-side, PIP)
- **D**: Toggle detection boxes
- **Y**: Toggle YOLO detection on/off
- **C**: Cycle thermal color palettes
- **A**: Toggle audio alerts
- **S**: Save screenshot
- **P**: Print performance stats
- **H**: Show help overlay

## Troubleshooting

### Camera Not Detected

**Problem**: `No cameras detected`

**Solutions**:
1. Check USB connection (use USB 3.0 port)
2. Open Device Manager → verify camera appears
3. Try different camera ID: `python main.py --camera-id 1`
4. Close other apps using camera
5. Run test script: `python test_flir_detection.py --list`

### OpenCV Import Error

**Problem**: `ModuleNotFoundError: No module named 'cv2'`

**Solutions**:
```cmd
pip install --upgrade opencv-python
```

### PyQt5 Import Error

**Problem**: `ModuleNotFoundError: No module named 'PyQt5'`

**Solutions**:
```cmd
pip install PyQt5
```

### CUDA/GPU Not Working

**Problem**: YOLO detection slow or `CUDA not available`

**Solutions**:
1. Check NVIDIA GPU installed:
   ```cmd
   nvidia-smi
   ```

2. Reinstall PyTorch with CUDA:
   ```cmd
   pip uninstall torch torchvision
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```

3. Verify CUDA:
   ```cmd
   python -c "import torch; print(torch.cuda.is_available())"
   ```

4. If no GPU, use CPU mode:
   ```cmd
   python main.py --device cpu
   ```

### Low FPS / Lag

**Problem**: Application running slowly

**Solutions**:
1. Use smaller YOLO model: `--model yolov8n.pt` (fastest)
2. Use CPU mode if GPU causing issues: `--device cpu`
3. Enable frame skip (edit code: `frame_skip_value = 2`)
4. Reduce detection confidence: `--confidence 0.4`
5. Close other applications

### Camera Opens But No Image

**Problem**: Camera detected but black screen

**Solutions**:
1. Check camera lens cap removed
2. Try different resolution:
   ```cmd
   python main.py --width 320 --height 256
   ```
3. Test with OpenCV directly:
   ```python
   import cv2
   cap = cv2.VideoCapture(0)
   ret, frame = cap.read()
   print(f"Success: {ret}, Shape: {frame.shape if ret else 'None'}")
   ```

### FLIR Firefly Not Detected

**Problem**: Firefly camera not found

**Solutions**:
1. Install Spinnaker SDK from FLIR
2. Test with SpinView software first
3. Ensure Firefly connected to USB 3.0 port
4. Install PySpin:
   ```cmd
   pip install spinnaker_python-*-win_amd64.whl
   ```

## Performance Tips

### For Best Performance:

1. **Use USB 3.0 ports** for all cameras
2. **Close background apps** (especially camera apps)
3. **Use GPU acceleration** if available (NVIDIA GPU + CUDA)
4. **Choose right YOLO model**:
   - `yolov8n.pt` - Fastest (6MB, ~50-100 FPS)
   - `yolov8s.pt` - Balanced (22MB, ~30-60 FPS)
   - `yolov8m.pt` - Accurate (52MB, ~15-30 FPS)

5. **Optimize detection**:
   - Lower confidence threshold: `--confidence 0.2`
   - Use edge detection mode: `--detection-mode edge` (faster, no YOLO)

6. **Display optimization**:
   - Lower scale: `--scale 1.5`
   - Disable fullscreen initially

## Next Steps

1. **Test camera detection**:
   ```cmd
   python test_flir_detection.py
   ```

2. **Run basic thermal-only mode**:
   ```cmd
   python main.py --disable-rgb
   ```

3. **Enable RGB fusion** (if RGB camera available):
   ```cmd
   python main.py
   ```

4. **Experiment with view modes**:
   - Press **V** to cycle views
   - Try different fusion modes with GUI buttons

5. **Optimize for your system**:
   - Test different YOLO models (press **M** in GUI)
   - Adjust confidence threshold
   - Try CPU vs GPU mode

## Windows-Specific Notes

- **No VPI acceleration**: VPI (Vision Programming Interface) is Jetson-only. Windows uses OpenCV fallback (still performs well).
- **DirectShow recommended**: Better compatibility with UVC cameras than MSMF.
- **Antivirus**: May need to whitelist Python or allow camera access in Windows Security.
- **Power settings**: Set to "High Performance" mode for best results (Control Panel → Power Options).
- **USB 3.0**: Use USB 3.0 ports for optimal camera bandwidth.

## Getting Help

1. **Check logs**: `thermal_fusion_debug.log` (created in project folder)
2. **Test cameras individually**: `python test_flir_detection.py`
3. **Verify installation**: `pip list` (check all packages installed)
4. **GitHub Issues**: Report problems with logs attached

## Windows Features

All major features fully supported on Windows:
- ✅ FLIR Boson thermal camera (640x512, 320x256)
- ✅ RGB cameras (UVC webcams + FLIR Firefly with Spinnaker)
- ✅ Thermal-RGB sensor fusion
- ✅ YOLOv8 object detection (GPU with CUDA or CPU)
- ✅ Multi-view display (Thermal, RGB, Fusion, Side-by-side, PIP)
- ✅ Real-time alerts and distance estimation
- ✅ Audio alerts via Windows sound system
- ✅ Professional PyQt5 GUI
- ✅ Hot-plug camera support (auto-reconnect)

**Windows Limitations**:
- ❌ VPI hardware acceleration (Jetson-only - OpenCV fallback used)
- ❌ CSI cameras (Jetson-only - USB cameras work fine)

## Summary

You now have a fully cross-platform thermal fusion driving assist system! The application will:
1. Auto-detect your FLIR Boson camera
2. Auto-detect RGB cameras (Firefly or webcam)
3. Use appropriate backends for Windows (DirectShow/MSMF)
4. Provide GPU acceleration if NVIDIA GPU available
5. Fall back gracefully to CPU mode if needed

Enjoy your thermal vision system!
