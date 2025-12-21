"""
Thermal Backend Factory.

Factory function to create appropriate thermal camera backend based on type.
Extracted from inspection_main.py for modular architecture.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def create_thermal_backend(backend_type: str, device_id: int, resolution: Tuple[int, int],
                           enable_sdk: bool = False, com_port: Optional[str] = None):
    """
    Factory function to create thermal camera backend.

    Args:
        backend_type: 'opencv' for FLIRBosonCamera, 'flirpy' for FlirpyThermalBackend
        device_id: Video device ID
        resolution: Camera resolution (width, height)
        enable_sdk: Enable Boson SDK for serial control
        com_port: COM port for SDK control

    Returns:
        Thermal camera backend instance
    """
    if backend_type == 'flirpy':
        logger.info(f"Creating flirpy thermal backend (16-bit Y16 + SDK via {com_port or 'COM7'})")
        try:
            from thermal_inspection.sdk.flirpy_thermal_backend import FlirpyThermalBackend
            backend = FlirpyThermalBackend(
                com_port=com_port or 'COM7',
                auto_configure=True  # Auto-configure T-Linear mode
            )
            # Flirpy backend handles SDK control internally via dual-path architecture
            # SDK control is handled separately via BosonSDK wrapper
            return backend
        except ImportError as e:
            logger.warning(f"Flirpy backend not available: {e}, falling back to opencv")
            backend_type = 'opencv'
    
    # Default to 'opencv' (FLIRBosonCamera)
    logger.info(f"Creating OpenCV thermal backend (device_id={device_id}, resolution={resolution}, sdk={enable_sdk})")
    from thermal_inspection.cameras.flir_camera import FLIRBosonCamera
    return FLIRBosonCamera(
        device_id=device_id,
        resolution=resolution,
        enable_sdk=enable_sdk,
        com_port=com_port
    )
