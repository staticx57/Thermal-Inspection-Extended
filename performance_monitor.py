"""
Performance Monitoring for Jetson Orin
Tracks GPU, CPU, memory, and thermal metrics
"""
import time
import psutil
from typing import Dict, Optional
import logging

try:
    import jtop
    JTOP_AVAILABLE = True
except ImportError:
    JTOP_AVAILABLE = False
    logging.warning("jtop not available. Install with: sudo pip3 install jetson-stats")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Monitor system performance metrics on Jetson Orin"""

    def __init__(self):
        """Initialize performance monitor"""
        self.jetson = None
        self.using_jtop = False
        self.last_update = 0
        self.update_interval = 1.0  # Update every second

        # Cached metrics
        self.metrics = {
            'gpu_usage': 0.0,
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'memory_total_mb': 0,
            'memory_used_mb': 0,
            'temperature': 0.0,
            'power_watts': 0.0,
            'fps': 0.0,
            'inference_time_ms': 0.0
        }

        self._initialize_jtop()

    def _initialize_jtop(self):
        """Initialize jtop if available"""
        if JTOP_AVAILABLE:
            try:
                from jtop import jtop as JtopContext
                self.jetson = JtopContext()
                self.jetson.start()
                self.using_jtop = True
                logger.info("jtop initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize jtop: {e}")
                self.using_jtop = False
        else:
            logger.warning("jtop not available, using basic metrics only")

    def update(self) -> Dict:
        """
        Update and return current performance metrics

        Returns:
            Dictionary of performance metrics
        """
        current_time = time.time()

        # Throttle updates to reduce overhead
        if current_time - self.last_update < self.update_interval:
            return self.metrics

        self.last_update = current_time

        if self.using_jtop and self.jetson:
            self._update_with_jtop()
        else:
            self._update_basic()

        return self.metrics

    def _update_with_jtop(self):
        """Update metrics using jtop (Jetson-specific)"""
        try:
            # GPU usage
            if hasattr(self.jetson, 'gpu') and self.jetson.gpu:
                self.metrics['gpu_usage'] = float(self.jetson.gpu.get('GR3D', {}).get('status', {}).get('load', 0))

            # CPU usage (average across all cores)
            if hasattr(self.jetson, 'cpu') and self.jetson.cpu:
                cpu_loads = [core.get('user', 0) for core in self.jetson.cpu.values() if isinstance(core, dict)]
                if cpu_loads:
                    self.metrics['cpu_usage'] = sum(cpu_loads) / len(cpu_loads)

            # Memory
            if hasattr(self.jetson, 'memory') and self.jetson.memory:
                mem = self.jetson.memory.get('RAM', {})
                self.metrics['memory_total_mb'] = mem.get('tot', 0)
                self.metrics['memory_used_mb'] = mem.get('used', 0)
                total = mem.get('tot', 1)
                used = mem.get('used', 0)
                self.metrics['memory_usage'] = (used / total * 100) if total > 0 else 0

            # Temperature (average of thermal zones)
            if hasattr(self.jetson, 'temperature') and self.jetson.temperature:
                temps = [v.get('temp', 0) for v in self.jetson.temperature.values()]
                if temps:
                    self.metrics['temperature'] = sum(temps) / len(temps)

            # Power
            if hasattr(self.jetson, 'power') and self.jetson.power:
                total_power = sum([v.get('power', [0])[0] for v in self.jetson.power.values() if 'power' in v])
                self.metrics['power_watts'] = total_power / 1000.0  # mW to W

        except Exception as e:
            logger.error(f"Error updating jtop metrics: {e}")
            self._update_basic()

    def _update_basic(self):
        """Update basic metrics using psutil (fallback)"""
        try:
            # CPU usage
            self.metrics['cpu_usage'] = psutil.cpu_percent(interval=0.1)

            # Memory
            mem = psutil.virtual_memory()
            self.metrics['memory_usage'] = mem.percent
            self.metrics['memory_total_mb'] = mem.total // (1024 * 1024)
            self.metrics['memory_used_mb'] = mem.used // (1024 * 1024)

            # Temperature (if available)
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    # Get first available temperature
                    for name, entries in temps.items():
                        if entries:
                            self.metrics['temperature'] = entries[0].current
                            break
            except:
                pass

        except Exception as e:
            logger.error(f"Error updating basic metrics: {e}")

    def update_inference_metrics(self, fps: float, inference_time_ms: float):
        """
        Update inference-specific metrics

        Args:
            fps: Frames per second
            inference_time_ms: Inference time in milliseconds
        """
        self.metrics['fps'] = fps
        self.metrics['inference_time_ms'] = inference_time_ms

    def get_metrics(self) -> Dict:
        """Get current metrics without updating"""
        return self.metrics.copy()

    def get_summary(self) -> str:
        """Get formatted summary of metrics"""
        m = self.metrics
        summary = f"""
Performance Metrics:
  FPS: {m['fps']:.1f}
  Inference: {m['inference_time_ms']:.1f}ms
  GPU Usage: {m['gpu_usage']:.1f}%
  CPU Usage: {m['cpu_usage']:.1f}%
  Memory: {m['memory_used_mb']:.0f}/{m['memory_total_mb']:.0f}MB ({m['memory_usage']:.1f}%)
  Temperature: {m['temperature']:.1f}°C
  Power: {m['power_watts']:.1f}W
        """
        return summary.strip()

    def is_throttling(self) -> bool:
        """Check if system is likely throttling due to thermal/power limits"""
        return (self.metrics['temperature'] > 85.0 or  # High temp
                self.metrics['gpu_usage'] < 50.0 and self.metrics['fps'] < 15.0)  # Low performance

    def release(self):
        """Release resources"""
        if self.using_jtop and self.jetson:
            try:
                self.jetson.close()
            except:
                pass
        logger.info("Performance monitor released")

    def __del__(self):
        """Destructor"""
        self.release()