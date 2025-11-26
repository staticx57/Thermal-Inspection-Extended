# Jetson Orin GPU Setup Guide

Your Jetson Orin is detected but **GPU acceleration is currently NOT working** because PyTorch was installed without CUDA support.

## Current Status

```
Platform: Jetson Orin (R36 - JetPack 6.x)
PyTorch: 2.0.1 (CPU-only build)
CUDA: Not available to PyTorch
```

## Why This Matters

- **Without GPU**: 1-5 FPS (unusable for real-time detection)
- **With GPU + TensorRT**: 30-120 FPS (smooth, responsive)

## Fix GPU Acceleration

### Option 1: Install PyTorch for Jetson (Recommended)

For **JetPack 6.x**, install the official NVIDIA PyTorch build:

```bash
# Check your Python version
python3 --version

# For Python 3.10 (JetPack 6.x)
wget https://developer.download.nvidia.com/compute/redist/jp/v60/pytorch/torch-2.1.0a0+41361538.nv23.06-cp310-cp310-linux_aarch64.whl

pip3 install torch-2.1.0a0+41361538.nv23.06-cp310-cp310-linux_aarch64.whl

# Install torchvision
sudo apt-get install libjpeg-dev zlib1g-dev libpython3-dev libopenblas-dev libavcodec-dev libavformat-dev libswscale-dev
pip3 install torchvision==0.16.0
```

### Option 2: Use PyTorch NGC Container

```bash
# Pull NVIDIA's container with PyTorch + CUDA
sudo docker pull nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3

# Run the application in container
sudo docker run --runtime nvidia -it --rm --network host \
    --device /dev/video0 --device /dev/video1 \
    -v /home/michael/Desktop/thermal\ only:/app \
    nvcr.io/nvidia/l4t-pytorch:r36.2.0-pth2.1-py3 \
    bash -c "cd /app && pip install ultralytics && python3 main.py"
```

### Verify Installation

After installing PyTorch, verify CUDA works:

```bash
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python3 -c "import torch; print(f'Device: {torch.cuda.get_device_name(0)}')"
```

You should see:
```
CUDA available: True
Device: Orin
```

## Resources

- **PyTorch for Jetson**: https://forums.developer.nvidia.com/t/pytorch-for-jetson/72048
- **JetPack 6 Documentation**: https://docs.nvidia.com/jetson/jetpack/
- **NVIDIA PyTorch Container**: https://catalog.ngc.nvidia.com/orgs/nvidia/containers/l4t-pytorch

## Run After GPU is Fixed

Once GPU is working:

```bash
# Quick test
./setup_jetson_gpu.sh

# Run application with auto-detection
python3 main.py

# Or specify camera manually
python3 main.py --camera-id 0
```

## Performance Expectations

With proper GPU acceleration on Jetson Orin:

- **Orin Nano (8GB)**: 30-50 FPS with yolov8n
- **Orin NX (16GB)**: 50-80 FPS with yolov8n
- **Orin AGX (64GB)**: 80-120 FPS with yolov8n

## Troubleshooting

### "CUDA NOT AVAILABLE" Error

The application will **refuse to run** without GPU acceleration to prevent unusable performance. Fix GPU first.

### CUDA Libraries Not Found

```bash
# Add CUDA to path
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### TensorRT Export Fails

If TensorRT conversion fails, the application will fall back to standard PyTorch GPU mode (still fast, ~20-40 FPS).

To force TensorRT:
```bash
python3 main.py --use-tensorrt
```

To skip TensorRT:
```bash
python3 main.py --no-tensorrt
```