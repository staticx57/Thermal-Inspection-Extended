#!/bin/bash
# Setup script for GPU acceleration on Jetson Orin

echo "========================================"
echo "Jetson Orin GPU Setup for Thermal Inspection Fusion Tool"
echo "(PyTorch is OPTIONAL: it only accelerates fusion/3D and enables ML depth for parallax)"
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
        echo "Your system is ready for GPU-accelerated fusion in the Thermal Inspection Fusion Tool!"
        exit 0
    fi
fi

echo "✗ CUDA is NOT working with PyTorch"
echo ""
echo "PyTorch is optional: without it the app falls back to the CPU (OpenCV/NumPy) paths."
echo "For GPU acceleration install NVIDIA's PyTorch build that matches your JetPack AND your Python"
echo "(this project needs Python 3.10 or newer - check with: python3 --version):"
echo ""
echo "  https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/"
echo "  https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048"
echo ""
echo "Do NOT pip-install the generic PyPI torch wheel on a Jetson: it is CPU-only (or the wrong CUDA)."
echo "After installing, verify with:"
echo "   python3 -c 'import torch; print(torch.cuda.is_available())'"
echo ""

exit 1
