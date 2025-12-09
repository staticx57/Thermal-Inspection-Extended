# Enhancement #7: Performance Improvements - Implementation Plan

> **Thermal Inspection Application**  
> Created: December 2024

This document provides a detailed implementation roadmap for Enhancement #7, covering all performance optimization phases with code examples, file changes, and verification steps.

---

## Table of Contents

1. [Current Architecture Analysis](#current-architecture-analysis)
2. [Phase 1: Profiling Infrastructure](#phase-1-profiling-infrastructure)
3. [Phase 2: Frame Processing Optimization](#phase-2-frame-processing-optimization)
4. [Phase 3: GPU Acceleration](#phase-3-gpu-acceleration)
5. [Phase 4: Adaptive Resolution Scaling](#phase-4-adaptive-resolution-scaling)
6. [Phase 5: Threaded Capture Tuning](#phase-5-threaded-capture-tuning)
7. [Phase 6: Memory Management](#phase-6-memory-management)
8. [Phase 7: Benchmark Reporting UI](#phase-7-benchmark-reporting-ui)
9. [Phase 8: Testing and Validation](#phase-8-testing-and-validation)
10. [Priority Matrix](#priority-matrix)
11. [Verification Plan](#verification-plan)

---

## Current Architecture Analysis

### Existing Performance Infrastructure

| Component | File | Current State |
|-----------|------|---------------|
| PerformanceMonitor | `performance_monitor.py` | Basic CPU/GPU/memory metrics, jtop support for Jetson |
| ThreadedCameraCapture | `threaded_camera_capture.py` | Background capture with FPS tracking |
| DualThreadedCameraCapture | `threaded_camera_capture.py` | Parallel thermal + RGB capture |
| Timing Profile | `inspection_main.py:1409-1424` | `t_prof` dict capturing stage timings |
| Parallel ROI Analysis | `inspection_main.py:1537-1559` | ThreadPoolExecutor for ROI analysis |
| Parallel Global Analysis | `inspection_main.py:1580-1616` | ThreadPoolExecutor for detection |

### Processing Pipeline Flow

```
┌─────────────────┐
│  Frame Capture  │ ← DualThreadedCameraCapture
└────────┬────────┘
         ▼
┌─────────────────┐
│Thermal Processor│ ← Motion detection, edge detection
└────────┬────────┘
         ▼
┌─────────────────┐
│Palette Manager  │ ← Color palette application
└────────┬────────┘
         ▼
┌─────────────────┐
│ Temp Estimation │ ← 8-bit pseudo-radiometric (optional)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Auto-ROI Detect │ ← Temperature, gradient, motion, edge ROIs
└────────┬────────┘
         ▼
┌─────────────────┐
│  ROI Analysis   │ ← Per-ROI thermal stats (parallelized)
└────────┬────────┘
         ▼
┌─────────────────┐
│ Global Analysis │ ← Hot/cold spots, anomalies (parallelized)
└────────┬────────┘
         ▼
┌─────────────────┐
│Fusion Processor │ ← Thermal + RGB fusion modes
└────────┬────────┘
         ▼
┌─────────────────┐
│ Display Update  │ ← ROI drawing, overlay, GUI update
└─────────────────┘
```

---

## Phase 1: Profiling Infrastructure

### Goal
Establish baseline performance metrics and create tools for identifying bottlenecks.

### Files to Create/Modify

| Action | File |
|--------|------|
| CREATE | `profiler_utils.py` |
| MODIFY | `inspection_main.py` |

### Implementation: profiler_utils.py

```python
#!/usr/bin/env python3
"""
Performance Profiling Utilities for Thermal Inspection
Provides frame-level profiling with minimal overhead.
"""

import cProfile
import pstats
import io
import time
from functools import wraps
from typing import Dict, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class FrameProfiler:
    """Profile frame processing with minimal overhead.
    
    Usage:
        profiler = FrameProfiler(sample_rate=100)
        profiler.enabled = True
        
        # In processing loop:
        profiler.start_stage('thermal_processing')
        # ... do work ...
        profiler.end_stage('thermal_processing')
        
        # Get results:
        summary = profiler.get_summary()
    """
    
    def __init__(self, sample_rate: int = 100):
        """
        Args:
            sample_rate: Profile every Nth frame to reduce overhead
        """
        self.sample_rate = sample_rate
        self.frame_count = 0
        self.stage_times: Dict[str, List[float]] = {}
        self.enabled = False
        self._current_stage: Optional[str] = None
        self._stage_start: float = 0
        
    def start_stage(self, name: str):
        """Mark start of a processing stage."""
        if not self.enabled or self.frame_count % self.sample_rate != 0:
            return
        self._current_stage = name
        self._stage_start = time.perf_counter_ns()
        
    def end_stage(self, name: str):
        """Mark end of a processing stage and record time."""
        if not self.enabled or self._current_stage != name:
            return
        elapsed_ms = (time.perf_counter_ns() - self._stage_start) / 1_000_000
        if name not in self.stage_times:
            self.stage_times[name] = []
        self.stage_times[name].append(elapsed_ms)
        self._current_stage = None
        
    def frame_complete(self):
        """Call at end of each frame."""
        self.frame_count += 1
        
    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """Get statistical summary of all stages."""
        summary = {}
        for stage, times in self.stage_times.items():
            if times:
                summary[stage] = {
                    'avg_ms': sum(times) / len(times),
                    'min_ms': min(times),
                    'max_ms': max(times),
                    'p95_ms': sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
                    'samples': len(times)
                }
        return summary
    
    def reset(self):
        """Clear all recorded data."""
        self.stage_times.clear()
        self.frame_count = 0


class BenchmarkRecorder:
    """Record performance metrics over a time period."""
    
    def __init__(self):
        self.start_time: float = 0
        self.duration: int = 0
        self.fps_samples: List[float] = []
        self.cpu_samples: List[float] = []
        self.memory_samples: List[int] = []
        self.stage_times: Dict[str, List[float]] = {}
        self.frame_count: int = 0
        self.recording: bool = False
        
    def start(self, duration_seconds: int = 60):
        """Start recording benchmark data."""
        self.start_time = time.time()
        self.duration = duration_seconds
        self.fps_samples = []
        self.cpu_samples = []
        self.memory_samples = []
        self.stage_times = {}
        self.frame_count = 0
        self.recording = True
        logger.info(f"Benchmark started for {duration_seconds} seconds")
        
    def record_frame(self, fps: float, cpu: float, memory_mb: int, 
                     stage_times: Optional[Dict[str, float]] = None):
        """Record metrics for a single frame."""
        if not self.recording:
            return
            
        # Check if duration exceeded
        if time.time() - self.start_time > self.duration:
            self.recording = False
            return
            
        self.fps_samples.append(fps)
        self.cpu_samples.append(cpu)
        self.memory_samples.append(memory_mb)
        self.frame_count += 1
        
        if stage_times:
            for stage, time_ms in stage_times.items():
                if stage not in self.stage_times:
                    self.stage_times[stage] = []
                self.stage_times[stage].append(time_ms)
                
    def stop(self) -> Dict:
        """Stop recording and return summary."""
        self.recording = False
        return self.get_summary()
        
    def get_summary(self) -> Dict:
        """Calculate and return benchmark summary."""
        if not self.fps_samples:
            return {'error': 'No data recorded'}
            
        # Calculate statistics
        summary = {
            'total_frames': self.frame_count,
            'duration_seconds': time.time() - self.start_time,
            'fps': {
                'avg': sum(self.fps_samples) / len(self.fps_samples),
                'min': min(self.fps_samples),
                'max': max(self.fps_samples),
                'p5': sorted(self.fps_samples)[int(len(self.fps_samples) * 0.05)],
            },
            'cpu': {
                'avg': sum(self.cpu_samples) / len(self.cpu_samples),
                'max': max(self.cpu_samples),
            },
            'memory': {
                'avg_mb': sum(self.memory_samples) / len(self.memory_samples),
                'peak_mb': max(self.memory_samples),
            },
            'stage_breakdown': {}
        }
        
        # Stage breakdown
        total_frame_time = sum(
            sum(times) / len(times) 
            for times in self.stage_times.values()
        )
        
        for stage, times in self.stage_times.items():
            avg_ms = sum(times) / len(times)
            summary['stage_breakdown'][stage] = {
                'avg_ms': avg_ms,
                'pct_of_frame': (avg_ms / total_frame_time * 100) if total_frame_time > 0 else 0
            }
            
        return summary


def profile_function(output_file: Optional[str] = None, top_n: int = 20):
    """Decorator to profile a function with cProfile.
    
    Usage:
        @profile_function(output_file='profile.txt')
        def my_function():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()
            result = func(*args, **kwargs)
            profiler.disable()
            
            # Format output
            stream = io.StringIO()
            stats = pstats.Stats(profiler, stream=stream)
            stats.sort_stats('cumulative')
            stats.print_stats(top_n)
            
            if output_file:
                with open(output_file, 'a') as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"Profile of {func.__name__} at {time.strftime('%H:%M:%S')}\n")
                    f.write(stream.getvalue())
            else:
                logger.info(stream.getvalue())
                
            return result
        return wrapper
    return decorator
```

### Integration with inspection_main.py

Add to `ThermalInspectionFusion.__init__()`:

```python
# Performance profiling
from profiler_utils import FrameProfiler, BenchmarkRecorder
self.frame_profiler = FrameProfiler(sample_rate=100)
self.benchmark_recorder = BenchmarkRecorder()
```

Add to `process_frame()`:

```python
def process_frame(self, thermal_frame, rgb_frame):
    # Existing timing profile
    t_prof = {}
    t_prof['start'] = time.time()
    
    # Add profiler integration
    self.frame_profiler.start_stage('thermal_processor')
    processor_result = self.thermal_processor.process_frame(thermal_frame)
    self.frame_profiler.end_stage('thermal_processor')
    
    self.frame_profiler.start_stage('palette')
    thermal_colorized = self.palette_manager.apply_composite_palette(...)
    self.frame_profiler.end_stage('palette')
    
    # ... rest of processing ...
    
    self.frame_profiler.frame_complete()
```

---

## Phase 2: Frame Processing Optimization

### Goal
Reduce per-frame processing time by 30-50% through vectorization and caching.

### Files to Modify

| Action | File |
|--------|------|
| MODIFY | `inspection_main.py` |
| MODIFY | `thermal_processor.py` |
| MODIFY | `palette_manager.py` |
| MODIFY | `thermal_analyzer.py` |

### 2.1 Vectorize Spot Meter Extraction

**Current (slow):**
```python
# inspection_main.py:1806-1811
for x, y, label in coords:
    if 0 <= x < w and 0 <= y < h:
        val = temp_map_for_spots[y, x]
        if not np.isnan(val):
            spot_values.append({'label': label, 'temperature': float(val), 'unit': unit})
```

**Optimized:**
```python
if coords:
    coords_array = np.array([[x, y] for x, y, _ in coords], dtype=np.int32)
    labels = [label for _, _, label in coords]
    
    # Bounds check vectorized
    valid_mask = (
        (coords_array[:, 0] >= 0) & (coords_array[:, 0] < w) &
        (coords_array[:, 1] >= 0) & (coords_array[:, 1] < h)
    )
    
    # Extract all temperatures at once
    valid_coords = coords_array[valid_mask]
    if len(valid_coords) > 0:
        temperatures = temp_map_for_spots[valid_coords[:, 1], valid_coords[:, 0]]
        
        # Filter NaN and build results
        valid_temps = ~np.isnan(temperatures)
        for i, (temp, label) in enumerate(zip(temperatures[valid_temps], 
                                               [labels[j] for j, m in enumerate(valid_mask) if m][valid_temps])):
            spot_values.append({'label': label, 'temperature': float(temp), 'unit': unit})
```

### 2.2 Pre-compute Palette LUTs

**Add to palette_manager.py:**

```python
class PaletteManager:
    def __init__(self, ...):
        # Pre-compute all palette LUTs at startup
        self._lut_cache: Dict[str, np.ndarray] = {}
        self._precompute_luts()
        
    def _precompute_luts(self):
        """Pre-compute all palette LUTs to avoid runtime computation."""
        for palette_type in PaletteType:
            lut = self._generate_lut(palette_type)
            self._lut_cache[palette_type.value] = lut
            
    def apply_palette_fast(self, frame: np.ndarray, palette_name: str) -> np.ndarray:
        """Apply palette using pre-computed LUT (faster than cv2.applyColorMap)."""
        if palette_name not in self._lut_cache:
            return self._apply_palette_fallback(frame, palette_name)
            
        lut = self._lut_cache[palette_name]
        
        # Normalize to 8-bit if needed
        if frame.dtype == np.uint16:
            frame_8bit = (frame / 256).astype(np.uint8)
        elif frame.ndim == 3:
            frame_8bit = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            frame_8bit = frame
            
        # Direct LUT indexing (faster than cv2.LUT for simple cases)
        return lut[frame_8bit]
```

### 2.3 Cache ROI Masks

**Add to roi_manager.py:**

```python
class ROIManager:
    def __init__(self, ...):
        self._mask_cache: Dict[str, Tuple[np.ndarray, Tuple[int, int]]] = {}
        
    def get_cached_mask(self, roi_id: str, frame_shape: Tuple[int, int]) -> np.ndarray:
        """Get ROI mask with caching."""
        cache_key = roi_id
        
        if cache_key in self._mask_cache:
            cached_mask, cached_shape = self._mask_cache[cache_key]
            if cached_shape == frame_shape[:2]:
                return cached_mask
                
        # Generate and cache
        roi = self.get_roi(roi_id)
        if roi:
            mask = roi.get_mask(frame_shape)
            self._mask_cache[cache_key] = (mask, frame_shape[:2])
            return mask
            
        return None
        
    def invalidate_mask_cache(self, roi_id: Optional[str] = None):
        """Invalidate cached masks when ROI changes."""
        if roi_id:
            self._mask_cache.pop(roi_id, None)
        else:
            self._mask_cache.clear()
```

---

## Phase 3: GPU Acceleration

### Goal
Offload heavy computations to GPU when CUDA is available.

### Files to Create/Modify

| Action | File |
|--------|------|
| CREATE | `gpu_utils.py` |
| MODIFY | `thermal_processor.py` |
| MODIFY | `palette_manager.py` |
| MODIFY | `thermal_analyzer.py` |

### Implementation: gpu_utils.py

```python
#!/usr/bin/env python3
"""
GPU Acceleration Utilities
Provides CUDA acceleration when available, with CPU fallback.
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)

# Detect available GPU libraries
CUPY_AVAILABLE = False
TORCH_CUDA_AVAILABLE = False
VPI_AVAILABLE = False

try:
    import cupy as cp
    CUPY_AVAILABLE = True
    GPU_DEVICE = cp.cuda.Device(0)
    logger.info(f"CuPy available - GPU: {GPU_DEVICE.name}")
except ImportError:
    logger.info("CuPy not available")
except Exception as e:
    logger.warning(f"CuPy error: {e}")

try:
    import torch
    if torch.cuda.is_available():
        TORCH_CUDA_AVAILABLE = True
        logger.info(f"PyTorch CUDA available - GPU: {torch.cuda.get_device_name(0)}")
except ImportError:
    pass

try:
    import vpi
    VPI_AVAILABLE = True
    logger.info("VPI available for hardware acceleration")
except ImportError:
    pass


def get_acceleration_status() -> dict:
    """Get status of available GPU acceleration."""
    return {
        'cupy': CUPY_AVAILABLE,
        'torch_cuda': TORCH_CUDA_AVAILABLE,
        'vpi': VPI_AVAILABLE,
        'recommended': 'cupy' if CUPY_AVAILABLE else ('torch' if TORCH_CUDA_AVAILABLE else 'cpu')
    }


class GPUArray:
    """Wrapper for GPU array operations with automatic fallback."""
    
    @staticmethod
    def to_gpu(np_array: np.ndarray):
        """Transfer NumPy array to GPU."""
        if CUPY_AVAILABLE:
            return cp.asarray(np_array)
        return np_array
        
    @staticmethod  
    def to_cpu(gpu_array) -> np.ndarray:
        """Transfer GPU array back to CPU."""
        if CUPY_AVAILABLE and hasattr(gpu_array, 'get'):
            return gpu_array.get()
        return gpu_array
        
    @staticmethod
    def is_gpu_array(arr) -> bool:
        """Check if array is on GPU."""
        if CUPY_AVAILABLE:
            return isinstance(arr, cp.ndarray)
        return False


def apply_lut_gpu(frame: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Apply color LUT using GPU if available."""
    if not CUPY_AVAILABLE:
        return lut[frame]  # CPU fallback
        
    frame_gpu = cp.asarray(frame)
    lut_gpu = cp.asarray(lut)
    result_gpu = lut_gpu[frame_gpu]
    return cp.asnumpy(result_gpu)


def convert_y16_to_celsius_gpu(raw_frame: np.ndarray) -> np.ndarray:
    """Convert Y16 radiometric frame to Celsius using GPU."""
    if CUPY_AVAILABLE:
        raw_gpu = cp.asarray(raw_frame, dtype=cp.float32)
        celsius_gpu = (raw_gpu - 27315.0) / 100.0
        return cp.asnumpy(celsius_gpu)
    else:
        return (raw_frame.astype(np.float32) - 27315.0) / 100.0


def gaussian_blur_gpu(frame: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """Apply Gaussian blur using GPU."""
    if not CUPY_AVAILABLE:
        import cv2
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)
        
    # CuPy implementation
    from cupyx.scipy.ndimage import gaussian_filter
    frame_gpu = cp.asarray(frame)
    sigma = kernel_size / 6.0
    result_gpu = gaussian_filter(frame_gpu, sigma=sigma)
    return cp.asnumpy(result_gpu)
```

---

## Phase 4: Adaptive Resolution Scaling

### Goal
Dynamically adjust processing resolution to maintain target FPS.

### Files to Modify

| Action | File |
|--------|------|
| MODIFY | `inspection_main.py` |
| MODIFY | `inspection_gui_qt.py` (Settings panel) |

### Implementation

```python
# Add to inspection_main.py

class AdaptiveResolutionController:
    """Dynamically adjust processing resolution based on FPS."""
    
    RESOLUTION_LEVELS = [
        (640, 512),   # Level 0: Full resolution
        (512, 410),   # Level 1: 80%
        (448, 358),   # Level 2: 70%
        (320, 256),   # Level 3: 50% - Performance mode
    ]
    
    def __init__(self, target_fps: int = 30, hysteresis: float = 0.1):
        """
        Args:
            target_fps: Target frames per second
            hysteresis: FPS margin before switching (prevents oscillation)
        """
        self.target_fps = target_fps
        self.hysteresis = hysteresis
        self.current_level = 0
        self.fps_history: List[float] = []
        self.history_size = 30  # 1 second of samples at 30 FPS
        self.enabled = False
        
    def update(self, current_fps: float) -> Tuple[int, int]:
        """Update FPS and return recommended resolution.
        
        Returns:
            (width, height) tuple for processing
        """
        if not self.enabled:
            return self.RESOLUTION_LEVELS[0]
            
        self.fps_history.append(current_fps)
        if len(self.fps_history) > self.history_size:
            self.fps_history.pop(0)
            
        if len(self.fps_history) < 10:
            return self.RESOLUTION_LEVELS[self.current_level]
            
        avg_fps = sum(self.fps_history) / len(self.fps_history)
        
        # Downscale if too slow
        low_threshold = self.target_fps * (1 - self.hysteresis)
        if avg_fps < low_threshold:
            if self.current_level < len(self.RESOLUTION_LEVELS) - 1:
                self.current_level += 1
                logger.info(f"Adaptive scaling: Downscaled to {self.RESOLUTION_LEVELS[self.current_level]} (FPS: {avg_fps:.1f})")
                self.fps_history.clear()  # Reset after change
                
        # Upscale if fast enough
        high_threshold = self.target_fps * (1 + self.hysteresis)
        if avg_fps > high_threshold:
            if self.current_level > 0:
                self.current_level -= 1
                logger.info(f"Adaptive scaling: Upscaled to {self.RESOLUTION_LEVELS[self.current_level]} (FPS: {avg_fps:.1f})")
                self.fps_history.clear()
                
        return self.RESOLUTION_LEVELS[self.current_level]
        
    def set_performance_mode(self, enabled: bool):
        """Force lowest resolution for maximum performance."""
        if enabled:
            self.current_level = len(self.RESOLUTION_LEVELS) - 1
            self.enabled = False  # Disable auto-scaling
        else:
            self.current_level = 0
            self.enabled = True
```

---

## Phase 5: Threaded Capture Tuning

### Goal
Minimize capture latency and optimize buffer management.

### Files to Modify

| Action | File |
|--------|------|
| MODIFY | `threaded_camera_capture.py` |

### Optimized Implementation

```python
class OptimizedThreadedCapture:
    """Zero-copy threaded capture with ring buffer."""
    
    def __init__(self, camera, name: str = "Camera", buffer_size: int = 2):
        self.camera = camera
        self.name = name
        self.buffer_size = buffer_size
        
        # Ring buffer for zero-allocation frame storage
        self.frame_buffer: List[Optional[np.ndarray]] = [None] * buffer_size
        self.timestamp_buffer: List[float] = [0.0] * buffer_size
        self.write_index = 0
        self.read_index = 0
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Stats
        self.fps = 0.0
        self.frame_count = 0
        self.dropped_frames = 0
        
    def _capture_loop(self):
        """Optimized capture loop with buffer reuse."""
        frame_times = []
        last_time = time.time()
        
        while self.running:
            try:
                ret, frame = self.camera.read()
                
                if ret and frame is not None:
                    with self.lock:
                        # Reuse existing buffer if same shape
                        idx = self.write_index % self.buffer_size
                        
                        if self.frame_buffer[idx] is None or \
                           self.frame_buffer[idx].shape != frame.shape or \
                           self.frame_buffer[idx].dtype != frame.dtype:
                            # Allocate new buffer
                            self.frame_buffer[idx] = frame.copy()
                        else:
                            # Zero-copy reuse
                            np.copyto(self.frame_buffer[idx], frame)
                            
                        self.timestamp_buffer[idx] = time.time()
                        self.write_index += 1
                        self.frame_count += 1
                        
                        # Check for overflow (consumer too slow)
                        if self.write_index - self.read_index > self.buffer_size:
                            self.dropped_frames += 1
                            self.read_index = self.write_index - self.buffer_size
                    
                    # FPS calculation
                    current_time = time.time()
                    frame_times.append(current_time - last_time)
                    if len(frame_times) > 30:
                        frame_times.pop(0)
                    avg_time = sum(frame_times) / len(frame_times)
                    self.fps = 1.0 / avg_time if avg_time > 0 else 0
                    last_time = current_time
                    
            except Exception as e:
                logger.error(f"{self.name}: Capture error: {e}")
                time.sleep(0.01)
                
    def get_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """Get latest frame (may skip frames if consumer is slow)."""
        with self.lock:
            if self.write_index == 0:
                return False, None, 0
                
            # Get most recent frame
            idx = (self.write_index - 1) % self.buffer_size
            self.read_index = self.write_index  # Mark as read
            
            return True, self.frame_buffer[idx], self.timestamp_buffer[idx]
```

---

## Phase 6: Memory Management

### Goal
Reduce GC pressure and prevent memory leaks in long-running sessions.

### Files to Create/Modify

| Action | File |
|--------|------|
| CREATE | `memory_pool.py` |
| MODIFY | `inspection_main.py` |

### Implementation: memory_pool.py

```python
#!/usr/bin/env python3
"""
Memory Pool for Frame Buffers
Pre-allocates frame buffers to reduce garbage collection pressure.
"""

import numpy as np
from typing import Tuple, Optional, Set, Dict
import weakref
import threading
import logging

logger = logging.getLogger(__name__)


class FramePool:
    """Pre-allocated frame buffer pool."""
    
    def __init__(self, shape: Tuple[int, ...], dtype=np.uint8, pool_size: int = 10):
        """
        Args:
            shape: Frame shape (H, W) or (H, W, C)
            dtype: NumPy dtype for frames
            pool_size: Number of pre-allocated buffers
        """
        self.shape = shape
        self.dtype = dtype
        self.pool_size = pool_size
        
        # Pre-allocate buffers
        self.pool = [np.empty(shape, dtype=dtype) for _ in range(pool_size)]
        self.available: Set[int] = set(range(pool_size))
        self.in_use: Dict[int, int] = {}  # id(frame) -> pool index
        
        self.lock = threading.Lock()
        self.allocation_count = 0
        self.fallback_count = 0
        
    def acquire(self) -> np.ndarray:
        """Get a frame buffer from the pool."""
        with self.lock:
            if self.available:
                idx = self.available.pop()
                frame = self.pool[idx]
                self.in_use[id(frame)] = idx
                self.allocation_count += 1
                return frame
            else:
                # Pool exhausted, allocate new (will be GC'd)
                self.fallback_count += 1
                logger.debug(f"FramePool exhausted, allocating fallback buffer")
                return np.empty(self.shape, dtype=self.dtype)
                
    def release(self, frame: np.ndarray):
        """Return a frame buffer to the pool."""
        with self.lock:
            frame_id = id(frame)
            if frame_id in self.in_use:
                idx = self.in_use.pop(frame_id)
                self.available.add(idx)
                
    def get_stats(self) -> Dict:
        """Get pool statistics."""
        return {
            'pool_size': self.pool_size,
            'available': len(self.available),
            'in_use': len(self.in_use),
            'total_allocations': self.allocation_count,
            'fallback_allocations': self.fallback_count,
            'hit_rate': (self.allocation_count - self.fallback_count) / max(1, self.allocation_count)
        }


class FramePoolManager:
    """Manages multiple frame pools for different frame sizes."""
    
    def __init__(self):
        self.pools: Dict[Tuple, FramePool] = {}
        
    def get_pool(self, shape: Tuple[int, ...], dtype=np.uint8) -> FramePool:
        """Get or create a pool for the given frame specification."""
        key = (shape, dtype)
        if key not in self.pools:
            self.pools[key] = FramePool(shape, dtype, pool_size=5)
        return self.pools[key]
        
    def acquire(self, shape: Tuple[int, ...], dtype=np.uint8) -> np.ndarray:
        """Acquire a frame buffer of the given specification."""
        return self.get_pool(shape, dtype).acquire()
        
    def release(self, frame: np.ndarray):
        """Release a frame buffer back to its pool."""
        key = (frame.shape, frame.dtype)
        if key in self.pools:
            self.pools[key].release(frame)
```

---

## Phase 7: Benchmark Reporting UI

### Goal
Provide real-time performance visibility to users.

### Files to Create/Modify

| Action | File |
|--------|------|
| CREATE | `performance_overlay.py` |
| MODIFY | `inspection_gui_qt.py` |

### Implementation: performance_overlay.py

```python
#!/usr/bin/env python3
"""
Performance Overlay Widget for Qt GUI
Displays real-time FPS, CPU, GPU, and stage timing information.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor
from typing import Dict, Optional


class PerformanceOverlayWidget(QFrame):
    """Semi-transparent overlay showing real-time performance metrics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setObjectName("PerformanceOverlay")
        self.setStyleSheet("""
            #PerformanceOverlay {
                background-color: rgba(0, 0, 0, 180);
                border: 1px solid #444;
                border-radius: 8px;
                padding: 8px;
            }
            QLabel {
                color: white;
                font-family: 'Consolas', 'Monaco', monospace;
            }
        """)
        
        self._setup_ui()
        self.setVisible(False)  # Hidden by default
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        # FPS (large, colored)
        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.fps_label)
        
        # Frame time
        self.frame_time_label = QLabel("Frame: --ms")
        self.frame_time_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.frame_time_label)
        
        # Separator
        layout.addSpacing(4)
        
        # System metrics
        self.cpu_label = QLabel("CPU: --%")
        self.cpu_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.cpu_label)
        
        self.gpu_label = QLabel("GPU: --%")
        self.gpu_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.gpu_label)
        
        self.memory_label = QLabel("Mem: --MB")
        self.memory_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.memory_label)
        
        # Stage breakdown (expandable)
        self.stages_label = QLabel("")
        self.stages_label.setStyleSheet("font-size: 10px; color: #aaa;")
        layout.addWidget(self.stages_label)
        
    def update_metrics(self, metrics: Dict):
        """Update displayed metrics."""
        fps = metrics.get('fps', 0)
        
        # Color FPS based on performance
        if fps >= 30:
            fps_color = '#00ff00'  # Green
        elif fps >= 20:
            fps_color = '#ffff00'  # Yellow
        else:
            fps_color = '#ff4444'  # Red
            
        self.fps_label.setText(f"FPS: {fps:.1f}")
        self.fps_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {fps_color};")
        
        # Frame time
        frame_time = 1000 / fps if fps > 0 else 0
        self.frame_time_label.setText(f"Frame: {frame_time:.1f}ms")
        
        # System metrics
        self.cpu_label.setText(f"CPU: {metrics.get('cpu_usage', 0):.1f}%")
        self.gpu_label.setText(f"GPU: {metrics.get('gpu_usage', 0):.1f}%")
        self.memory_label.setText(f"Mem: {metrics.get('memory_mb', 0):.0f}MB")
        
        # Stage breakdown
        stage_times = metrics.get('stage_times', {})
        if stage_times:
            # Sort by time and show top 5
            sorted_stages = sorted(stage_times.items(), key=lambda x: -x[1])[:5]
            stage_text = "── Stages ──\n"
            for stage, time_ms in sorted_stages:
                stage_text += f"  {stage}: {time_ms:.1f}ms\n"
            self.stages_label.setText(stage_text)
        else:
            self.stages_label.setText("")
            
    def toggle_visibility(self):
        """Toggle overlay visibility."""
        self.setVisible(not self.isVisible())
```

---

## Phase 8: Testing and Validation

### Goal
Ensure optimizations don't degrade functionality and performance targets are met.

### Files to Create

| Action | File |
|--------|------|
| CREATE | `tests/test_performance.py` |

### Implementation: test_performance.py

```python
#!/usr/bin/env python3
"""
Performance Regression Tests
Verifies that performance targets are met.
"""

import pytest
import time
import numpy as np
import gc
import psutil

# Adjust import path as needed
import sys
sys.path.insert(0, '..')


class TestPerformanceTargets:
    """Automated tests to verify performance targets."""
    
    @pytest.fixture
    def mock_thermal_frame(self):
        """Generate test thermal frame."""
        return np.random.randint(0, 65535, (512, 640), dtype=np.uint16)
        
    @pytest.fixture
    def mock_rgb_frame(self):
        """Generate test RGB frame."""
        return np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        
    def test_palette_application_speed(self, mock_thermal_frame):
        """Verify palette application is under 3ms."""
        from palette_manager import PaletteManager
        
        pm = PaletteManager()
        
        # Warm-up
        for _ in range(10):
            pm.apply_global_palette(mock_thermal_frame)
        
        # Benchmark
        times = []
        for _ in range(100):
            start = time.perf_counter()
            pm.apply_global_palette(mock_thermal_frame)
            times.append((time.perf_counter() - start) * 1000)
            
        avg_time = sum(times) / len(times)
        assert avg_time < 3.0, f"Palette application took {avg_time:.2f}ms (target: <3ms)"
        
    def test_y16_conversion_speed(self, mock_thermal_frame):
        """Verify Y16 to Celsius conversion is under 1ms."""
        from thermal_analyzer import ThermalAnalyzer
        
        analyzer = ThermalAnalyzer()
        
        # Benchmark
        times = []
        for _ in range(100):
            start = time.perf_counter()
            celsius = (mock_thermal_frame.astype(np.float32) - 27315.0) / 100.0
            times.append((time.perf_counter() - start) * 1000)
            
        avg_time = sum(times) / len(times)
        assert avg_time < 1.0, f"Y16 conversion took {avg_time:.2f}ms (target: <1ms)"
        
    def test_memory_stability(self):
        """Verify memory doesn't grow unbounded over 1000 frames."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Simulate processing 1000 frames
        for i in range(1000):
            # Allocate frame-like arrays
            thermal = np.random.randint(0, 65535, (512, 640), dtype=np.uint16)
            rgb = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
            result = (thermal.astype(np.float32) - 27315.0) / 100.0
            
            # Clean up explicit references
            del thermal, rgb, result
            
            if i % 100 == 0:
                gc.collect()
                
        gc.collect()
        final_memory = process.memory_info().rss
        growth_mb = (final_memory - initial_memory) / (1024 * 1024)
        
        assert growth_mb < 100, f"Memory grew by {growth_mb:.1f}MB (limit: 100MB)"
        
    def test_frame_pool_effectiveness(self):
        """Verify frame pool reduces allocations."""
        from memory_pool import FramePool
        
        pool = FramePool((512, 640), dtype=np.uint16, pool_size=5)
        
        # Simulate acquire/release cycle
        for _ in range(100):
            frames = [pool.acquire() for _ in range(3)]
            for f in frames:
                pool.release(f)
                
        stats = pool.get_stats()
        assert stats['hit_rate'] > 0.9, f"Pool hit rate {stats['hit_rate']:.2%} below 90%"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

---

## Priority Matrix

| Priority | Phase | Effort | Impact | Dependencies |
|----------|-------|--------|--------|--------------|
| 🔴 **HIGH** | Phase 1: Profiling | 2-3 hrs | Foundation | None |
| 🔴 **HIGH** | Phase 2: Pipeline | 4-6 hrs | +30% FPS | Phase 1 |
| 🟡 MEDIUM | Phase 5: Capture | 2-3 hrs | -20ms latency | None |
| 🟡 MEDIUM | Phase 7: UI | 3-4 hrs | User visibility | Phase 1 |
| 🟢 LOW | Phase 3: GPU | 4-6 hrs | +50% FPS (with GPU) | Phase 2 |
| 🟢 LOW | Phase 4: Resolution | 2-3 hrs | Graceful degradation | Phase 1 |
| 🟢 LOW | Phase 6: Memory | 2-3 hrs | Long-run stability | None |
| 🟢 LOW | Phase 8: Testing | 3-4 hrs | Regression prevention | All |

---

## Verification Plan

### Performance Targets

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| FPS (640×512) | ≥30 | ≥25 | <20 |
| Frame Time | <33ms | <40ms | >50ms |
| Memory Growth/hr | <50MB | <100MB | >200MB |
| Capture Latency | <50ms | <100ms | >150ms |

### Automated Tests
```bash
# Run performance tests
cd tests
pytest test_performance.py -v

# Run with profiling
python -m cProfile -s cumulative ../inspection_main.py
```

### Manual Verification
1. Enable Performance Overlay (Settings → Show Performance)
2. Run for 10 minutes, observe FPS stability
3. Check memory in Task Manager over time
4. Test GPU toggle if CUDA available
5. Verify detection accuracy unchanged

---

## Next Steps

1. **Create `profiler_utils.py`** with FrameProfiler class
2. **Run baseline benchmark** before any optimizations  
3. **Implement Phase 2** (highest impact)
4. **Add Performance Overlay** for visibility
5. **Create test suite** for regression prevention

---

*Document created: December 2024*  
*See also: `PERFORMANCE_GUIDE.md` for best practices reference*
