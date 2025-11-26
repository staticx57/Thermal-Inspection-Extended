# Software Parallax Compensation Plan

## Problem Statement

The thermal camera (FLIR Boson) and RGB camera (Firefly) are physically separated, creating parallax - a difference in the apparent position of objects when viewed from different positions. While optical alignment can minimize this, it cannot fully eliminate parallax due to the physical separation between camera sensors.

**Key Challenge**: Objects at different distances from the camera rig will have different amounts of displacement between thermal and RGB views.

---

## Parallax Fundamentals

### What Causes Parallax?

```
        Thermal Camera          RGB Camera
              |                      |
              |                      |
         [Baseline Distance B]
              |                      |
              v                      v
         =========================
              Near Object
         =========================

         =========================
              Far Object
         =========================
```

- **Baseline (B)**: Physical distance between camera centers
- **Near objects**: Large displacement between thermal/RGB views
- **Far objects**: Small displacement between thermal/RGB views
- **At infinity**: Zero displacement (cameras are parallel)

### Parallax Formula

```
Disparity (pixels) = (Baseline × Focal_Length) / Distance_to_Object
```

For a fixed baseline and focal length, disparity is **inversely proportional** to object distance.

---

## Current System Characteristics

### Camera Setup
- **Thermal**: FLIR Boson 640x512 (640×512 resolution)
- **RGB**: Firefly FFY-U3-16S2C-DL (1440×1080 max resolution)
- **Baseline**: TBD (measure physical separation between camera centers)
- **Field of View (FoV)**: Different for thermal vs RGB
- **Mounting**: Side-by-side or vertical configuration (TBD)

### Existing Calibration
- **File**: Calibration file support already exists (`calibration_file` parameter)
- **Fusion Processor**: Already has transformation support
- **Current Method**: Static transformation matrix (doesn't account for depth-varying parallax)

---

## Compensation Strategy Overview

### Multi-Level Approach

1. **Level 1: Calibration Matrix** (Already Implemented)
   - Static homography for best-fit alignment at a reference distance
   - Works well for objects at the calibration distance
   - Fails for objects significantly closer or farther

2. **Level 2: Depth-Based Correction** (NEW - Recommended)
   - Estimate depth of each pixel/region
   - Apply distance-dependent transformation
   - Most accurate compensation

3. **Level 3: Stereo Reconstruction** (ADVANCED - Optional)
   - Full 3D reconstruction using stereo vision
   - Most computationally expensive
   - Provides complete 3D thermal map

---

## Recommended Implementation: Depth-Based Correction

### Overview

Use depth estimation to compute parallax correction on a per-pixel or per-region basis, then warp the thermal image to align with RGB.

### Pipeline

```
RGB Frame → Depth Estimation → Parallax Map → Thermal Warping → Aligned Fusion
Thermal Frame ────────────────────────────────────────┘
```

### Step-by-Step Implementation

#### **Step 1: Depth Estimation**

**Option A: Monocular Depth Estimation (Simpler)**
- Use pre-trained neural network (MiDaS, DPT, or DepthAnything)
- Input: RGB frame
- Output: Relative depth map (same resolution as RGB)
- **Pros**: No additional hardware, fast inference on GPU
- **Cons**: Relative depth only (not metric), may be noisy

**Option B: Stereo Depth (If adding second RGB camera)**
- Use two RGB cameras in stereo configuration
- Compute disparity using block matching or SGM
- Convert disparity to depth using camera parameters
- **Pros**: Metric depth, more accurate
- **Cons**: Requires additional camera, calibration, compute

**Recommended**: Start with **Option A** using MiDaS or DepthAnything for rapid prototyping.

#### **Step 2: Compute Parallax Map**

For each pixel `(x, y)` in the depth map:

```python
# Given:
# - depth[y, x]: estimated depth at pixel (x, y)
# - baseline: physical separation between cameras (meters)
# - focal_length_thermal: thermal camera focal length (pixels)

disparity_x = (baseline * focal_length_thermal) / depth[y, x]
```

This gives the horizontal shift (in pixels) needed to align that pixel.

#### **Step 3: Warp Thermal Image**

Use the parallax map to create a dense flow field, then warp thermal image:

```python
# Create flow field
flow_x = disparity_map  # Horizontal shift
flow_y = np.zeros_like(flow_x)  # No vertical shift (assuming horizontal baseline)

# Warp thermal image using cv2.remap
thermal_aligned = cv2.remap(thermal_frame,
                             x_coords + flow_x,
                             y_coords + flow_y,
                             interpolation=cv2.INTER_LINEAR)
```

#### **Step 4: Integrate with Fusion Processor**

Modify `fusion_processor.py` to:
1. Run depth estimation on RGB frame (cache for performance)
2. Compute parallax correction map
3. Apply warping to thermal frame before fusion
4. Proceed with existing fusion algorithms

---

## Implementation Phases

### Phase 1: Baseline Measurement & Calibration (Week 1)
**Goal**: Measure system parameters

**Tasks**:
- Measure physical baseline distance between camera centers
- Measure/calculate thermal camera focal length
- Create initial stereo calibration between thermal and RGB
- Capture calibration dataset (checkerboard at multiple distances)

**Deliverables**:
- `camera_baseline.json` with physical parameters
- Stereo calibration matrices
- Test images at 1m, 2m, 5m, 10m distances

### Phase 2: Depth Estimation Integration (Week 2)
**Goal**: Add monocular depth estimation

**Tasks**:
- Integrate MiDaS or DepthAnything model
- Create `DepthEstimator` class in new file `depth_estimator.py`
- Add GPU acceleration support
- Benchmark inference speed (target: >20 FPS on CUDA)

**Deliverables**:
- `depth_estimator.py` module
- Depth map visualization in GUI
- Performance benchmark report

### Phase 3: Parallax Compensation Module (Week 3)
**Goal**: Implement depth-based warping

**Tasks**:
- Create `ParallaxCompensator` class in `parallax_compensator.py`
- Implement disparity-to-flow conversion
- Implement thermal image warping with caching
- Add compensation quality metrics (alignment error)

**Deliverables**:
- `parallax_compensator.py` module
- Unit tests with synthetic data
- Visual comparison: before/after compensation

### Phase 4: Integration & Optimization (Week 4)
**Goal**: Integrate into main application

**Tasks**:
- Modify `FusionProcessor` to use parallax compensation
- Add GUI toggle: "Parallax Compensation ON/OFF"
- Optimize for real-time performance
- Add option to cache depth maps (update every N frames)

**Deliverables**:
- Updated `fusion_processor.py`
- GUI controls for compensation
- Performance tuning results

### Phase 5: Validation & Tuning (Week 5)
**Goal**: Test and validate

**Tasks**:
- Test with real-world scenes at various distances
- Measure alignment accuracy improvement
- Fine-tune parameters (depth smoothing, interpolation method)
- Document best practices

**Deliverables**:
- Validation report with metrics
- Parameter tuning guide
- User documentation

---

## Technical Specifications

### Depth Estimation Models

| Model | Resolution | Speed (GPU) | Accuracy | License |
|-------|-----------|-------------|----------|---------|
| MiDaS v3 | 384×384 | ~30 FPS | Good | MIT |
| DPT-Large | 384×384 | ~20 FPS | Better | MIT |
| DepthAnything | 518×518 | ~40 FPS | Best | Apache 2.0 |

**Recommendation**: **DepthAnything** - Latest, fastest, most accurate, permissive license.

### Parallax Compensation Algorithm

```python
class ParallaxCompensator:
    def __init__(self, baseline_m, focal_length_thermal_px, depth_estimator):
        """
        Args:
            baseline_m: Camera baseline in meters
            focal_length_thermal_px: Thermal camera focal length in pixels
            depth_estimator: DepthEstimator instance
        """
        self.baseline = baseline_m
        self.focal_length = focal_length_thermal_px
        self.depth_estimator = depth_estimator

    def compensate(self, thermal_frame, rgb_frame):
        """
        Apply parallax compensation to thermal frame

        Args:
            thermal_frame: (H, W) thermal image
            rgb_frame: (H, W, 3) RGB image

        Returns:
            compensated_thermal: (H, W) aligned thermal image
        """
        # 1. Estimate depth from RGB
        depth_map = self.depth_estimator.predict(rgb_frame)

        # 2. Resize depth to thermal resolution
        depth_thermal = cv2.resize(depth_map, (thermal_frame.shape[1], thermal_frame.shape[0]))

        # 3. Compute disparity (parallax shift)
        # Avoid division by zero
        disparity = np.divide(self.baseline * self.focal_length,
                            depth_thermal,
                            out=np.zeros_like(depth_thermal),
                            where=depth_thermal > 0.1)

        # 4. Create flow field
        h, w = thermal_frame.shape
        x_coords, y_coords = np.meshgrid(np.arange(w), np.arange(h))

        # Apply horizontal shift (assuming horizontal baseline)
        x_coords_shifted = x_coords + disparity

        # 5. Warp thermal image
        compensated = cv2.remap(thermal_frame,
                               x_coords_shifted.astype(np.float32),
                               y_coords.astype(np.float32),
                               interpolation=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)

        return compensated
```

---

## Performance Considerations

### Computational Cost

**Depth Estimation**: ~10-30ms per frame (GPU)
**Parallax Computation**: ~1-2ms per frame
**Warping**: ~2-3ms per frame

**Total Overhead**: ~15-35ms per frame
**Target Frame Rate**: 20-30 FPS (achievable with GPU)

### Optimization Strategies

1. **Depth Map Caching**
   - Update depth every 5-10 frames (scene doesn't change rapidly)
   - Reduces average overhead to ~2-5ms per frame

2. **Resolution Downsampling**
   - Run depth estimation at lower resolution (e.g., 320×240)
   - Upsample depth map to thermal resolution
   - Trades accuracy for speed

3. **GPU Acceleration**
   - Use CUDA for depth estimation (already available via `device='cuda'`)
   - Use GPU-based warping with PyTorch or cv2.cuda

4. **Model Quantization**
   - Use INT8 or FP16 quantized depth models
   - 2-3× speedup with minimal accuracy loss

---

## Alternative Approaches

### Approach 1: Feature-Based Alignment (Lightweight)
- Detect keypoints in both thermal and RGB (SIFT, ORB)
- Match features and compute homography per region
- **Pros**: No ML model needed, fast
- **Cons**: Fails in low-texture scenes, less accurate

### Approach 2: Optical Flow Tracking (Dynamic Scenes)
- Track motion between frames using optical flow
- Estimate relative depth from motion parallax
- **Pros**: Works well for moving camera/objects
- **Cons**: Requires motion, accumulates error

### Approach 3: Structured Light / ToF Sensor (Hardware)
- Add dedicated depth sensor (e.g., Intel RealSense, ToF camera)
- Get accurate metric depth
- **Pros**: Most accurate, metric depth
- **Cons**: Additional hardware cost, power consumption

---

## Validation Metrics

### Alignment Error
- Measure pixel displacement between corresponding points in thermal/RGB
- **Target**: < 5 pixels average error at calibration distance

### Feature Registration Accuracy
- Use SIFT/ORB to match features before/after compensation
- Measure increase in correct matches
- **Target**: > 80% correct matches after compensation

### Visual Inspection
- Overlay thermal on RGB before/after compensation
- Check edge alignment (buildings, objects)
- Create comparison videos

---

## File Structure

```
Thermal-Inspection/
├── depth_estimator.py          # Depth estimation module (NEW)
├── parallax_compensator.py     # Parallax compensation (NEW)
├── fusion_processor.py         # Modified to use compensation
├── calibration/
│   ├── camera_baseline.json    # Physical parameters (NEW)
│   ├── stereo_calib.npz        # Stereo calibration (NEW)
│   └── depth_model.pth         # Pre-trained depth model (NEW)
├── tests/
│   ├── test_depth_estimator.py
│   └── test_parallax_compensator.py
└── docs/
    ├── PARALLAX_COMPENSATION_PLAN.md (this file)
    └── PARALLAX_CALIBRATION_GUIDE.md (NEW)
```

---

## Dependencies

### New Python Packages
```bash
pip install timm  # For DepthAnything model
pip install einops  # Tensor operations
```

### Model Download
```python
# Download DepthAnything model
from huggingface_hub import hf_hub_download

model_path = hf_hub_download(
    repo_id="LiheYoung/depth-anything-base",
    filename="depth_anything_vitb14.pth"
)
```

---

## GUI Integration

### Control Panel Additions

**New Section in Settings Tab**: "Parallax Compensation"

- **[Checkbox]** Enable Parallax Compensation
- **[Slider]** Depth Update Frequency (1-30 frames)
- **[Button]** Recalibrate Baseline
- **[Label]** Current Baseline: 0.15m
- **[Label]** Compensation Status: Active / Inactive

**New Visualization**: "Depth Map" view mode
- Show estimated depth map from RGB camera
- Color-coded: Red (near) → Blue (far)

---

## Expected Results

### Before Compensation
- Objects at different distances show misalignment
- Close objects: Large offset between thermal/RGB
- Far objects: Small offset
- Fusion quality degrades with distance variation

### After Compensation
- Improved alignment across all depths
- Reduced ghosting in fused images
- Better MSX (Multi-Spectral Dynamic Imaging) quality
- More accurate ROI tracking

### Quantitative Improvement
- **Alignment Error**: 15-20 pixels → 3-5 pixels
- **Feature Match Rate**: 40% → 85%
- **User-Reported Quality**: Subjective improvement in fusion clarity

---

## Risks & Mitigation

### Risk 1: Depth Estimation Inaccuracy
- **Impact**: Incorrect parallax correction, worse than no correction
- **Mitigation**:
  - Validate depth estimation on known-distance objects
  - Add confidence threshold (only correct high-confidence regions)
  - Provide manual baseline adjustment

### Risk 2: Performance Degradation
- **Impact**: Frame rate drops below acceptable level
- **Mitigation**:
  - Implement depth caching (update every N frames)
  - Use model quantization
  - Make compensation optional (user toggle)

### Risk 3: Model Availability
- **Impact**: Pre-trained models not available or licensed improperly
- **Mitigation**:
  - Use Apache 2.0 or MIT licensed models only
  - Keep local copies of models
  - Document model sources

---

## Future Enhancements

### Enhancement 1: Adaptive Baseline
- Auto-adjust virtual baseline based on scene depth
- Optimize for dominant depth range

### Enhancement 2: Multi-Distance Calibration
- Store calibration matrices for multiple distance ranges
- Blend corrections based on depth

### Enhancement 3: Real-Time 3D Reconstruction
- Build 3D thermal map in real-time
- Enable novel view synthesis
- Support augmented reality overlays

### Enhancement 4: Machine Learning Optimization
- Train custom depth model on thermal + RGB pairs
- Learn optimal parallax correction end-to-end
- Potentially eliminate explicit depth estimation

---

## Summary

This plan provides a **pragmatic, phased approach** to software-based parallax compensation:

1. **Start simple**: Monocular depth estimation (MiDaS/DepthAnything)
2. **Compute parallax**: Use depth + baseline to calculate pixel shifts
3. **Warp thermal**: Align thermal image to RGB view
4. **Integrate**: Add to fusion processor with GPU acceleration
5. **Optimize**: Cache depth maps, tune parameters

**Expected Timeline**: 5 weeks from baseline measurement to production-ready implementation

**Success Criteria**:
- < 5 pixel alignment error at calibration distance
- > 20 FPS with compensation enabled
- User-visible improvement in fusion quality

---

## Next Steps

1. **Measure baseline distance** between Boson and Firefly cameras
2. **Choose depth estimation model** (recommend DepthAnything)
3. **Create `depth_estimator.py`** module with model integration
4. **Implement `ParallaxCompensator`** class
5. **Test with sample frames** and measure improvement

**Questions to Address**:
- What is the current camera mounting configuration (side-by-side or vertical)?
- What are the target use cases (inspection distance range)?
- What is the acceptable performance overhead?

---

**Document Version**: 1.0
**Date**: 2025-11-25
**Author**: Claude (Anthropic)
**Status**: Draft - Ready for Review
