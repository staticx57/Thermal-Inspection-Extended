#!/bin/bash
cd "$(dirname "$0")/.."
#
# Thermal Inspection Fusion Tool - Linux Repair/Update Script
# Brings existing installation up to date with latest requirements
#
# Usage (run from repo root):
#   chmod +x scripts/repair_linux.sh
#   ./scripts/repair_linux.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Thermal Inspection Fusion Tool Repair${NC}"
echo -e "${BLUE}(see CHANGELOG.md for the release notes)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ] || [ ! -f "thermal_inspection/app.py" ]; then
    echo -e "${RED}✗ Error: thermal_inspection/app.py not found${NC}"
    echo -e "${YELLOW}Please run this script from the Thermal Inspection Fusion Tool repo root${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Project directory found${NC}"
echo ""

# Python 3.10+ is required (3.10 - 3.12 are the tested versions)
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo -e "${RED}✗ Python 3.10 or newer is required (found: $(python3 --version 2>&1))${NC}"
    echo -e "${YELLOW}  Install a newer Python (e.g. sudo apt-get install python3.11) and re-run.${NC}"
    exit 1
fi

# Debian 12 / Ubuntu 23.04+ mark the system Python "externally managed" (PEP 668): pip refuses to install into it
STDLIB_DIR=$(python3 -c "import sysconfig; print(sysconfig.get_path('stdlib'))")
if [ -f "$STDLIB_DIR/EXTERNALLY-MANAGED" ] && [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}This system's Python is externally managed (PEP 668), so pip cannot install into it.${NC}"
    echo -e "${BLUE}Use a virtual environment, then re-run this script from inside it:${NC}"
    echo -e "    python3 -m venv --system-site-packages .venv   # keeps Jetson's CUDA OpenCV/torch visible"
    echo -e "    source .venv/bin/activate"
    echo -e "    ./scripts/$(basename "$0")"
    exit 1
fi

# Step 1: Update Python packages
echo -e "${BLUE}[1/4] Updating Python packages...${NC}"
pip3 install --user --upgrade pip

# Step 2: Install/update PyQt6 (required for v3.x Qt GUI)
echo -e "${BLUE}[2/4] Installing/updating PyQt6...${NC}"
pip3 install --user --upgrade PyQt6

# Verify PyQt6
python3 -c "from PyQt6.QtWidgets import QApplication; print('✓ PyQt6 verified')" || {
    echo -e "${RED}✗ PyQt6 installation failed${NC}"
    echo -e "${YELLOW}Trying system package...${NC}"
    sudo apt-get install -y python3-pyqt6 python3-pyqt6.qtsvg python3-pyqt6.qtopengl
}

# Step 3: Update requirements
echo -e "${BLUE}[3/4] Updating project dependencies...${NC}"
if [ -f requirements.txt ]; then
    pip3 install --user --upgrade -r requirements.txt
else
    echo -e "${YELLOW}⚠ requirements.txt not found. Updating core packages...${NC}"
    pip3 install --user --upgrade numpy scipy opencv-python Pillow PyQt6 "pyqtgraph>=0.14" psutil pyserial flirpy "setuptools<81"
fi

# Step 4: Verify installation
echo -e "${BLUE}[4/4] Verifying repaired installation...${NC}"
echo ""

VERIFICATION_FAILED=false

# Test Python modules
echo -e "${BLUE}Testing Python modules...${NC}"
python3 << 'EOF'
import sys
exit_code = 0

modules = [
    ('numpy', 'NumPy'),
    ('cv2', 'OpenCV'),
    ('PyQt6.QtWidgets', 'PyQt6'),
    ('pyqtgraph', 'pyqtgraph'),
    ('psutil', 'psutil'),
    ('serial', 'pyserial'),
    ('scipy', 'SciPy'),
    ('flirpy', 'flirpy (Boson)'),
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
    echo -e "${RED}✗ Some Python modules failed${NC}"
else
    echo -e "${GREEN}✓ All required modules available${NC}"
fi

# Test Qt GUI
echo ""
echo -e "${BLUE}Testing Qt GUI components...${NC}"
python3 << 'EOF'
import sys
try:
    from PyQt6.QtWidgets import QApplication, QPushButton, QMainWindow
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

# Check project files
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
    echo -e "${RED}Repair Failed!${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Some components failed verification.${NC}"
    echo -e "${YELLOW}You may need to pull the latest code from git:${NC}"
    echo -e "  ${BLUE}git pull origin main${NC}"
else
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Repair Complete & Verified!${NC}"
    echo -e "${GREEN}========================================${NC}"
fi

echo ""
echo -e "${BLUE}What you have:${NC}"
echo -e "  • PyQt6 GUI with a camera plugin architecture"
echo -e "  • Thermal/RGB fusion modes, 100+ palettes, ROI Manager, spot meters, radiometric analysis"
echo -e "  • Boson/Tau2/Lepton thermal camera plugins; optional 3D Fusion / 3D Mapping (see requirements.txt)"
echo ""
echo -e "${GREEN}Ready to run: python3 -m thermal_inspection${NC}"
echo -e "${GREEN}Troubleshooting: python3 -m thermal_inspection --log-level DEBUG --log-file debug.log${NC}"
echo -e "${GREEN}Or use the quick-launch scripts in scripts/ (see LAUNCHER_GUIDE.md)${NC}"
echo ""
