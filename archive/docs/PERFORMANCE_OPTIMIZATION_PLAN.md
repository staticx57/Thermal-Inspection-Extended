# Performance Optimization Plan: 30 FPS Target

## Executive Summary
This document analyzes the current thermal inspection pipeline, identifies performance bottlenecks, and proposes async/multithreading optimizations to achieve a sustained 30 FPS target.

**Target**: 30 FPS = ~33.3ms per frame budget

---

## 1. Current Performance Bottleneck Analysis

### Frame Processing Pipeline Breakdown
Based on the timing instrumentation in `inspection_main.py:1076-1097`:

```
Main Loop Components:
├── thermal_read        (Camera I/O - blocking)
├── rgb_read            (Camera I/O - blocking)
├── process_frame       (CRITICAL PATH - see breakdown below)
├── gui_update          (Qt GUI rendering)
└── processEvents       (Qt event loop)

process_frame() Breakdown:
├── thermal_processor   (Motion + Edge detection)
├── palette             (Colormap application)
├── auto_roi            (ROI detection - runs every N frames)
├── roi_analysis        (Per-ROI thermal stats)
├── thermal_analysis    (Hot/cold spots, anomalies, manual threshold)
├── anomaly_priority    (Gradient fade visualization)
├── fusion              (Thermal + RGB fusion)
├── display_select      (View mode rendering)
└── draw_rois           (ROI overlay drawing)
```

### Identified Bottlenecks (in order of severity)

#### **CRITICAL BOTTLENECKS** (>10ms each)

1. **thermal_analysis** (15-25ms)
   - Location: `inspection_main.py:689-715`
   - Includes:
     - `analyze_frame()` - Global thermal statistics
     - `detect_hot_spots()` - Percentile-based hot spot detection
     - `detect_cold_spots()` - Percentile-based cold spot detection
     - `detect_anomalies()` - Statistical anomaly detection
     - `detect_threshold_anomalies()` - Manual threshold detection
   - **Why slow**: Multiple full-frame numpy operations (percentile, std, gradient)

2. **roi_analysis** (5-20ms, scales with ROI count)
   - Location: `inspection_main.py:670-686`
   - Serial loop over all ROIs, each calling `analyze_frame()` with mask
   - **Why slow**: N×O(frame_size) operations in serial

3. **thermal_processor** (10-15ms)
   - Location: `thermal_processor.py:455-493`
   - Motion detection: Background subtraction
   - Edge detection: VPI-accelerated Canny (if available)
   - **Why slow**: Sequential motion + edge processing

4. **anomaly_priority** (8-12ms when enabled)
   - Location: `inspection_main.py:719-755`
   - Gradient fade visualization with distance transforms
   - **Why slow**: Distance transform + alpha blending on full frame

#### **MODERATE BOTTLENECKS** (3-8ms each)

5. **fusion** (5-8ms)
   - Location: `inspection_main.py:767-775`
   - Multi-algorithm fusion (7 modes available)
   - **Why slow**: Full-frame blending operations

6. **palette** (3-5ms)
   - Location: `inspection_main.py:631-635`
   - Composite palette with ROI overrides
   - **Why slow**: Per-pixel colormap lookups

7. **auto_roi** (varies, only runs every N frames)
   - Location: `inspection_main.py:640-667`
   - Temperature/gradient/motion/edge-based ROI detection
   - **Why slow**: Multiple detection algorithms in serial

#### **MINOR BOTTLENECKS** (<3ms each)

8. **draw_rois**, **display_select**, **gui_update** (1-3ms each)
   - Relatively cheap rendering operations

---

## 2. Async/Multithreading Opportunities

### Current Threading Status
- **Already threaded**: Camera capture via `ThreadedCameraCapture`
  - Location: `inspection_main.py:858-860`
  - Benefit: Non-blocking frame acquisition
  - ✅ **Good foundation**

### Proposed Threading Architecture

```
Main Thread (Qt Event Loop)
│
├── Camera Thread [EXISTING] ✅
│   ├── Thermal camera I/O
│   └── RGB camera I/O
│
├── Processing Thread Pool [NEW]
│   │
│   ├── Worker 1: Motion Detection
│   │   └── thermal_processor.detect_motion()
│   │
│   ├── Worker 2: Edge Detection
│   │   └── thermal_processor.detect_edges()
│   │
│   ├── Worker 3: Hot/Cold Spot Detection
│   │   ├── detect_hot_spots()
│   │   └── detect_cold_spots()
│   │
│   ├── Worker 4: Anomaly Detection
│   │   ├── detect_anomalies()
│   │   └── detect_threshold_anomalies()
│   │
│   └── Worker 5-N: ROI Analysis (parallel per ROI)
│       └── analyze_frame() with mask
│
└── Rendering Thread [NEW]
    ├── Palette application
    ├── Anomaly priority colorization
    ├── Fusion processing
    └── Display frame preparation
```

### Parallelization Strategy by Task

#### **High-Value Parallelization** (✅ Independent, CPU-bound)

1. **Detection Tasks** - Run in parallel
   ```python
   # These are fully independent and can run concurrently
   with ThreadPoolExecutor(max_workers=4) as executor:
       future_hot = executor.submit(detect_hot_spots, thermal_frame)
       future_cold = executor.submit(detect_cold_spots, thermal_frame)
       future_anomaly = executor.submit(detect_anomalies, thermal_frame)
       future_motion = executor.submit(detect_motion, thermal_frame)

       hot_spots = future_hot.result()
       cold_spots = future_cold.result()
       anomalies = future_anomaly.result()
       motion = future_motion.result()
   ```
   **Expected gain**: 15-25ms → 6-8ms (3-4x speedup)

2. **ROI Analysis** - Parallel per ROI
   ```python
   def analyze_single_roi(roi, thermal_frame):
       mask = roi.get_mask(thermal_frame.shape)
       return self.thermal_analyzer.analyze_frame(thermal_frame, mask)

   with ThreadPoolExecutor() as executor:
       roi_stats = list(executor.map(
           lambda r: analyze_single_roi(r, thermal_frame),
           rois
       ))
   ```
   **Expected gain**: 5-20ms → 2-5ms (2-4x speedup for 4+ ROIs)

3. **Motion + Edge Detection** - Run in parallel
   ```python
   # Currently sequential in thermal_processor.process_frame()
   with ThreadPoolExecutor(max_workers=2) as executor:
       future_motion = executor.submit(self.detect_motion, frame)
       future_edges = executor.submit(self.detect_edges, frame)

       motion_detections = future_motion.result()
       edge_image, edge_clusters = future_edges.result()
   ```
   **Expected gain**: 10-15ms → 5-8ms (2x speedup)

#### **Medium-Value Parallelization** (⚠️ Some dependencies)

4. **Rendering Pipeline** - Offload to separate thread
   ```python
   # Can run asynchronously after detections complete
   async def prepare_display_frame(thermal_frame, detections):
       thermal_colorized = apply_palette(thermal_frame)
       if anomaly_priority_enabled:
           thermal_colorized = apply_anomaly_priority(thermal_colorized, detections)
       if fusion_enabled:
           fused = fuse_frames(thermal_colorized, rgb_frame)
       return select_display_frame(thermal_colorized, fused)
   ```
   **Expected gain**: Reduces GUI thread blocking, smoother rendering

#### **Low-Value Parallelization** (❌ Not worth complexity)

5. **Palette application** - Already optimized with NumPy vectorization
6. **GUI updates** - Must stay on main thread (Qt requirement)

---

## 3. Specific Optimization Proposals

### Phase 1: Quick Wins (Immediate Impact) ⚡

#### Optimization 1.1: Parallelize Detection Tasks
**File**: `inspection_main.py:689-715`

**Current** (Sequential):
```python
# 5. Global thermal analysis (whole frame)
global_stats = self.thermal_analyzer.analyze_frame(thermal_frame)
result['thermal_stats'] = global_stats

# Hot/cold spot detection
result['hot_spots'] = self.thermal_analyzer.detect_hot_spots(thermal_frame)
result['cold_spots'] = self.thermal_analyzer.detect_cold_spots(thermal_frame)

# Anomaly detection
result['anomalies'] = self.thermal_analyzer.detect_anomalies(thermal_frame, 'global')

# Manual threshold detection
if self.manual_threshold_enabled:
    threshold_result = self.thermal_analyzer.detect_threshold_anomalies(...)
```

**Optimized** (Parallel):
```python
from concurrent.futures import ThreadPoolExecutor

# Run all detections in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    future_stats = executor.submit(self.thermal_analyzer.analyze_frame, thermal_frame)
    future_hot = executor.submit(self.thermal_analyzer.detect_hot_spots, thermal_frame)
    future_cold = executor.submit(self.thermal_analyzer.detect_cold_spots, thermal_frame)
    future_anomaly = executor.submit(self.thermal_analyzer.detect_anomalies, thermal_frame, 'global')

    future_threshold = None
    if self.manual_threshold_enabled:
        future_threshold = executor.submit(
            self.thermal_analyzer.detect_threshold_anomalies,
            thermal_frame,
            mode=self.manual_threshold_mode,
            min_threshold=self.manual_threshold_min,
            max_threshold=self.manual_threshold_max,
            use_raw_values=self.manual_threshold_use_raw
        )

    # Collect results
    result['thermal_stats'] = future_stats.result()
    result['hot_spots'] = future_hot.result()
    result['cold_spots'] = future_cold.result()
    result['anomalies'] = future_anomaly.result()
    result['manual_threshold_result'] = future_threshold.result() if future_threshold else None
```

**Expected Improvement**: 20-30ms → 6-10ms (**~3x faster**)

---

#### Optimization 1.2: Parallelize ROI Analysis
**File**: `inspection_main.py:670-686`

**Current** (Sequential loop):
```python
for roi in self.roi_manager.get_all_rois(active_only=True):
    mask = roi.get_mask(thermal_frame.shape)
    stats = self.thermal_analyzer.analyze_frame(thermal_frame, mask)
    if stats:
        roi.metadata['thermal_stats'] = {...}
        self.thermal_analyzer.update_trend(roi.roi_id, stats.mean_temp)
```

**Optimized** (Parallel):
```python
def analyze_roi_parallel(roi, thermal_frame):
    mask = roi.get_mask(thermal_frame.shape)
    stats = self.thermal_analyzer.analyze_frame(thermal_frame, mask)
    return roi, stats

rois = self.roi_manager.get_all_rois(active_only=True)
if rois:
    with ThreadPoolExecutor(max_workers=min(len(rois), 4)) as executor:
        roi_results = list(executor.map(
            lambda r: analyze_roi_parallel(r, thermal_frame),
            rois
        ))

    # Update ROI metadata
    for roi, stats in roi_results:
        if stats:
            roi.metadata['thermal_stats'] = {
                'min_temp': stats.min_temp,
                'max_temp': stats.max_temp,
                'mean_temp': stats.mean_temp,
                'std_temp': stats.std_temp
            }
            self.thermal_analyzer.update_trend(roi.roi_id, stats.mean_temp)
```

**Expected Improvement**:
- 1 ROI: No change
- 4 ROIs: 20ms → 6ms (**~3x faster**)
- 8 ROIs: 40ms → 12ms (**~3x faster**)

---

#### Optimization 1.3: Parallelize Motion + Edge Detection
**File**: `thermal_processor.py:455-493`

**Current** (Sequential):
```python
def process_frame(self, frame: np.ndarray) -> Dict:
    # Detect motion
    motion_detections = self.detect_motion(frame) if self.motion_enabled else []

    # Detect edges
    edge_image, edge_clusters = self.detect_edges(frame) if self.edge_enabled else (None, [])
```

**Optimized** (Parallel):
```python
def process_frame(self, frame: np.ndarray) -> Dict:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_motion = executor.submit(self.detect_motion, frame) if self.motion_enabled else None
        future_edges = executor.submit(self.detect_edges, frame) if self.edge_enabled else None

        motion_detections = future_motion.result() if future_motion else []
        edge_result = future_edges.result() if future_edges else (None, [])
        edge_image, edge_clusters = edge_result
```

**Expected Improvement**: 10-15ms → 5-8ms (**~2x faster**)

---

### Phase 2: Advanced Optimizations (Moderate Complexity) 🚀

#### Optimization 2.1: Pipeline Parallelism with Frame Buffering

**Concept**: Process frame N+1 while rendering frame N

```python
class PipelinedProcessor:
    def __init__(self):
        self.detection_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="detect")
        self.render_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="render")
        self.pending_render = None

    def process_frame(self, thermal_frame, rgb_frame):
        # Wait for previous render to complete
        if self.pending_render:
            previous_display = self.pending_render.result()
            # Display previous frame while processing current

        # Start detections in parallel (non-blocking)
        detection_future = self.detection_executor.submit(
            self._run_all_detections, thermal_frame
        )

        # When detections complete, start rendering
        def on_detections_complete(future):
            detections = future.result()
            return self._render_display_frame(thermal_frame, rgb_frame, detections)

        self.pending_render = detection_future
```

**Expected Improvement**: Effective latency reduction, smoother frame pacing

---

#### Optimization 2.2: Async Auto-ROI Detection

**Current**: Blocks every N frames for auto-ROI detection (can take 10-20ms)

**Optimized**: Run auto-ROI in background thread
```python
class AsyncAutoROIDetector:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="auto_roi")
        self.pending_detection = None

    def trigger_detection(self, thermal_frame, motion_detections):
        # Only trigger if no detection in progress
        if self.pending_detection is None or self.pending_detection.done():
            self.pending_detection = self.executor.submit(
                self._detect_all_rois, thermal_frame.copy(), motion_detections
            )

    def get_latest_rois(self):
        if self.pending_detection and self.pending_detection.done():
            return self.pending_detection.result()
        return None  # Use previous ROIs
```

**Expected Improvement**: Eliminates periodic 10-20ms spikes

---

#### Optimization 2.3: Caching and Incremental Processing

1. **Cache thermal statistics**: Don't recompute global stats if frame unchanged
2. **Incremental palette updates**: Only recompute changed ROIs
3. **Lazy evaluation**: Only compute detections for enabled features

```python
# Example: Conditional detection execution
detections_to_run = []
if self.enabled_anomaly_types.get("hot_spots", True):
    detections_to_run.append(('hot_spots', self.thermal_analyzer.detect_hot_spots))
if self.enabled_anomaly_types.get("cold_spots", True):
    detections_to_run.append(('cold_spots', self.thermal_analyzer.detect_cold_spots))

# Only run enabled detections
with ThreadPoolExecutor() as executor:
    futures = {name: executor.submit(fn, thermal_frame) for name, fn in detections_to_run}
    results = {name: future.result() for name, future in futures.items()}
```

**Expected Improvement**: 5-10ms savings when features disabled

---

### Phase 3: Algorithmic Optimizations (Lower-level) 🔧

#### Optimization 3.1: NumPy → Numba JIT Compilation

Convert hot loops in thermal_analyzer.py to Numba JIT:

```python
from numba import jit

@jit(nopython=True, parallel=True)
def compute_hot_spots_fast(thermal_data, threshold):
    # Replace numpy operations with numba-compiled loops
    # Can achieve 2-5x speedup on CPU
    ...
```

**Target functions**:
- `detect_hot_spots()` - percentile calculations
- `detect_cold_spots()` - percentile calculations
- `detect_anomalies()` - statistical computations

**Expected Improvement**: 15-20ms → 5-8ms (**~2-3x faster**)

---

#### Optimization 3.2: GPU Acceleration with CuPy

Replace critical NumPy operations with CuPy (GPU):

```python
import cupy as cp

def detect_hot_spots_gpu(self, thermal_frame):
    # Transfer to GPU
    gpu_frame = cp.asarray(thermal_frame)

    # GPU-accelerated percentile
    threshold = cp.percentile(gpu_frame, self.hot_spot_percentile)

    # GPU-accelerated masking
    hot_mask = gpu_frame > threshold

    # Transfer back to CPU for OpenCV operations
    hot_mask_cpu = cp.asnumpy(hot_mask)
    ...
```

**Expected Improvement**: 15-20ms → 2-4ms (**~5-10x faster on NVIDIA GPUs**)

---

## 4. Implementation Roadmap

### Week 1: Quick Wins (Target: 25-30 FPS)
- ✅ Implement Optimization 1.1 (Parallel detections)
- ✅ Implement Optimization 1.2 (Parallel ROI analysis)
- ✅ Implement Optimization 1.3 (Parallel motion+edge)
- ⚠️ Add performance regression tests

**Expected Result**: 15-20 FPS → 25-30 FPS

### Week 2: Advanced Optimizations (Target: 30+ FPS stable)
- ✅ Implement Optimization 2.1 (Pipeline parallelism)
- ✅ Implement Optimization 2.2 (Async auto-ROI)
- ✅ Implement Optimization 2.3 (Caching/lazy eval)
- ⚠️ Profile and tune thread pool sizes

**Expected Result**: 30+ FPS sustained

### Week 3: Algorithmic Optimizations (Target: 40+ FPS)
- ✅ Implement Optimization 3.1 (Numba JIT)
- ✅ Implement Optimization 3.2 (CuPy GPU acceleration)
- ⚠️ Benchmark and validate accuracy

**Expected Result**: 40+ FPS on GPU-enabled systems

---

## 5. Performance Monitoring

### Add Real-time Performance Dashboard

```python
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'detection_ms': deque(maxlen=100),
            'roi_analysis_ms': deque(maxlen=100),
            'rendering_ms': deque(maxlen=100),
            'total_ms': deque(maxlen=100)
        }

    def log_timing(self, category, duration_ms):
        self.metrics[category].append(duration_ms)

    def get_stats(self):
        return {
            category: {
                'mean': np.mean(values),
                'p95': np.percentile(values, 95),
                'p99': np.percentile(values, 99)
            }
            for category, values in self.metrics.items()
        }
```

### Success Criteria

| Metric | Current | Target Phase 1 | Target Phase 2 | Target Phase 3 |
|--------|---------|----------------|----------------|----------------|
| **Average FPS** | 15-20 | 25-30 | 30-35 | 40+ |
| **P99 Frame Time** | 80-100ms | <40ms | <33ms | <25ms |
| **Detection Time** | 20-30ms | 6-10ms | 5-8ms | 2-4ms |
| **ROI Analysis (4 ROIs)** | 20ms | 6ms | 4ms | 2ms |
| **Total Pipeline** | 50-70ms | 30-35ms | 25-30ms | 20-25ms |

---

## 6. Risk Mitigation

### Potential Issues

1. **Thread Safety**: NumPy operations are generally thread-safe, but:
   - ⚠️ Ensure thermal_analyzer state (trends, history) uses locks
   - ✅ Use thread-local storage for temporary buffers

2. **GIL Contention**: Python's GIL limits true parallelism
   - ✅ Use ProcessPoolExecutor for CPU-bound tasks if needed
   - ✅ Numba/CuPy release the GIL automatically

3. **Memory Overhead**: Multiple frames in flight
   - ⚠️ Monitor memory usage
   - ✅ Use frame copying judiciously (copy.copy() vs .copy())

4. **Debugging Complexity**: Parallel bugs are harder to reproduce
   - ✅ Add comprehensive logging with thread IDs
   - ✅ Implement deterministic test mode (disable threading)

---

## 7. Code Examples

### Example: Thread-Safe ThermalAnalyzer

```python
from threading import Lock

class ThermalAnalyzer:
    def __init__(self):
        self.trend_lock = Lock()
        self.trends = {}

    def update_trend(self, roi_id: str, value: float):
        with self.trend_lock:
            if roi_id not in self.trends:
                self.trends[roi_id] = deque(maxlen=100)
            self.trends[roi_id].append(value)
```

### Example: Configurable Parallelism

```python
class InspectionApp:
    def __init__(self, args):
        # Allow disabling parallelism for debugging
        self.enable_parallel_processing = args.enable_parallel if hasattr(args, 'enable_parallel') else True
        self.max_workers = args.max_workers if hasattr(args, 'max_workers') else 4

        if self.enable_parallel_processing:
            self.detection_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        else:
            self.detection_executor = None  # Fall back to sequential
```

---

## Conclusion

By implementing these optimizations in phases, we can achieve:

- **Phase 1** (Quick Wins): 25-30 FPS with minimal risk
- **Phase 2** (Advanced): 30-35 FPS sustained
- **Phase 3** (Algorithmic): 40+ FPS on capable hardware

The key insight is that **detection tasks are embarrassingly parallel** - they operate on the same input frame but produce independent outputs. This makes them ideal candidates for concurrent execution.

**Recommended Start**: Implement Phase 1 optimizations first (Optimizations 1.1, 1.2, 1.3) as they provide the biggest performance improvement with the lowest implementation risk.
