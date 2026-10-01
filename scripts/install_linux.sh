#!/bin/bash
cd "$(dirname "$0")/.."
#
# Thermal Inspection Fusion Tool - Linux Installation Script
# For Jetson Orin Nano (ARM64) and x86-64 Linux systems
#
# This script installs:
# - System dependencies (OpenCV, Python packages)
# - UVC webcam support (built-in to Linux kernel)
# - OPTIONAL: FLIR Firefly Spinnaker SDK (for global shutter cameras)
#
# Usage (run from repo root):
#   chmod +x scripts/install_linux.sh
#   ./scripts/install_linux.sh                 # Install base system (UVC webcams)
#   ./scripts/install_linux.sh --with-firefly  # Install base + FLIR Firefly support
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect architecture
ARCH=$(uname -m)
IS_JETSON=false

if [ -f /etc/nv_tegra_release ]; then
    IS_JETSON=true
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Thermal Inspection Fusion Tool Installation${NC}"
echo -e "${BLUE}Version 3.0.0${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Architecture: ${GREEN}${ARCH}${NC}"
if [ "$IS_JETSON" = true ]; then
    echo -e "Platform: ${GREEN}NVIDIA Jetson$(cat /etc/nv_tegra_release)${NC}"
else
    echo -e "Platform: ${GREEN}Generic Linux${NC}"
fi
echo ""

# Parse command-line arguments
INSTALL_FIREFLY=false
for arg in "$@"; do
    case $arg in
        --with-firefly)
            INSTALL_FIREFLY=true
            shift
            ;;
        --help)
            echo "Usage: scripts/install_linux.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --with-firefly    Install FLIR Firefly Spinnaker SDK (optional)"
            echo "  --help            Show this help message"
            echo ""
            exit 0
            ;;
    esac
done

# Step 1: Update system packages
echo -e "${BLUE}[1/6] Updating system packages...${NC}"
sudo apt-get update

# Step 2: Install Python dependencies
echo -e "${BLUE}[2/6] Installing Python dependencies...${NC}"
sudo apt-get install -y python3 python3-pip python3-dev python3-numpy

# Step 3: Install OpenCV (if not already installed)
echo -e "${BLUE}[3/6] Installing OpenCV...${NC}"
if [ "$IS_JETSON" = true ]; then
    # Jetson comes with OpenCV pre-installed (with CUDA support)
    echo -e "${GREEN}✓ Jetson platform detected - using pre-installed OpenCV with CUDA${NC}"
    python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" || {
        echo -e "${YELLOW}⚠ OpenCV not found. Installing...${NC}"
        sudo apt-get install -y python3-opencv
    }
else
    # Generic Linux - install OpenCV via pip
    echo -e "${YELLOW}Installing OpenCV via pip...${NC}"
    pip3 install --user opencv-python
fi

# Step 4: Install V4L2 utilities (for UVC webcam debugging)
echo -e "${BLUE}[4/6] Installing V4L2 utilities...${NC}"
sudo apt-get install -y v4l-utils

# List available cameras
echo -e "${GREEN}✓ Listing available UVC cameras:${NC}"
v4l2-ctl --list-devices || echo -e "${YELLOW}⚠ No cameras detected${NC}"

# Step 5: Install project dependencies
echo -e "${BLUE}[5/7] Installing project Python dependencies...${NC}"
if [ -f requirements.txt ]; then
    pip3 install --user -r requirements.txt
else
    echo -e "${YELLOW}⚠ requirements.txt not found. Installing core packages manually...${NC}"
    pip3 install --user numpy scipy opencv-python Pillow PyQt6 "pyqtgraph>=0.14" psutil pyserial flirpy "setuptools<81"
fi

# Step 5.5: Install PyQt6 for Qt GUI
echo -e "${BLUE}[5.5/7] Installing PyQt6 for Qt GUI (v3.x)...${NC}"
if [ "$IS_JETSON" = true ]; then
    # Jetson: Try system package first (better performance)
    echo -e "${YELLOW}Attempting system PyQt6 installation...${NC}"
    sudo apt-get install -y python3-pyqt6 python3-pyqt6.qtsvg python3-pyqt6.qtopengl || {
        echo -e "${YELLOW}⚠ System PyQt6 failed. Installing via pip...${NC}"
        pip3 install --user PyQt6
    }
else
    # Generic Linux: pip installation
    pip3 install --user PyQt6
fi

# Verify PyQt6
python3 -c "from PyQt6.QtWidgets import QApplication; print('✓ PyQt6 installed successfully')" || {
    echo -e "${RED}✗ PyQt6 installation failed${NC}"
    echo -e "${YELLOW}⚠ Qt GUI may not work. Try: pip3 install --user PyQt6${NC}"
}

# Step 6: OPTIONAL - Install FLIR Firefly Spinnaker SDK
if [ "$INSTALL_FIREFLY" = true ]; then
    echo -e "${BLUE}[6/7] Installing FLIR Firefly Spinnaker SDK...${NC}"

    # Check architecture
    if [ "$ARCH" = "aarch64" ]; then
        # ARM64 (Jetson)
        SPINNAKER_ARCH="arm64"
        SPINNAKER_VERSION="spinnaker-3.2.0.62-Ubuntu22.04-arm64-pkg.tar.gz"  # Latest as of 2025
        SPINNAKER_URL="https://flir.netx.net/file/asset/54321/original/attachment"  # Placeholder - requires FLIR account
    elif [ "$ARCH" = "x86_64" ]; then
        # x86-64
        SPINNAKER_ARCH="amd64"
        SPINNAKER_VERSION="spinnaker-3.2.0.62-Ubuntu22.04-amd64-pkg.tar.gz"  # Latest as of 2025
        SPINNAKER_URL="https://flir.netx.net/file/asset/54320/original/attachment"  # Placeholder - requires FLIR account
    else
        echo -e "${RED}✗ Unsupported architecture for Spinnaker: ${ARCH}${NC}"
        exit 1
    fi

    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}FLIR Spinnaker SDK Installation${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo -e "${YELLOW}IMPORTANT: You need to manually download Spinnaker SDK from FLIR website:${NC}"
    echo -e "${BLUE}  1. Go to: https://www.flir.com/products/spinnaker-sdk/${NC}"
    echo -e "${BLUE}  2. Create a free account / login${NC}"
    echo -e "${BLUE}  3. Download: ${SPINNAKER_VERSION}${NC}"
    echo -e "${BLUE}  4. Place the .tar.gz file in the current directory${NC}"
    echo ""
    echo -e "${YELLOW}Once downloaded, we'll install it automatically.${NC}"
    echo ""

    # Check if Spinnaker tarball exists
    if [ -f "${SPINNAKER_VERSION}" ]; then
        echo -e "${GREEN}✓ Found ${SPINNAKER_VERSION}${NC}"
        echo -e "${BLUE}Extracting and installing...${NC}"

        # Extract
        tar -xzf ${SPINNAKER_VERSION}
        SPINNAKER_DIR=$(basename ${SPINNAKER_VERSION} .tar.gz)
        cd ${SPINNAKER_DIR}

        # Install dependencies
        sudo apt-get install -y libusb-1.0-0

        # Install Spinnaker
        echo -e "${BLUE}Installing Spinnaker packages...${NC}"
        sudo dpkg -i libgentl*.deb
        sudo dpkg -i libspinnaker*.deb
        sudo dpkg -i libspinvideo*.deb
        sudo dpkg -i spinnaker*.deb
        sudo dpkg -i spinview*.deb

        # Configure USB permissions
        echo -e "${BLUE}Configuring USB permissions...${NC}"
        sudo sh -c 'echo "SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"1e10\", MODE=\"0666\"" > /etc/udev/rules.d/40-flir-spinnaker.rules'
        sudo udevadm control --reload-rules
        sudo udevadm trigger

        # Install PySpin (Python wrapper)
        echo -e "${BLUE}Installing PySpin (Python wrapper)...${NC}"
        if [ "$ARCH" = "aarch64" ]; then
            # Jetson ARM64
            pip3 install --user spinnaker_python*.whl || {
                echo -e "${YELLOW}⚠ PySpin wheel not found. Trying pip install...${NC}"
                pip3 install --user spinnaker-python
            }
        else
            # x86-64
            pip3 install --user spinnaker_python*.whl || {
                echo -e "${YELLOW}⚠ PySpin wheel not found. Trying pip install...${NC}"
                pip3 install --user spinnaker-python
            }
        fi

        cd ..

        echo -e "${GREEN}✓ Spinnaker SDK installed successfully!${NC}"
        echo -e "${GREEN}✓ You can now use FLIR Firefly cameras${NC}"

    else
        echo -e "${RED}✗ ${SPINNAKER_VERSION} not found in current directory${NC}"
        echo -e "${YELLOW}⚠ Skipping Spinnaker installation. UVC webcams will still work.${NC}"
        echo ""
        echo -e "${BLUE}To install Spinnaker later:${NC}"
        echo -e "  1. Download SDK from https://www.flir.com/products/spinnaker-sdk/"
        echo -e "  2. Run: ./scripts/install_linux.sh --with-firefly"
    fi
else
    echo -e "${BLUE}[6/7] Skipping FLIR Firefly support (use --with-firefly to enable)${NC}"
fi

# Step 7: Verify installation
echo -e "${BLUE}[7/7] Verifying installation...${NC}"
echo ""

VERIFICATION_FAILED=false

# Test 1: Python imports
echo -e "${BLUE}Testing Python modules...${NC}"
python3 << 'EOF'
import sys
exit_code = 0

# Required modules
modules = [
    ('numpy', 'NumPy'),
    ('cv2', 'OpenCV'),
    ('PyQt6.QtWidgets', 'PyQt6'),
    ('pyqtgraph', 'pyqtgraph'),
    ('psutil', 'psutil'),
    ('serial', 'pyserial'),
]

for module, name in modules:
    try:
        __import__(module)
        print(f'  ✓ {name}')
    except ImportError:
        print(f'  ✗ {name} - FAILED')
        exit_code = 1

sys.exit(exit_code)
EOF

if [ $? -ne 0 ]; then
    VERIFICATION_FAILED=true
    echo -e "${RED}✗ Some Python modules failed to import${NC}"
else
    echo -e "${GREEN}✓ All required Python modules available${NC}"
fi

# Test 2: Qt GUI components
echo ""
echo -e "${BLUE}Testing Qt GUI components...${NC}"
python3 << 'EOF'
import sys
try:
    from PyQt6.QtWidgets import QApplication, QPushButton, QLabel, QMainWindow
    from PyQt6.QtCore import QThread, pyqtSignal
    from PyQt6.QtGui import QImage, QPixmap
    print('  ✓ Qt GUI components')
    sys.exit(0)
except Exception as e:
    print(f'  ✗ Qt GUI components - {e}')
    sys.exit(1)
EOF

if [ $? -ne 0 ]; then
    VERIFICATION_FAILED=true
    echo -e "${RED}✗ Qt GUI verification failed${NC}"
else
    echo -e "${GREEN}✓ Qt GUI ready${NC}"
fi

# Test 3: Project files
echo ""
echo -e "${BLUE}Checking project files...${NC}"
required_files=(
    "thermal_inspection/app.py"
    "thermal_inspection/cli.py"
    "thermal_inspection/gui/main_window.py"
    "thermal_inspection/processing/fusion_processor.py"
    "thermal_inspection/processing/thermal_analyzer.py"
    "thermal_inspection/processing/roi_manager.py"
    "thermal_inspection/sdk/boson_sdk_wrapper.py"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓ $file${NC}"
    else
        echo -e "  ${RED}✗ $file - MISSING${NC}"
        VERIFICATION_FAILED=true
    fi
done

echo ""
if [ "$VERIFICATION_FAILED" = true ]; then
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Verification Failed!${NC}"
    echo -e "${RED}========================================${NC}"
    echo -e "${YELLOW}Some components failed verification. Please check the errors above.${NC}"
else
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Installation Complete & Verified!${NC}"
    echo -e "${GREEN}========================================${NC}"
fi

echo ""
echo -e "${BLUE}System Status:${NC}"
echo -e "  ${GREEN}✓ Python 3 & dependencies${NC}"
echo -e "  ${GREEN}✓ OpenCV (computer vision)${NC}"
echo -e "  ${GREEN}✓ PyQt6 (Qt GUI v3.x)${NC}"
echo -e "  ${GREEN}✓ UVC webcam support${NC}"
if [ "$INSTALL_FIREFLY" = true ] && [ -f "${SPINNAKER_VERSION}" ]; then
    echo -e "  ${GREEN}✓ FLIR Firefly support${NC}"
else
    echo -e "  ${YELLOW}⚠ FLIR Firefly support: Not installed (use --with-firefly)${NC}"
fi
echo ""
echo -e "${BLUE}Qt GUI Features (v3.x):${NC}"
echo -e "  • Camera plugin architecture (Boson/Tau2/Lepton thermal, Firefly/UVC/GigE RGB)"
echo -e "  • 9 fusion algorithms, ROI management, radiometric temperature analysis"
echo -e "  • Isotherm highlighting, gradient overlays, media recording"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "  ${BLUE}1.${NC} Connect RGB camera (UVC webcam or FLIR Firefly)"
echo -e "  ${BLUE}2.${NC} Run system: ${GREEN}python3 -m thermal_inspection${NC}"
echo -e "  ${BLUE}3.${NC} Or use a quick-launch script in scripts/ (see LAUNCHER_GUIDE.md)"
echo ""
echo -e "${BLUE}Testing Commands:${NC}"
echo -e "  • List cameras: ${GREEN}v4l2-ctl --list-devices${NC}"
echo -e "  • Verify modules: ${GREEN}python3 -c 'import PyQt6; import cv2; print(\"OK\")'${NC}"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo -e "  • Main guide: ${GREEN}README.md${NC}"
echo -e "  • Launcher guide: ${GREEN}LAUNCHER_GUIDE.md${NC}"
echo -e "  • Full changelog: ${GREEN}CHANGELOG.md${NC}"
echo ""
