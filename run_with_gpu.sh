#!/bin/bash
# Wrapper script to run the application with proper CUDA/cuDNN library paths

# Add CUDA libraries to path
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH

# Create temporary symlinks for cuDNN if needed
TEMP_LIB_DIR="/tmp/cuda_compat_libs"
mkdir -p "$TEMP_LIB_DIR"

# Create cuDNN 8 symlinks pointing to cuDNN 9
if [ ! -f "$TEMP_LIB_DIR/libcudnn.so.8" ]; then
    ln -sf /usr/lib/aarch64-linux-gnu/libcudnn.so.9 "$TEMP_LIB_DIR/libcudnn.so.8"
    ln -sf /usr/lib/aarch64-linux-gnu/libcudnn_ops_infer.so.9 "$TEMP_LIB_DIR/libcudnn_ops_infer.so.8" 2>/dev/null || true
    ln -sf /usr/lib/aarch64-linux-gnu/libcudnn_cnn_infer.so.9 "$TEMP_LIB_DIR/libcudnn_cnn_infer.so.8" 2>/dev/null || true
fi

# Add compatibility libs to path
export LD_LIBRARY_PATH="$TEMP_LIB_DIR:$LD_LIBRARY_PATH"

echo "=================================="
echo "CUDA Environment:"
echo "  CUDA_HOME: ${CUDA_HOME:-/usr/local/cuda}"
echo "  LD_LIBRARY_PATH: $LD_LIBRARY_PATH"
echo "=================================="

# Run the application with all arguments passed through
python3 main.py "$@"