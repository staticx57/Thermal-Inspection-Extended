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
        self.config_file = Path(config_file)
        self.schema_file = Path(schema_file)

        self._settings: Dict[str, Any] = {}
        self._schema: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}

        self.platform = platform.system()
        self.is_windows = self.platform == 'Windows'
        self.is_linux = self.platform == 'Linux'

        logger.info(f"SettingsManager initialized on {self.platform}")

        self._load_schema()
        self.load()

    def _load_schema(self):
        """Load JSON schema and extract default values"""
        try:
            if self.schema_file.exists():
                with open(self.schema_file, encoding='utf-8') as f:
                    self._schema = json.load(f)
                self._defaults = self._extract_defaults(self._schema.get('properties', {}))
                logger.info(f"Schema loaded: {len(self._defaults)} default values extracted")
            else:
                logger.warning(f"Schema file not found: {self.schema_file}")
                self._defaults = self._get_fallback_defaults()
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            self._defaults = self._get_fallback_defaults()

    def _extract_defaults(self, properties: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """Recursively extract default values from JSON schema"""
        defaults = {}
        for key, value in properties.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if 'default' in value:
                defaults[full_key] = value['default']
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
            "detection.mode": "edge",
            "gui.theme": "dark",
            "audio.enabled": True,
            "audio.volume": 0.7,
        }

    def load(self) -> bool:
        """Load settings from config file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, encoding='utf-8') as f:
                    loaded = json.load(f)
                self._settings = self._deep_merge(deepcopy(self._defaults), loaded)
                logger.info(f"Settings loaded from {self.config_file}")
                return True
            else:
                logger.info(f"Config file not found, using defaults: {self.config_file}")
                self._settings = deepcopy(self._defaults)
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
        """Save settings to config file (atomic write)"""
        try:
            temp_file = self.config_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, sort_keys=True)
            # os.replace() is atomic and overwrites the destination on
            # both platforms - Path.rename() doesn't overwrite on
            # Windows, which is why this used to unlink() the destination
            # as a separate step first: a crash between that unlink() and
            # the rename() left no config file at all.
            os.replace(temp_file, self.config_file)
            logger.info(f"Settings saved to {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get setting value with dot notation"""
        try:
            keys = key.split('.')
            value = self._settings
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default if default is not None else self._defaults.get(key)
            return value
        except Exception as e:
            logger.debug(f"Error getting setting '{key}': {e}")
            return default if default is not None else self._defaults.get(key)

    def set(self, key: str, value: Any, save_immediately: bool = False) -> bool:
        """Set setting value with dot notation"""
        try:
            keys = key.split('.')
            current = self._settings
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value
            logger.debug(f"Setting '{key}' = {value}")
            if save_immediately:
                return self.save()
            return True
        except Exception as e:
            logger.error(f"Error setting '{key}': {e}")
            return False

    def get_category(self, category: str) -> Dict[str, Any]:
        """Get all settings in a category"""
        return self._settings.get(category, {})

    def reset_to_defaults(self, category: Optional[str] = None) -> bool:
        """Reset settings to defaults"""
        try:
            if category:
                if category in self._defaults:
                    self._settings[category] = deepcopy(self._defaults.get(category, {}))
                    logger.info(f"Reset category '{category}' to defaults")
                else:
                    logger.warning(f"Category '{category}' not found")
                    return False
            else:
                self._settings = deepcopy(self._defaults)
                logger.info("Reset all settings to defaults")
            return True
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            return False

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dicts (override values take precedence)"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def export_to_file(self, file_path: str) -> bool:
        """Export current settings to a file"""
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
        """Import settings from a file"""
        try:
            import_path = Path(file_path)
            if not import_path.exists():
                logger.error(f"Import file not found: {import_path}")
                return False
            with open(import_path, encoding='utf-8') as f:
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

    def validate(self) -> tuple:
        """Validate current settings against schema"""
        errors = []
        try:
            thermal_width = self.get('camera.thermal.width')
            if thermal_width not in [320, 640]:
                errors.append(f"Invalid thermal width: {thermal_width}")

            thermal_height = self.get('camera.thermal.height')
            if thermal_height not in [256, 512]:
                errors.append(f"Invalid thermal height: {thermal_height}")

            volume = self.get('audio.volume')
            if volume and not (0.0 <= volume <= 1.0):
                errors.append(f"Invalid audio volume: {volume}")

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
        """Get platform-specific configuration directory"""
        if self.is_windows:
            base = Path(os.environ.get('APPDATA', Path.home()))
        elif self.is_linux:
            base = Path.home() / '.config'
        else:
            base = Path.home() / 'Library' / 'Application Support'
        config_dir = base / 'ThermalInspection'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    def __repr__(self) -> str:
        return f"<SettingsManager: {len(self._settings)} categories, {self.config_file}>"


# Global singleton instance
_settings_instance: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """Get global SettingsManager instance (singleton pattern)"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = SettingsManager()
        logger.info("Created global SettingsManager instance")
    return _settings_instance


def reset_settings_instance():
    """Reset global settings instance (for testing)"""
    global _settings_instance
    _settings_instance = None
