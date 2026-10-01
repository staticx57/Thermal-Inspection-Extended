"""
Configuration Management for Thermal Inspection Application
Handles user preferences, theme settings, and auto-retry configuration

Features:
- Automatic theme switching based on time of day
- Ambient light detection from RGB camera
- Manual theme override
- Persistent user preferences
"""
import copy
import json
import os
import logging
import platform
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class Config:
    """
    Configuration manager with file persistence
    Stores user preferences between sessions
    """

    DEFAULT_CONFIG = {
        # GUI Settings
        'theme': 'dark',  # 'dark' or 'light'
        'theme_mode': 'auto',  # 'auto', 'manual', 'time', 'ambient'
        'show_info_panel': False,  # Info panel hidden by default

        # Theme Auto-Switching
        'auto_theme_enabled': True,  # Enable automatic theme switching
        'day_start_hour': 7,  # Light theme starts at 7 AM
        'night_start_hour': 19,  # Dark theme starts at 7 PM
        'use_ambient_light': True,  # Use RGB camera ambient light
        'ambient_threshold': 100,  # Brightness threshold (0-255)
        'ambient_hysteresis': 15,  # Brightness dead zone to prevent jitter
        'theme_override': None,  # Manual override: None, 'light', or 'dark'

        # Sensor Settings
        'auto_retry_sensors': True,  # Auto-retry when fusion mode enabled
        'thermal_retry_interval': 3,  # seconds
        'rgb_retry_interval': 100,  # frames

        # Audio Settings
        'audio_enabled': True,
        'audio_volume': 0.7,

        # View Settings
        'view_mode': 'thermal',  # 'thermal', 'rgb', 'fusion', etc.
        'thermal_palette': 'ironbow',
        'fusion_mode': 'alpha_blend',
        'fusion_alpha': 0.5,

        # Performance Settings
        'buffer_flush_enabled': False,
        'frame_skip_value': 1,
        'device': 'cuda',  # 'cuda', 'cpu', or 'directml' (Intel/AMD - see utils/gpu_device.py)

        # Camera Settings
        'rgb_camera_type': 'auto',  # 'auto', 'firefly', 'uvc'
        'rgb_resolution': [640, 480],
        'rgb_fps': 30,
        'thermal_resolution': [640, 512],
        'thermal_device_id': None,  # Persisted device ID for Fast Path
        'rgb_device_id': None,      # Persisted device ID for Fast Path
        # Persisted video device scan; skips hardware probing on warm start.
        # See thermal_inspection/cameras/device_scanner.py
        'video_device_cache': None,

        # SDK/Serial Port Settings
        'sdk_com_port': None,  # COM port for SDK serial (None = auto-detect)
        'sdk_com_port_default': 'COM7',  # Default Windows COM port for FLIR
        'sdk_com_port_linux': '/dev/ttyACM0',  # Default Linux serial port
        'sdk_com_port_options': ['COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', '/dev/ttyACM0', '/dev/ttyUSB0'],

        # Per-plugin serial defaults (CCI control channels)
        'serial_ports': {
            'flir_boson': {'port': 'COM7', 'linux_port': '/dev/ttyACM0', 'baud': 921600},
            'flir_tau2': {'port': 'COM5', 'linux_port': '/dev/ttyUSB0', 'baud': 57600},
        },

        # Parallax correction alignment - a fixed mounting offset, once
        # found (by hand, or via Auto-Detect/Auto-Crop), shouldn't need
        # re-tuning on every app restart. None of these persisted before
        # 2026-09-08; ParallaxCompensator's own constructor defaults
        # (CameraGeometry's baseline_mm=50.0, manual_shift=(0,0),
        # fov_zoom_factor=1.0) are used whenever no saved value exists,
        # so this is purely additive - an app with no history behaves
        # exactly as before.
        'parallax_baseline_mm': None,
        'parallax_shift_x': None,
        'parallax_shift_y': None,
        'parallax_fov_zoom_factor': None,
        # (top, bottom, left, right) pixel counts from a one-time
        # Auto-Crop, or None if never run - see
        # ParallaxCompensator.set_crop_rect()/compute_auto_crop().
        'parallax_crop_rect': None,

        # Geometric (RGB -> thermal homography) alignment calibration: the file it was last loaded from/saved to and
        # whether it is switched on. Restored at startup; --calibration-file overrides the file.
        'alignment_calibration_file': None,
        'alignment_calibration_enabled': True,
    }

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize config manager

        Args:
            config_file: Path to config file (relative to project root)
        """
        if config_file is None:
            from thermal_inspection.utils.paths import data_path
            config_file = str(data_path('config.json'))
            os.makedirs(os.path.dirname(config_file) or '.', exist_ok=True)
        self.config_file = config_file
        # DEFAULT_CONFIG nests mutable objects (rgb_resolution/
        # thermal_resolution lists, the serial_ports dict-of-dicts) - a
        # shallow .copy() shares those by reference across every
        # ConfigManager instance, so any future in-place mutation
        # (.append, item assignment) on one instance's config would
        # silently corrupt the class-level default for the rest of the
        # process. No such mutation exists today, but deepcopy costs
        # nothing here (this dict is tiny, built once per instance).
        self.config = copy.deepcopy(self.DEFAULT_CONFIG)
        self.load()

        # Theme switching state (prevent jitter with hysteresis)
        self.last_ambient_theme = None

    def load(self) -> bool:
        """
        Load configuration from file

        Returns:
            True if loaded successfully, False if using defaults
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file) as f:
                    loaded_config = json.load(f)
                    # Merge with defaults (in case new keys added)
                    self.config.update(loaded_config)
                    logger.info(f"Configuration loaded from {self.config_file}")
                    return True
            else:
                logger.info("No config file found, using defaults")
                return False
        except Exception as e:
            logger.warning(f"Failed to load config: {e}. Using defaults.")
            return False

    def save(self) -> bool:
        """
        Save configuration to file

        Returns:
            True if saved successfully
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Set configuration value

        Args:
            key: Configuration key
            value: Value to set
            save: Whether to save to file immediately

        Returns:
            True if successful
        """
        self.config[key] = value
        if save:
            return self.save()
        return True

    def update(self, updates: Dict[str, Any], save: bool = True) -> bool:
        """
        Update multiple configuration values

        Args:
            updates: Dictionary of key-value pairs to update
            save: Whether to save to file immediately

        Returns:
            True if successful
        """
        self.config.update(updates)
        if save:
            return self.save()
        return True

    def reset_to_defaults(self, save: bool = True) -> bool:
        """
        Reset configuration to defaults

        Args:
            save: Whether to save to file immediately

        Returns:
            True if successful
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if save:
            return self.save()
        return True

    def get_theme_from_time(self) -> str:
        """
        Determine theme based on current time of day

        Returns:
            'light' or 'dark'
        """
        current_hour = datetime.now().hour
        day_start = self.config.get('day_start_hour', 7)
        night_start = self.config.get('night_start_hour', 19)

        if day_start <= current_hour < night_start:
            return 'light'
        else:
            return 'dark'

    def get_theme_from_ambient(self, rgb_frame: Optional[np.ndarray]) -> str:
        """
        Determine theme based on ambient light from RGB camera

        Args:
            rgb_frame: RGB camera frame (BGR format from OpenCV)

        Returns:
            'light' or 'dark'
        """
        if rgb_frame is None:
            return self.get_theme_from_time()

        try:
            gray = np.mean(rgb_frame, axis=2)
            avg_brightness = np.mean(gray)
            threshold = self.config.get('ambient_threshold', 100)

            if avg_brightness > threshold:
                return 'light'
            else:
                return 'dark'

        except Exception as e:
            logger.warning(f"Ambient light detection failed: {e}")
            return self.get_theme_from_time()

    def get_active_theme(self, rgb_frame: Optional[np.ndarray] = None) -> str:
        """
        Get currently active theme considering all settings

        Priority:
        1. Manual override (if set)
        2. Ambient light (if use_ambient_light + RGB available)
        3. Time-based (if auto_theme_enabled)
        4. Configured theme

        Args:
            rgb_frame: RGB camera frame for ambient light detection

        Returns:
            'light' or 'dark'
        """
        # Check for manual override
        override = self.config.get('theme_override')
        if override in ['light', 'dark']:
            return override

        # Check if auto theme is enabled
        if not self.config.get('auto_theme_enabled', True):
            return self.config.get('theme', 'dark')

        # Try ambient light first (if enabled and RGB available)
        if self.config.get('use_ambient_light', True) and rgb_frame is not None:
            return self.get_theme_from_ambient(rgb_frame)

        # If no RGB camera available, respect user's configured theme
        if rgb_frame is None:
            return self.config.get('theme', 'dark')

        # Only use time-based if RGB camera exists but ambient disabled
        return self.get_theme_from_time()

    def set_theme_override(self, override: Optional[str], save: bool = True) -> bool:
        """
        Set manual theme override

        Args:
            override: None (auto), 'light', or 'dark'
            save: Whether to save to file

        Returns:
            True if successful
        """
        if override not in [None, 'light', 'dark']:
            logger.error(f"Invalid theme override: {override}")
            return False

        return self.set('theme_override', override, save=save)

    def get_theme_colors(self) -> Dict[str, tuple]:
        """
        Get color scheme based on current theme

        Returns:
            Dictionary of color names to RGB tuples
        """
        if self.config['theme'] == 'light':
            return {
                'critical': (200, 60, 60),
                'warning': (230, 140, 30),
                'info': (50, 150, 200),
                'success': (60, 180, 80),
                'text': (40, 40, 40),
                'text_dim': (100, 100, 100),
                'bg': (245, 245, 250),
                'panel_bg': (255, 255, 255),
                'panel_accent': (235, 235, 240),
                'button_bg': (220, 220, 225),
                'button_inactive': (200, 200, 205),
                'button_hover': (180, 180, 195),
                'button_active': (80, 200, 120),
                'button_active_alt': (100, 150, 255),
                'button_warning': (255, 150, 60),
                'accent_cyan': (50, 180, 220),
                'accent_green': (60, 180, 80),
                'accent_purple': (150, 100, 200),
                'danger_pulse': (255, 30, 30),
                'warning_pulse': (255, 200, 0),
                'detection_person': (180, 180, 0),
                'detection_vehicle': (0, 150, 0),
                'detection_bike': (180, 0, 180),
                'detection_traffic': (0, 0, 200),
                'detection_default': (180, 180, 0),
                'distance_immediate': (0, 0, 200),
                'distance_close': (0, 100, 200),
                'distance_medium': (0, 150, 150),
                'distance_safe': (0, 150, 0),
                'label_bg': (40, 40, 40),
                'motion_color': (0, 120, 200),
            }
        else:
            return {
                'critical': (30, 30, 255),
                'warning': (0, 180, 255),
                'info': (255, 220, 0),
                'success': (100, 255, 100),
                'text': (255, 255, 255),
                'text_dim': (200, 200, 200),
                'bg': (0, 0, 0),
                'panel_bg': (35, 35, 45),
                'panel_accent': (45, 50, 65),
                'button_bg': (40, 45, 55),
                'button_inactive': (50, 50, 60),
                'button_hover': (65, 70, 90),
                'button_active': (20, 180, 100),
                'button_active_alt': (100, 150, 255),
                'button_warning': (255, 120, 30),
                'accent_cyan': (0, 255, 255),
                'accent_green': (100, 255, 100),
                'accent_purple': (200, 100, 255),
                'danger_pulse': (0, 0, 255),
                'warning_pulse': (0, 255, 255),
                'detection_person': (0, 255, 255),
                'detection_vehicle': (0, 255, 0),
                'detection_bike': (255, 0, 255),
                'detection_traffic': (0, 0, 255),
                'detection_default': (0, 255, 255),
                'distance_immediate': (0, 0, 255),
                'distance_close': (0, 165, 255),
                'distance_medium': (0, 255, 255),
                'distance_safe': (0, 255, 0),
                'label_bg': (0, 0, 0),
                'motion_color': (0, 165, 255),
            }


# Global config instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance (singleton pattern)

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def get_serial_port(plugin_id: str, fallback: str = None) -> str:
    """
    Resolve the serial control port for a camera plugin.

    An explicit user override (``sdk_com_port``) wins, then the platform-
    appropriate per-plugin default from ``serial_ports``.

    Args:
        plugin_id: Plugin identifier, e.g. 'flir_boson' or 'flir_tau2'.
        fallback: Port to use when the plugin has no configured entry.
    """
    config = get_config()

    override = config.get('sdk_com_port')
    if override:
        return override

    entry = config.get('serial_ports', {}).get(plugin_id, {})
    key = 'linux_port' if platform.system() != 'Windows' else 'port'
    if fallback is None:
        from thermal_inspection.utils.paths import default_serial_port
        fallback = default_serial_port()
    return entry.get(key) or fallback


def get_serial_baud(plugin_id: str, fallback: int = 115200) -> int:
    """
    Resolve the serial baud rate for a camera plugin's CCI channel.

    Args:
        plugin_id: Plugin identifier, e.g. 'flir_boson' or 'flir_tau2'.
        fallback: Baud rate to use when the plugin has no configured entry.
    """
    entry = get_config().get('serial_ports', {}).get(plugin_id, {})
    return entry.get('baud', fallback)
