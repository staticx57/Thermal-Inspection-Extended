#!/usr/bin/env python3
"""
SettingsManager - Central configuration management system
Cross-platform: Windows + Linux support
Handles loading, saving, validation, and migration of settings
"""

import json
import logging
import os
import platform
from pathlib import Path
from typing import Any, Dict, Optional
from copy import deepcopy

logger = logging.getLogger(__name__)


class SettingsManager:
    """
    Central settings management with JSON schema validation

    Features:
    - Cross-platform path handling (Windows + Linux)
    - Automatic migration from config.py to new format
    - Nested setting access with dot notation
    - Schema validation
    - Default value fallback
    - Atomic saves (write to temp, then rename)
    """

    def __init__(self, config_file: str = "config.json", schema_file: str = "settings_schema.json"):
        """
        Initialize settings manager

        Args:
            config_file: Path to config JSON file
            schema_file: Path to JSON schema file
        """
        self.config_file = Path(config_file)
        self.schema_file = Path(schema_file)

        # Settings storage
        self._settings: Dict[str, Any] = {}
        self._schema: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}

        # Platform detection
        self.platform = platform.system()  # 'Windows', 'Linux', 'Darwin'
        self.is_windows = self.platform == 'Windows'
        self.is_linux = self.platform == 'Linux'

        logger.info(f"SettingsManager initialized on {self.platform}")

        # Load schema and extract defaults
        self._load_schema()

        # Load settings (or create from defaults)
        self.load()

    def _load_schema(self):
        """Load JSON schema and extract default values"""
        try:
            if self.schema_file.exists():
                with open(self.schema_file, 'r', encoding='utf-8') as f:
                    self._schema = json.load(f)

                # Extract defaults from schema
                self._defaults = self._extract_defaults(self._schema.get('properties', {}))
                logger.info(f"Schema loaded: {len(self._defaults)} default values extracted")
            else:
                logger.warning(f"Schema file not found: {self.schema_file}")
                self._defaults = self._get_fallback_defaults()
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            self._defaults = self._get_fallback_defaults()

    def _extract_defaults(self, properties: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """
        Recursively extract default values from JSON schema

        Args:
            properties: Schema properties dict
            prefix: Current key prefix (for nested objects)

        Returns:
            Flat dict of default values with dot-notation keys
        """
        defaults = {}

        for key, value in properties.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if 'default' in value:
                defaults[full_key] = value['default']

            # Recurse into nested objects
            if value.get('type') == 'object' and 'properties' in value:
                nested = self._extract_defaults(value['properties'], full_key)
                defaults.update(nested)

        return defaults

    def _get_fallback_defaults(self) -> Dict[str, Any]:
        """Get minimal fallback defaults if schema fails to load"""
        return {
            "camera.thermal.width": 640,
            "camera.thermal.height": 512,
            "camera.rgb.enabled": True,
            "detection.mode": "model",
            "detection.yolo.model": "yolov8n.pt",
            "detection.yolo.confidence_threshold": 0.25,
            "gui.theme": "dark",
            "audio.enabled": True,
            "audio.volume": 0.7,
        }

    def load(self) -> bool:
        """
        Load settings from config file

        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)

                # Merge with defaults (loaded values override defaults)
                self._settings = self._deep_merge(deepcopy(self._defaults), loaded)

                logger.info(f"Settings loaded from {self.config_file}")
                return True
            else:
                logger.info(f"Config file not found, using defaults: {self.config_file}")
                self._settings = deepcopy(self._defaults)

                # Save defaults to file
                self.save()
                return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            self._settings = deepcopy(self._defaults)
            return False
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            self._settings = deepcopy(self._defaults)
            return False

    def save(self) -> bool:
        """
        Save settings to config file (atomic write)

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Atomic save: write to temp file, then rename
            temp_file = self.config_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, sort_keys=True)

            # Atomic rename (works on both Windows and Linux)
            if self.is_windows:
                # Windows: remove existing file first
                if self.config_file.exists():
                    self.config_file.unlink()

            temp_file.rename(self.config_file)

            logger.info(f"Settings saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get setting value with dot notation

        Args:
            key: Setting key (e.g., 'camera.thermal.width')
            default: Default value if key not found

        Returns:
            Setting value

        Examples:
            >>> settings.get('camera.thermal.width')
            640
            >>> settings.get('detection.yolo.model')
            'yolov8n.pt'
        """
        try:
            # Split key by dots and traverse nested dicts
            keys = key.split('.')
            value = self._settings

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    # Key not found, return default
                    return default if default is not None else self._defaults.get(key)

            return value

        except Exception as e:
            logger.debug(f"Error getting setting '{key}': {e}")
            return default if default is not None else self._defaults.get(key)

    def set(self, key: str, value: Any, save_immediately: bool = False) -> bool:
        """
        Set setting value with dot notation

        Args:
            key: Setting key (e.g., 'camera.thermal.width')
            value: New value
            save_immediately: Save to file immediately

        Returns:
            True if set successfully

        Examples:
            >>> settings.set('camera.thermal.width', 320)
            True
            >>> settings.set('detection.yolo.model', 'yolov8s.pt', save_immediately=True)
            True
        """
        try:
            # Split key by dots and traverse/create nested dicts
            keys = key.split('.')
            current = self._settings

            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]

            # Set the final value
            current[keys[-1]] = value

            logger.debug(f"Setting '{key}' = {value}")

            if save_immediately:
                return self.save()

            return True

        except Exception as e:
            logger.error(f"Error setting '{key}': {e}")
            return False

    def get_category(self, category: str) -> Dict[str, Any]:
        """
        Get all settings in a category

        Args:
            category: Category name (e.g., 'camera', 'detection')

        Returns:
            Dict of settings in category

        Examples:
            >>> settings.get_category('camera')
            {'thermal': {...}, 'rgb': {...}}
        """
        return self._settings.get(category, {})

    def reset_to_defaults(self, category: Optional[str] = None) -> bool:
        """
        Reset settings to defaults

        Args:
            category: If specified, only reset this category. If None, reset all.

        Returns:
            True if reset successful

        Examples:
            >>> settings.reset_to_defaults('camera')  # Reset only camera settings
            True
            >>> settings.reset_to_defaults()  # Reset all settings
            True
        """
        try:
            if category:
                # Reset specific category
                if category in self._defaults:
                    self._settings[category] = deepcopy(self._defaults.get(category, {}))
                    logger.info(f"Reset category '{category}' to defaults")
                else:
                    logger.warning(f"Category '{category}' not found")
                    return False
            else:
                # Reset all
                self._settings = deepcopy(self._defaults)
                logger.info("Reset all settings to defaults")

            return True

        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """
        Deep merge two dicts (override values take precedence)

        Args:
            base: Base dict
            override: Override dict

        Returns:
            Merged dict
        """
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dicts
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override value
                result[key] = value

        return result

    def export_to_file(self, file_path: str) -> bool:
        """
        Export current settings to a file

        Args:
            file_path: Destination file path

        Returns:
            True if exported successfully
        """
        try:
            export_path = Path(file_path)

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, sort_keys=True)

            logger.info(f"Settings exported to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting settings: {e}")
            return False

    def import_from_file(self, file_path: str, merge: bool = True) -> bool:
        """
        Import settings from a file

        Args:
            file_path: Source file path
            merge: If True, merge with existing settings. If False, replace all.

        Returns:
            True if imported successfully
        """
        try:
            import_path = Path(file_path)

            if not import_path.exists():
                logger.error(f"Import file not found: {import_path}")
                return False

            with open(import_path, 'r', encoding='utf-8') as f:
                imported = json.load(f)

            if merge:
                self._settings = self._deep_merge(self._settings, imported)
            else:
                self._settings = imported

            logger.info(f"Settings imported from {import_path}")
            return True

        except Exception as e:
            logger.error(f"Error importing settings: {e}")
            return False

    def migrate_from_legacy_config(self) -> bool:
        """
        Migrate settings from legacy config.py format

        Returns:
            True if migration successful or not needed
        """
        try:
            # Check if config.py exists
            legacy_config_path = Path("config.py")

            if not legacy_config_path.exists():
                logger.debug("No legacy config.py found, migration not needed")
                return True

            # Import and extract settings
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", legacy_config_path)
            if spec and spec.loader:
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)

                # Extract default_config dict
                if hasattr(config_module, 'default_config'):
                    legacy_settings = config_module.default_config

                    # Merge legacy settings into new format
                    self._settings = self._deep_merge(self._settings, legacy_settings)

                    # Save migrated settings
                    self.save()

                    logger.info("Successfully migrated from legacy config.py")
                    return True

            return False

        except Exception as e:
            logger.warning(f"Legacy config migration failed (not critical): {e}")
            return False

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate current settings against schema

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        try:
            # Basic validation (can be extended with jsonschema library)
            # For now, just check types and ranges for critical settings

            # Camera settings
            thermal_width = self.get('camera.thermal.width')
            if thermal_width not in [320, 640]:
                errors.append(f"Invalid thermal width: {thermal_width} (must be 320 or 640)")

            thermal_height = self.get('camera.thermal.height')
            if thermal_height not in [256, 512]:
                errors.append(f"Invalid thermal height: {thermal_height} (must be 256 or 512)")

            # Detection settings
            confidence = self.get('detection.yolo.confidence_threshold')
            if not (0.1 <= confidence <= 0.95):
                errors.append(f"Invalid confidence threshold: {confidence} (must be 0.1-0.95)")

            # Audio settings
            volume = self.get('audio.volume')
            if not (0.0 <= volume <= 1.0):
                errors.append(f"Invalid audio volume: {volume} (must be 0.0-1.0)")

            is_valid = len(errors) == 0

            if is_valid:
                logger.info("Settings validation passed")
            else:
                logger.warning(f"Settings validation failed: {len(errors)} error(s)")

            return is_valid, errors

        except Exception as e:
            logger.error(f"Error during validation: {e}")
            return False, [str(e)]

    def get_platform_config_dir(self) -> Path:
        """
        Get platform-specific configuration directory

        Returns:
            Path to config directory

        Platform locations:
            Windows: %APPDATA%/ThermalFusionDrivingAssist
            Linux: ~/.config/ThermalFusionDrivingAssist
            macOS: ~/Library/Application Support/ThermalFusionDrivingAssist
        """
        if self.is_windows:
            base = Path(os.environ.get('APPDATA', Path.home()))
        elif self.is_linux:
            base = Path.home() / '.config'
        else:  # macOS
            base = Path.home() / 'Library' / 'Application Support'

        config_dir = base / 'ThermalFusionDrivingAssist'
        config_dir.mkdir(parents=True, exist_ok=True)

        return config_dir

    def __repr__(self) -> str:
        """String representation"""
        return f"<SettingsManager: {len(self._settings)} categories, {self.config_file}>"


# Global singleton instance
_settings_instance: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """
    Get global SettingsManager instance (singleton pattern)

    Returns:
        SettingsManager instance

    Example:
        >>> from settings_manager import get_settings
        >>> settings = get_settings()
        >>> width = settings.get('camera.thermal.width')
    """
    global _settings_instance

    if _settings_instance is None:
        _settings_instance = SettingsManager()
        logger.info("Created global SettingsManager instance")

    return _settings_instance


def reset_settings_instance():
    """Reset global settings instance (for testing)"""
    global _settings_instance
    _settings_instance = None


if __name__ == '__main__':
    # Test settings manager
    logging.basicConfig(level=logging.INFO)

    settings = get_settings()

    print(f"\n{settings}")
    print(f"Platform: {settings.platform}")
    print(f"Config directory: {settings.get_platform_config_dir()}")

    # Test getting values
    print(f"\nThermal camera width: {settings.get('camera.thermal.width')}")
    print(f"YOLO model: {settings.get('detection.yolo.model')}")
    print(f"Theme: {settings.get('gui.theme')}")

    # Test setting values
    settings.set('camera.thermal.width', 320)
    print(f"Updated thermal width: {settings.get('camera.thermal.width')}")

    # Validate
    is_valid, errors = settings.validate()
    print(f"\nValidation: {'PASS' if is_valid else 'FAIL'}")
    if errors:
        for error in errors:
            print(f"  - {error}")

    print("\nSettings manager test complete!")
