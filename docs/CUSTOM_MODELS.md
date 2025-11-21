# Custom Model Configuration Guide

## Overview

ThermalFusionDrivingAssist v3.x supports custom YOLO models for specialized detection scenarios. You can configure custom models for:
- Thermal-optimized detection (e.g., FLIR-COCO trained models)
- RGB-optimized detection (higher quality or performance variants)
- Domain-specific models (wildlife detection, industrial scenarios, etc.)

## Configuration Method

### 1. Via config.json

Edit your `config.json` file to add custom model paths:

```json
{
  "yolo_model": "yolov8s.pt",
  "model_presets": {
    "yolov8n": "yolov8n.pt",
    "yolov8s": "yolov8s.pt",
    "yolov8m": "yolov8m.pt",
    "yolov8l": "yolov8l.pt"
  },
  "thermal_model": "models/thermal_flir_coco.pt",
  "rgb_model": "models/rgb_high_quality.pt",
  "custom_models": [
    "models/wildlife_detector.pt",
    "models/industrial_safety.pt",
    "/absolute/path/to/custom_model.pt"
  ]
}
```

### 2. Model Selection

**Standard Presets** (cycle with Model button):
- **YOLOv8n** - Nano variant (fastest, ~6ms inference on Jetson Orin)
- **YOLOv8s** - Small variant (balanced, ~10ms inference)
- **YOLOv8m** - Medium variant (higher accuracy, ~18ms inference)
- **YOLOv8l** - Large variant (highest accuracy, ~30ms inference)

**Custom Models** (automatically added to cycle):
- Any models listed in `custom_models` array
- Dedicated thermal model (if `thermal_model` is set)
- Dedicated RGB model (if `rgb_model` is set)

### 3. Developer Mode Controls

Press **Ctrl+D** to show developer controls:
- **🤖 Model** button: Cycles through all available models (presets + custom)
- Model name displayed on button (e.g., "MDL: V8N", "MDL: CUSTOM")

### 4. Model Cycling Order

The Model button cycles in this order:
1. YOLOv8n (preset)
2. YOLOv8s (preset)
3. YOLOv8m (preset)
4. YOLOv8l (preset)
5. Custom model 1 (if configured)
6. Custom model 2 (if configured)
7. ... (back to YOLOv8n)

## Custom Model Requirements

### Model Format
- **Supported**: `.pt` (PyTorch), `.engine` (TensorRT)
- **Framework**: YOLOv8 from Ultralytics
- **Classes**: COCO-compatible (80 classes) recommended

### Model Training

If you want to train a custom model:

```bash
# Install ultralytics
pip install ultralytics

# Train on custom dataset
yolo detect train data=thermal_dataset.yaml model=yolov8s.pt epochs=100

# Export for Jetson (optional TensorRT optimization)
yolo export model=runs/detect/train/weights/best.pt format=engine device=0
```

### Thermal-Specific Models

For thermal camera optimization:

**FLIR-COCO Dataset**: Pre-trained models available at:
- [FLIR Thermal Dataset](https://www.flir.com/oem/adas/adas-dataset-form/)
- Trained on 14,000+ thermal images
- Better performance for thermal-only detection

**Custom Thermal Training**:
```bash
# Download FLIR dataset
# Train YOLOv8 on thermal images
yolo detect train data=flir_coco.yaml model=yolov8m.pt epochs=200 imgsz=640

# Add to config.json
"thermal_model": "models/yolov8m_flir_coco.pt"
```

## Model Selection Strategy

### For RGB Camera:
- **Daylight, High Speed**: yolov8n.pt (fastest)
- **General Use**: yolov8s.pt (default)
- **High Accuracy Needed**: yolov8m.pt or yolov8l.pt

### For Thermal Camera:
- **Standard Detection**: yolov8s.pt (COCO trained)
- **Thermal Optimized**: FLIR-COCO trained model
- **Wildlife/Night**: Custom thermal-trained model

### Performance vs Accuracy Trade-off:

| Model      | Inference Time (Jetson Orin) | mAP@50 | Best For                    |
|------------|------------------------------|--------|-----------------------------|
| YOLOv8n    | ~6ms                         | 37.3   | High FPS, basic detection   |
| YOLOv8s    | ~10ms                        | 44.9   | Balanced (recommended)      |
| YOLOv8m    | ~18ms                        | 50.2   | Accuracy priority           |
| YOLOv8l    | ~30ms                        | 52.9   | Maximum accuracy            |
| FLIR-COCO  | ~10-18ms                     | ~48*   | Thermal-specific detection  |

*FLIR-COCO performance depends on base model used (s/m)

## Runtime Model Switching

### Current Limitation:
- Model changes require detector reload (app restart)
- Switching models at runtime will be implemented in future versions

### Workaround:
1. Set desired model in config.json
2. Restart application: `python3 main.py`
3. Model will be loaded on startup

### Future Enhancement:
Hot-swappable models (reload detector without app restart) is planned for v3.5.

## Examples

### Example 1: Wildlife Detection Setup

```json
{
  "yolo_model": "models/wildlife_thermal.pt",
  "custom_models": [
    "models/wildlife_thermal.pt",
    "models/wildlife_rgb.pt"
  ]
}
```

### Example 2: Industrial Safety

```json
{
  "yolo_model": "yolov8m.pt",
  "custom_models": [
    "models/ppe_detector.pt",
    "models/hazard_detection.pt"
  ]
}
```

### Example 3: Thermal + RGB Specialized

```json
{
  "yolo_model": "yolov8s.pt",
  "thermal_model": "models/flir_coco_yolov8m.pt",
  "rgb_model": "models/rgb_yolov8l.pt",
  "custom_models": []
}
```

## Troubleshooting

### Model Not Loading
- Check file path is correct (absolute or relative to project root)
- Verify model file exists: `ls -la models/your_model.pt`
- Check model format is compatible (YOLOv8 .pt or .engine)

### Poor Performance
- Try smaller model variant (n instead of l)
- Enable TensorRT optimization (automatic on Jetson)
- Reduce confidence threshold in config

### Custom Model Not Appearing
- Ensure model is added to `custom_models` array in config.json
- Restart application to reload config
- Check logs for model loading errors

## References

- [Ultralytics YOLOv8 Documentation](https://docs.ultralytics.com/)
- [FLIR Thermal Dataset](https://www.flir.com/oem/adas/adas-dataset-form/)
- [TensorRT Optimization Guide](https://docs.nvidia.com/deeplearning/tensorrt/)
