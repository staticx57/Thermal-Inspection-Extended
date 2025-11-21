#!/bin/bash
#
# ThermalFusionDrivingAssist - Linux Repair/Update Script
# Brings existing installation up to date with latest requirements
#
# Usage:
#   chmod +x repair_linux.sh
#   ./repair_linux.sh
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ThermalFusionDrivingAssist Repair${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if we're in the right directory
if [ ! -f "main.py" ]; then
    echo -e "${RED}✗ Error: main.py not found${NC}"
    echo -e "${YELLOW}Please run this script from the ThermalFusionDrivingAssist directory${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Project directory found${NC}"
echo ""

# Step 1: Update Python packages
echo -e "${BLUE}[1/4] Updating Python packages...${NC}"
pip3 install --user --upgrade pip

# Step 2: Install/update PyQt5 (required for v3.x Qt GUI)
echo -e "${BLUE}[2/4] Installing/updating PyQt5...${NC}"
pip3 install --user --upgrade PyQt5

# Verify PyQt5
python3 -c "from PyQt5.QtWidgets import QApplication; print('✓ PyQt5 verified')" || {
    echo -e "${RED}✗ PyQt5 installation failed${NC}"
    echo -e "${YELLOW}Trying system package...${NC}"
    sudo apt-get install -y python3-pyqt5 python3-pyqt5.qtsvg python3-pyqt5.qtopengl
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
    ('PyQt5.QtWidgets', 'PyQt5'),
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
    from PyQt5.QtWidgets import QApplication, QPushButton, QMainWindow
    from PyQt5.QtCore import QThread, pyqtSignal
    from PyQt5.QtGui import QImage, QPixmap
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
    "main.py"
    "driver_gui_qt.py"
    "video_worker.py"
    "developer_panel.py"
    "alert_overlay.py"
    "config.py"
    "object_detector.py"
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
echo -e "  • Qt GUI (replaces OpenCV GUI)"
echo -e "  • Multithreaded video processing"
echo -e "  • Developer mode (Ctrl+D) with 9 controls"
echo -e "  • ADAS-compliant alert overlays"
echo -e "  • Custom model support (see CUSTOM_MODELS.md)"
echo -e "  • Simulated thermal camera (debug mode)"
echo -e "  • Light/Dark theme auto-switching"
echo ""
echo -e "${GREEN}Ready to run: python3 main.py${NC}"
echo ""
