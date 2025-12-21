"""
Platform detection utilities for Thermal Inspection application.
Detects Jetson ARM vs x86-64 workstation for optimization choices.
"""

import os
import platform
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def detect_platform() -> Dict[str, any]:
    """
    Detect platform (Jetson ARM or x86-64 workstation).

    Returns:
        Dictionary with platform information:
        - machine: Architecture string (e.g., 'x86_64', 'aarch64')
        - is_jetson: True if running on NVIDIA Jetson
        - is_arm: True if ARM architecture
        - is_x86: True if x86 architecture
        - system: OS name (e.g., 'Windows', 'Linux')
        - platform: Full platform string
    """
    machine = platform.machine()
    is_jetson = os.path.exists('/etc/nv_tegra_release') or 'tegra' in platform.platform().lower()

    platform_info = {
        'machine': machine,
        'is_jetson': is_jetson,
        'is_arm': machine in ['aarch64', 'arm64', 'armv7l'],
        'is_x86': machine in ['x86_64', 'AMD64', 'i386', 'i686'],
        'system': platform.system(),
        'platform': platform.platform()
    }

    logger.info(f"Platform: {platform_info}")
    return platform_info


def is_jetson() -> bool:
    """Quick check if running on NVIDIA Jetson."""
    return os.path.exists('/etc/nv_tegra_release') or 'tegra' in platform.platform().lower()


def is_cuda_available() -> bool:
    """Check if CUDA is available for GPU acceleration."""
    try:
        import cv2
        # Check if OpenCV was built with CUDA support
        build_info = cv2.getBuildInformation()
        return 'CUDA' in build_info and 'YES' in build_info.split('CUDA')[1].split('\n')[0]
    except Exception:
        return False


def get_optimal_device() -> str:
    """Get optimal processing device based on platform."""
    if is_cuda_available():
        return 'cuda'
    return 'cpu'
