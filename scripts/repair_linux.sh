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
echo -e "${BLUE}Version 3.0.0${NC}"
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
    pip3 install --user --upgrade numpy opencv-python ultralytics supervision torch torchvision
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
    ('ultralytics', 'Ultralytics YOLO'),
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
echo -e "${BLUE}Latest Features (v3.x):${NC}"
echo -e "  • PyQt6 GUI with camera plugin architecture"
echo -e "  • 9 fusion algorithms, ROI management, radiometric analysis"
echo -e "  • Boson/Tau2/Lepton thermal camera plugins"
echo ""
echo -e "${GREEN}Ready to run: python3 -m thermal_inspection${NC}"
echo -e "${GREEN}Or use the quick-launch scripts in scripts/ (see LAUNCHER_GUIDE.md)${NC}"
echo ""
