# Performance Best Practices Guide

> **Thermal Inspection Application**  
> Last Updated: December 2024

This guide documents performance optimization patterns, bottleneck identification, and best practices for maintaining high frame rates in the Thermal Inspection application.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Profiling & Benchmarking](#profiling--benchmarking)
3. [Frame Processing Pipeline](#frame-processing-pipeline)
4. [GPU Acceleration](#gpu-acceleration)
5. [Threaded Capture Patterns](#threaded-capture-patterns)
6. [Memory Management](#memory-management)
7. [Adaptive Resolution](#adaptive-resolution)
8. [Performance Monitoring UI](#performance-monitoring-ui)
9. [Common Bottlenecks](#common-bottlenecks)
10. [Testing Performance](#testing-performance)

---

## Architecture Overview

### Processing Pipeline Stages

```
Frame Capture → Thermal Processing → Palette Application → Temperature Estimation
     ↓
Auto-ROI Detection → ROI Analysis → Global Thermal Analysis → Anomaly Priority
     ↓
Fusion Processing → Display Selection → ROI Drawing → Display Update
```

### Key Performance Files

| File | Purpose |
|------|---------|
| `performance_monitor.py` | CPU/GPU/memory metrics, jtop support |
| `threaded_camera_capture.py` | Non-blocking camera capture |
| `thermal_processor.py` | Motion & edge detection, palette application |
| `thermal_analyzer.py` | Temperature analysis, hot/cold spot detection |
| `fusion_processor.py` | Thermal-RGB image fusion |
| `inspection_main.py` | Main processing loop with timing profile |

### Existing Parallel Processing

The application already uses `ThreadPoolExecutor` for:
- ROI analysis (parallel per-ROI processing)
- Global thermal analysis (hot spots, cold spots, anomalies in parallel)

---

## Profiling & Benchmarking

### Built-in Timing Profile

The `process_frame()` method in `inspection_main.py` already captures timing:

```python
t_prof = {}  # Timing profile
t_prof['start'] = time.time()
t_prof['before_thermal_processor'] = time.time()
# ... processing ...
t_prof['after_thermal_processor'] = time.time()
```

### Using cProfile for Detailed Analysis

```python
import cProfile
import pstats

# Profile the main loop for 100 frames
profiler = cProfile.Profile()
profiler.enable()

for _ in range(100):
    app.process_frame(thermal_frame, rgb_frame)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

### Using line_profiler for Line-by-Line Analysis

```bash
pip install line_profiler
```

```python
# Add @profile decorator to functions
@profile
def process_frame(self, thermal_frame, rgb_frame):
    ...
```

```bash
kernprof -l -v inspection_main.py
```

### PerformanceMonitor Usage

```python
from performance_monitor import PerformanceMonitor

perf = PerformanceMonitor()
metrics = perf.update()  # Returns dict with cpu_usage, memory_usage, etc.
perf.update_inference_metrics(fps=30.5, inference_time_ms=15.2)
print(perf.get_summary())
```

---

## Frame Processing Pipeline

### Optimization Principles

1. **Minimize Python loops** - Use NumPy vectorized operations
2. **Avoid frame copies** - Use `np.copyto()` to reuse buffers
3. **Process only what's needed** - Skip disabled features
4. **Batch operations** - Group similar computations

### Bad Pattern: Python Loop

```python
# ❌ SLOW: Python loop over pixels
for y in range(height):
    for x in range(width):
        if frame[y, x] > threshold:
            result[y, x] = 255
```

### Good Pattern: Vectorized NumPy

```python
# ✅ FAST: NumPy vectorized operation
result = np.where(frame > threshold, 255, 0).astype(np.uint8)
```

### Cache Expensive Computations

```python
# Cache reusable intermediate results
class CachedComputation:
    def __init__(self):
        self._cache = {}
        
    def get_or_compute(self, key, compute_fn):
        if key not in self._cache:
            self._cache[key] = compute_fn()
        return self._cache[key]
```

### Reduce Palette Application Overhead

```python
# Pre-compute LUT once, apply many times
lut = cv2.applyColorMap(np.arange(256, dtype=np.uint8), cv2.COLORMAP_JET)
colored_frame = lut[grayscale_frame]  # Direct indexing, no function call
```

---

## GPU Acceleration

### Check CUDA Availability

```python
# CuPy (NumPy-compatible GPU arrays)
try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    CUPY_AVAILABLE = False

# PyTorch CUDA
try:
    import torch
    TORCH_CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    TORCH_CUDA_AVAILABLE = False
```

### GPU-Accelerated Operations

```python
import cupy as cp

def apply_palette_gpu(frame, lut):
    """Apply color palette using GPU."""
    frame_gpu = cp.asarray(frame)
    lut_gpu = cp.asarray(lut)
    result_gpu = lut_gpu[frame_gpu]
    return cp.asnumpy(result_gpu)

def convert_y16_to_celsius_gpu(raw_frame):
    """Convert Y16 radiometric to Celsius on GPU."""
    raw_gpu = cp.asarray(raw_frame.astype(cp.float32))
    celsius_gpu = (raw_gpu - 27315.0) / 100.0
    return cp.asnumpy(celsius_gpu)
```

### VPI (NVIDIA Vision Programming Interface)

The application already checks for VPI in `thermal_processor.py`:

```python
try:
    import vpi
    VPI_AVAILABLE = True
except ImportError:
    VPI_AVAILABLE = False
```

---

## Threaded Capture Patterns

### Current Implementation

`threaded_camera_capture.py` provides:
- `ThreadedCameraCapture` - Single camera background capture
- `DualThreadedCameraCapture` - Parallel thermal + RGB capture

### Optimal Buffer Strategy

```python
class OptimizedCapture:
    def __init__(self, camera, buffer_size=2):
        self.buffer_size = buffer_size  # Small = low latency
        self.frame_buffer = [None] * buffer_size
        self.buffer_index = 0
        
    def _capture_loop(self):
        while self.running:
            ret, frame = self.camera.read()
            if ret:
                # Reuse buffer slot (zero allocation if same size)
                idx = self.buffer_index % self.buffer_size
                if self.frame_buffer[idx] is None:
                    self.frame_buffer[idx] = frame.copy()
                else:
                    np.copyto(self.frame_buffer[idx], frame)
                self.buffer_index += 1
```

### Back-Pressure Strategy

Drop frames when consumer is slower than producer:

```python
def should_process(queue_depth, max_depth=3):
    """Return False to drop frame if queue is full."""
    return queue_depth <= max_depth
```

---

## Memory Management

### Pre-allocated Frame Pool

```python
class FramePool:
    """Reduce GC pressure with pre-allocated buffers."""
    
    def __init__(self, shape, dtype=np.uint8, pool_size=10):
        self.pool = [np.empty(shape, dtype=dtype) for _ in range(pool_size)]
        self.available = set(range(pool_size))
        self.in_use = {}
        
    def acquire(self):
        if not self.available:
            return np.empty(self.shape, dtype=self.dtype)  # Fallback
        idx = self.available.pop()
        frame = self.pool[idx]
        self.in_use[id(frame)] = idx
        return frame
        
    def release(self, frame):
        frame_id = id(frame)
        if frame_id in self.in_use:
            idx = self.in_use.pop(frame_id)
            self.available.add(idx)
```

### Cleanup Old References

```python
def cleanup_old_frames(self, max_age_seconds=2.0):
    """Release frame references to help garbage collection."""
    current_time = time.time()
    if hasattr(self, '_frame_cache'):
        keys_to_delete = [
            k for k, (frame, ts) in self._frame_cache.items()
            if current_time - ts > max_age_seconds
        ]
        for k in keys_to_delete:
            del self._frame_cache[k]
```

### Monitor Memory Usage

```python
import psutil

process = psutil.Process()
memory_mb = process.memory_info().rss / (1024 * 1024)
print(f"Memory: {memory_mb:.1f} MB")
```

---

## Adaptive Resolution

### Dynamic Resolution Scaling

```python
class AdaptiveResolutionController:
    """Adjust resolution based on FPS performance."""
    
    RESOLUTION_LEVELS = [
        (640, 512),   # Full
        (512, 410),   # 80%
        (448, 358),   # 70%
        (320, 256),   # 50% (performance mode)
    ]
    
    def __init__(self, target_fps=30):
        self.target_fps = target_fps
        self.current_level = 0
        self.fps_history = []
        
    def update(self, current_fps):
        self.fps_history.append(current_fps)
        if len(self.fps_history) > 30:
            self.fps_history.pop(0)
            
        avg_fps = sum(self.fps_history) / len(self.fps_history)
        
        # Downscale if too slow
        if avg_fps < self.target_fps * 0.9:
            if self.current_level < len(self.RESOLUTION_LEVELS) - 1:
                self.current_level += 1
                
        # Upscale if fast enough
        elif avg_fps > self.target_fps * 1.1:
            if self.current_level > 0:
                self.current_level -= 1
                
        return self.RESOLUTION_LEVELS[self.current_level]
```

### Performance Mode Toggle

```python
def set_performance_mode(self, enabled):
    if enabled:
        self.auto_roi_update_interval = 30  # Less frequent
        self.resolution_level = 3  # Lowest
        self.enable_edge_detection = False
    else:
        self.auto_roi_update_interval = 10
        self.resolution_level = 0  # Highest
        self.enable_edge_detection = True
```

---

## Performance Monitoring UI

### Real-time Overlay

```python
def draw_performance_overlay(frame, metrics):
    """Draw FPS and metrics on frame corner."""
    fps = metrics.get('fps', 0)
    
    # Color based on performance
    if fps >= 30:
        color = (0, 255, 0)  # Green
    elif fps >= 20:
        color = (0, 255, 255)  # Yellow
    else:
        color = (0, 0, 255)  # Red
        
    text = f"FPS: {fps:.1f}"
    cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                1.0, color, 2)
    
    # Stage breakdown
    y = 60
    for stage, time_ms in metrics.get('stage_times', {}).items():
        cv2.putText(frame, f"{stage}: {time_ms:.1f}ms", (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += 20
```

### Export Performance Log

```python
import json

def export_performance_log(filepath, metrics):
    """Export metrics for offline analysis."""
    with open(filepath, 'w') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'fps_avg': metrics['fps_avg'],
            'fps_min': metrics['fps_min'],
            'cpu_avg': metrics['cpu_avg'],
            'memory_peak_mb': metrics['memory_peak'],
            'stage_breakdown': metrics['stage_times']
        }, f, indent=2)
```

---

## Common Bottlenecks

### 1. Palette Application (5-10ms)
**Solution:** Pre-compute LUT, use direct array indexing instead of `cv2.applyColorMap`

### 2. Auto-ROI Detection (10-20ms every N frames)
**Solution:** Increase `auto_roi_update_interval`, use simpler detection

### 3. Fusion Processing (5-15ms)
**Solution:** Reduce RGB resolution before fusion, skip if thermal-only view

### 4. ROI Drawing (1-5ms per ROI)
**Solution:** Batch draw operations, cache ROI masks

### 5. Memory Allocation (cumulative)
**Solution:** Use frame pools, reuse buffers with `np.copyto()`

### 6. GIL Contention in Threads
**Solution:** Use `multiprocessing` for CPU-bound work, `threading` for I/O

---

## Testing Performance

### Quick Benchmark

```python
import time

def benchmark_processing(app, n_frames=100):
    """Measure processing FPS."""
    thermal = np.random.randint(0, 65535, (512, 640), dtype=np.uint16)
    
    # Warm-up
    for _ in range(10):
        app.process_frame(thermal, None)
    
    # Timed run
    start = time.perf_counter()
    for _ in range(n_frames):
        app.process_frame(thermal, None)
    elapsed = time.perf_counter() - start
    
    fps = n_frames / elapsed
    print(f"Benchmark: {fps:.1f} FPS ({elapsed*1000/n_frames:.1f}ms per frame)")
    return fps
```

### Regression Test

```python
def test_fps_target():
    """Verify 30 FPS target is met."""
    fps = benchmark_processing(app, n_frames=100)
    assert fps >= 30, f"FPS {fps:.1f} below target"
```

### Memory Stability Test

```python
def test_memory_stable():
    """Verify no memory leaks over time."""
    import gc
    
    initial_memory = psutil.Process().memory_info().rss
    
    for i in range(1000):
        thermal = np.random.randint(0, 65535, (512, 640), dtype=np.uint16)
        app.process_frame(thermal, None)
        if i % 100 == 0:
            gc.collect()
    
    final_memory = psutil.Process().memory_info().rss
    growth_mb = (final_memory - initial_memory) / (1024 * 1024)
    
    assert growth_mb < 100, f"Memory grew by {growth_mb:.1f}MB"
```

---

## Implementation Checklist

### Phase 1: Profiling Infrastructure
- [ ] Create `profiler_utils.py` with FrameProfiler class
- [ ] Add profiling hooks to `process_frame()`
- [ ] Create baseline benchmark

### Phase 2: Pipeline Optimization
- [ ] Vectorize remaining Python loops
- [ ] Add frame caching for expensive operations
- [ ] Optimize palette application with pre-computed LUT

### Phase 3: GPU Acceleration (Optional)
- [ ] Add CuPy/PyTorch CUDA detection
- [ ] Implement GPU-accelerated palette application
- [ ] Implement GPU-accelerated Y16 conversion

### Phase 4: Threaded Capture Tuning
- [ ] Optimize buffer sizes in ThreadedCameraCapture
- [ ] Add back-pressure/frame-dropping strategy
- [ ] Reduce lock contention

### Phase 5: Memory Management
- [ ] Implement FramePool for pre-allocation
- [ ] Add periodic cleanup of old references
- [ ] Monitor and log memory usage

### Phase 6: Adaptive Resolution
- [ ] Implement AdaptiveResolutionController
- [ ] Add Performance Mode toggle to GUI
- [ ] Test resolution switching smoothness

### Phase 7: Benchmark UI
- [ ] Create performance overlay widget
- [ ] Add benchmark export function
- [ ] Integrate with Settings panel

### Phase 8: Testing
- [ ] Add performance regression tests
- [ ] Create CI pipeline for performance validation
- [ ] Document performance targets

---

## Quick Reference

### Performance Targets

| Metric | Target | Acceptable |
|--------|--------|------------|
| FPS (640×512) | ≥30 | ≥25 |
| Frame Time | <33ms | <40ms |
| Memory Growth/hr | <50MB | <100MB |
| Latency (capture→display) | <100ms | <150ms |

### Key Commands

```bash
# Profile application
python -m cProfile -s cumulative inspection_main.py 2>&1 | head -50

# Line-by-line profiling
kernprof -l -v inspection_main.py

# Memory profiling
python -m memory_profiler inspection_main.py

# Monitor GPU usage (Jetson)
sudo jtop
```

---

*This guide should be updated as new optimizations are implemented.*
