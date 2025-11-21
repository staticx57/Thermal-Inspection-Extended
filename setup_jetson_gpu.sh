#!/bin/bash
# Setup script for GPU acceleration on Jetson Orin

echo "========================================"
echo "Jetson Orin GPU Setup for Thermal Monitor"
echo "========================================"
echo ""

# Check if running on Jetson
if [ ! -f /etc/nv_tegra_release ]; then
    echo "WARNING: This does not appear to be a Jetson device"
    echo "This script is designed for NVIDIA Jetson Orin"
    exit 1
fi

echo "Detected Jetson platform:"
cat /etc/nv_tegra_release
echo ""

# Check JetPack version
echo "Checking JetPack version..."
sudo apt-cache show nvidia-jetpack | grep Version
echo ""

# Check CUDA installation
echo "Checking CUDA installation..."
if command -v nvcc &> /dev/null; then
    nvcc --version
else
    echo "WARNING: nvcc not found. CUDA may not be properly installed."
fi
echo ""

# Check current PyTorch installation
echo "Checking PyTorch installation..."
python3 -c "import torch; print(f'PyTorch version: {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')" 2>&1

CUDA_WORKS=$?
echo ""

if [ $CUDA_WORKS -eq 0 ]; then
    CUDA_CHECK=$(python3 -c "import torch; print('yes' if torch.cuda.is_available() else 'no')" 2>/dev/null)

    if [ "$CUDA_CHECK" = "yes" ]; then
        echo "✓ CUDA is working properly!"
        echo ""
        echo "GPU Information:"
        python3 -c "import torch; print(f'  Device: {torch.cuda.get_device_name(0)}'); print(f'  Compute Capability: {torch.cuda.get_device_capability(0)}'); print(f'  Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB')"
        echo ""
        echo "Your system is ready to run the Thermal Road Monitor!"
        exit 0
    fi
fi

echo "✗ CUDA is NOT working with PyTorch"
echo ""
echo "To fix this, you need to install PyTorch with CUDA support for Jetson:"
echo ""
echo "1. For JetPack 5.x (recommended):"
echo "   wget https://nvidia.box.com/shared/static/mp164asf3sceb570wvjsrezk1p4ftj8t.whl -O torch-2.0.0+nv23.05-cp38-cp38-linux_aarch64.whl"
echo "   pip3 install torch-2.0.0+nv23.05-cp38-cp38-linux_aarch64.whl"
echo ""
echo "2. Or visit: https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048"
echo ""
echo "3. After installation, verify with:"
echo "   python3 -c 'import torch; print(torch.cuda.is_available())'"
echo ""
echo "For more help, see: https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/"
echo ""

exit 1