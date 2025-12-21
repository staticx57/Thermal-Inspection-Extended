"""
Performance Monitoring for Thermal Inspection Application

BACKWARD COMPATIBILITY SHIM
New code should import from: thermal_inspection.utils.performance_monitor
"""

from thermal_inspection.utils.performance_monitor import PerformanceMonitor

__all__ = ['PerformanceMonitor']
