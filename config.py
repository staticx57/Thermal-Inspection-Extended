"""
Configuration Management for ThermalFusionDrivingAssist
Handles user preferences, theme settings, and auto-retry configuration

Features:
- Automatic theme switching based on time of day
- Ambient light detection from RGB camera
- Manual theme override
- Persistent user preferences
"""
import json
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
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
        'developer_mode': False,  # Start in simple mode by default
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

        # Detection Settings
        'yolo_model': 'yolov8s.pt',
        'confidence_threshold': 0.25,
        'detection_mode': 'model',  # 'model' or 'edge'

        # Model Selection (Enhanced)
        'model_presets': {
            'yolov8n': 'yolov8n.pt',  # Nano - fastest, lower accuracy
            'yolov8s': 'yolov8s.pt',  # Small - balanced (default)
            'yolov8m': 'yolov8m.pt',  # Medium - higher accuracy
            'yolov8l': 'yolov8l.pt',  # Large - highest accuracy, slower
        },
        'thermal_model': None,  # Optional: Dedicated thermal model (e.g., FLIR-COCO trained)
        'rgb_model': None,  # Optional: Dedicated RGB model
        'custom_models': [],  # User-defined custom model paths: ['path/to/custom1.pt', ...]

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
        'device': 'cuda',  # 'cuda' or 'cpu'

        # Camera Settings
        'rgb_camera_type': 'auto',  # 'auto', 'firefly', 'uvc'
        'rgb_resolution': [640, 480],
        'rgb_fps': 30,
        'thermal_resolution': [640, 512],
    }

    def __init__(self, config_file: str = 'config.json'):
        """
        Initialize config manager

        Args:
            config_file: Path to config file (relative to project root)
        """
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()

        # Theme switching state (prevent jitter with hysteresis)
        self.last_ambient_theme = None  # Track last theme from ambient light

    def load(self) -> bool:
        """
        Load configuration from file

        Returns:
            True if loaded successfully, False if using defaults
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
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
            # Fall back to time-based if no RGB available
            return self.get_theme_from_time()

        try:
            # Calculate average brightness (convert BGR to grayscale)
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

        # If no RGB camera available, respect user's configured theme (don't auto-switch)
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
                # Light theme colors
                'critical': (200, 60, 60),     # Red
                'warning': (230, 140, 30),     # Orange
                'info': (50, 150, 200),        # Blue
                'success': (60, 180, 80),      # Green
                'text': (40, 40, 40),          # Dark gray
                'text_dim': (100, 100, 100),   # Medium gray
                'bg': (245, 245, 250),         # Light gray
                'panel_bg': (255, 255, 255),   # White
                'panel_accent': (235, 235, 240), # Very light gray
                'button_bg': (220, 220, 225),  # Light button
                'button_inactive': (200, 200, 205),
                'button_hover': (180, 180, 195),
                'button_active': (80, 200, 120),  # Green
                'button_active_alt': (100, 150, 255),  # Blue
                'button_warning': (255, 150, 60),  # Orange
                'accent_cyan': (50, 180, 220),
                'accent_green': (60, 180, 80),  # Green accent
                'accent_purple': (150, 100, 200),
                'danger_pulse': (255, 30, 30),  # Bright red for danger pulse
                'warning_pulse': (255, 200, 0),  # Bright yellow for warning pulse
                # Detection box colors (light theme - darker colors for visibility)
                'detection_person': (180, 180, 0),  # Cyan (BGR)
                'detection_vehicle': (0, 150, 0),  # Green
                'detection_bike': (180, 0, 180),  # Magenta
                'detection_traffic': (0, 0, 200),  # Red
                'detection_default': (180, 180, 0),  # Cyan
                # Distance-based colors (light theme)
                'distance_immediate': (0, 0, 200),  # Dark red
                'distance_close': (0, 100, 200),  # Dark orange
                'distance_medium': (0, 150, 150),  # Dark yellow
                'distance_safe': (0, 150, 0),  # Dark green
                'label_bg': (40, 40, 40),  # Dark gray for labels
                'motion_color': (0, 120, 200),  # Orange for motion
            }
        else:
            # Dark theme colors (default)
            return {
                'critical': (30, 30, 255),     # Red
                'warning': (0, 180, 255),      # Orange
                'info': (255, 220, 0),         # Cyan
                'success': (100, 255, 100),    # Green
                'text': (255, 255, 255),       # White
                'text_dim': (200, 200, 200),   # Dim white
                'bg': (0, 0, 0),               # Black
                'panel_bg': (35, 35, 45),      # Dark blue-gray
                'panel_accent': (45, 50, 65),  # Lighter blue-gray
                'button_bg': (40, 45, 55),
                'button_inactive': (50, 50, 60),
                'button_hover': (65, 70, 90),
                'button_active': (20, 180, 100),  # Green
                'button_active_alt': (100, 150, 255),  # Blue
                'button_warning': (255, 120, 30),  # Orange
                'accent_cyan': (0, 255, 255),
                'accent_green': (100, 255, 100),  # Green accent
                'accent_purple': (200, 100, 255),
                'danger_pulse': (0, 0, 255),  # Bright red for danger pulse
                'warning_pulse': (0, 255, 255),  # Bright yellow for warning pulse
                # Detection box colors (dark theme - bright colors for visibility)
                'detection_person': (0, 255, 255),  # Cyan (BGR)
                'detection_vehicle': (0, 255, 0),  # Green
                'detection_bike': (255, 0, 255),  # Magenta
                'detection_traffic': (0, 0, 255),  # Red
                'detection_default': (0, 255, 255),  # Cyan
                # Distance-based colors (dark theme)
                'distance_immediate': (0, 0, 255),  # Bright red
                'distance_close': (0, 165, 255),  # Bright orange
                'distance_medium': (0, 255, 255),  # Bright yellow
                'distance_safe': (0, 255, 0),  # Bright green
                'label_bg': (0, 0, 0),  # Black for labels
                'motion_color': (0, 165, 255),  # Orange for motion
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


if __name__ == "__main__":
    """Test configuration system"""
    print("="*60)
    print("Configuration System Test")
    print("="*60)

    # Create config
    config = Config('test_config.json')

    print("\nDefault configuration:")
    for key, value in config.config.items():
        print(f"  {key}: {value}")

    # Test setting values
    print("\nSetting values...")
    config.set('theme', 'light')
    config.set('yolo_model', 'yolov8n.pt')
    config.set('auto_retry_sensors', True)

    print("\nUpdated configuration:")
    print(f"  theme: {config.get('theme')}")
    print(f"  yolo_model: {config.get('yolo_model')}")
    print(f"  auto_retry_sensors: {config.get('auto_retry_sensors')}")

    # Test theme colors
    print("\nDark theme colors:")
    config.set('theme', 'dark', save=False)
    colors = config.get_theme_colors()
    for name, rgb in list(colors.items())[:5]:
        print(f"  {name}: {rgb}")

    print("\nLight theme colors:")
    config.set('theme', 'light', save=False)
    colors = config.get_theme_colors()
    for name, rgb in list(colors.items())[:5]:
        print(f"  {name}: {rgb}")

    # Test save/load
    print("\nSaving configuration...")
    config.save()

    print("\nLoading configuration...")
    config2 = Config('test_config.json')
    print(f"  Loaded theme: {config2.get('theme')}")
    print(f"  Loaded model: {config2.get('yolo_model')}")

    # Cleanup
    if os.path.exists('test_config.json'):
        os.remove('test_config.json')
        print("\nTest config file removed")

    print("\n" + "="*60)
    print("Configuration System Test Complete!")
    print("="*60)
