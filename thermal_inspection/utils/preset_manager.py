#!/usr/bin/env python3
"""
Preset Manager for Settings
Manages runtime settings presets for quick configuration switching
Supports 3 preset slots with persistence
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SettingsPreset:
    """Settings preset configuration"""
    name: str
    view_mode: str
    fusion_mode: str
    fusion_alpha: float
    thermal_palette: str
    yolo_enabled: bool
    yolo_model: str
    show_boxes: bool
    audio_enabled: bool
    frame_skip: int
    device: str
    saved_at: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: dict) -> 'SettingsPreset':
        """Create from dictionary"""
        return SettingsPreset(**data)
    
    @staticmethod
    def from_runtime_state(name: str, app_state: Dict[str, Any]) -> 'SettingsPreset':
        """
        Create preset from current application runtime state
        
        Args:
            name: Preset name
            app_state: Dictionary with current application state
            
        Returns:
            SettingsPreset instance
        """
        return SettingsPreset(
            name=name,
            view_mode=app_state.get('view_mode', 'thermal'),
            fusion_mode=app_state.get('fusion_mode', 'alpha_blend'),
            fusion_alpha=app_state.get('fusion_alpha', 0.5),
            thermal_palette=app_state.get('thermal_palette', 'ironbow'),
            yolo_enabled=app_state.get('yolo_enabled', True),
            yolo_model=app_state.get('yolo_model', 'yolov8n.pt'),
            show_boxes=app_state.get('show_boxes', True),
            audio_enabled=app_state.get('audio_enabled', True),
            frame_skip=app_state.get('frame_skip', 1),
            device=app_state.get('device', 'cuda'),
            saved_at=datetime.now().isoformat()
        )


class PresetManager:
    """Manages settings presets with persistence"""
    
    NUM_PRESETS = 3  # Number of preset slots
    
    def __init__(self, config_file: str = "presets.json"):
        """
        Initialize preset manager
        
        Args:
            config_file: Path to preset configuration file
        """
        self.config_file = Path(config_file)
        self.presets: Dict[int, Optional[SettingsPreset]] = {
            0: None,
            1: None,
            2: None
        }
        self._load_presets()
    
    def _load_presets(self):
        """Load presets from configuration file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                
                preset_list = data.get('presets', [])
                for i in range(min(len(preset_list), self.NUM_PRESETS)):
                    if preset_list[i] and 'name' in preset_list[i]:
                        self.presets[i] = SettingsPreset.from_dict(preset_list[i])
                        logger.info(f"Loaded preset {i}: {self.presets[i].name}")
                    else:
                        self.presets[i] = None
        except Exception as e:
            logger.warning(f"Could not load presets: {e}")
            # Initialize with default preset names
            self._create_default_presets()
    
    def _create_default_presets(self):
        """Create default empty presets"""
        for i in range(self.NUM_PRESETS):
            self.presets[i] = None
        logger.debug("Created default empty presets")
    
    def _save_presets(self):
        """Save presets to configuration file"""
        try:
            preset_list = []
            for i in range(self.NUM_PRESETS):
                if self.presets[i]:
                    preset_list.append(self.presets[i].to_dict())
                else:
                    preset_list.append({'name': f'Preset {i+1}', 'settings': None})
            
            data = {
                'presets': preset_list,
                'version': '1.0'
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Presets saved to config")
        except Exception as e:
            logger.error(f"Could not save presets: {e}")
    
    def save_preset(self, slot: int, name: str, app_state: Dict[str, Any]) -> bool:
        """
        Save current application state to a preset slot
        
        Args:
            slot: Preset slot (0-2)
            name: Preset name
            app_state: Current application state dictionary
            
        Returns:
            True if saved successfully
        """
        if not 0 <= slot < self.NUM_PRESETS:
            logger.error(f"Invalid preset slot: {slot}")
            return False
        
        try:
            preset = SettingsPreset.from_runtime_state(name, app_state)
            self.presets[slot] = preset
            self._save_presets()
            logger.info(f"Saved preset to slot {slot}: {name}")
            return True
        except Exception as e:
            logger.error(f"Error saving preset: {e}")
            return False
    
    def load_preset(self, slot: int) -> Optional[SettingsPreset]:
        """
        Load preset from a slot
        
        Args:
            slot: Preset slot (0-2)
            
        Returns:
            SettingsPreset if available, None otherwise
        """
        if not 0 <= slot < self.NUM_PRESETS:
            logger.error(f"Invalid preset slot: {slot}")
            return None
        
        preset = self.presets[slot]
        if preset:
            logger.info(f"Loaded preset from slot {slot}: {preset.name}")
        else:
            logger.warning(f"No preset saved in slot {slot}")
        
        return preset
    
    def get_preset_name(self, slot: int) -> str:
        """
        Get name of preset in slot
        
        Args:
            slot: Preset slot (0-2)
            
        Returns:
            Preset name or default name if empty
        """
        if not 0 <= slot < self.NUM_PRESETS:
            return "Invalid"
        
        preset = self.presets[slot]
        if preset:
            return preset.name
        else:
            return f"Preset {slot+1}"
    
    def rename_preset(self, slot: int, new_name: str) -> bool:
        """
        Rename a preset
        
        Args:
            slot: Preset slot (0-2)
            new_name: New name for preset
            
        Returns:
            True if renamed successfully
        """
        if not 0 <= slot < self.NUM_PRESETS:
            logger.error(f"Invalid preset slot: {slot}")
            return False
        
        preset = self.presets[slot]
        if preset:
            preset.name = new_name
            self._save_presets()
            logger.info(f"Renamed preset {slot} to: {new_name}")
            return True
        else:
            logger.warning(f"Cannot rename empty preset slot {slot}")
            return False
    
    def is_slot_empty(self, slot: int) -> bool:
        """
        Check if preset slot is empty
        
        Args:
            slot: Preset slot (0-2)
            
        Returns:
            True if slot is empty
        """
        if not 0 <= slot < self.NUM_PRESETS:
            return True
        return self.presets[slot] is None
    
    def get_saved_time(self, slot: int) -> Optional[str]:
        """
        Get formatted saved time for preset
        
        Args:
            slot: Preset slot (0-2)
            
        Returns:
            Formatted datetime string or None
        """
        if not 0 <= slot < self.NUM_PRESETS:
            return None
        
        preset = self.presets[slot]
        if preset:
            try:
                dt = datetime.fromisoformat(preset.saved_at)
                return dt.strftime("%Y-%m-%d %H:%M")
            except:
                return preset.saved_at
        return None
    
    def clear_preset(self, slot: int) -> bool:
        """
        Clear a preset slot
        
        Args:
            slot: Preset slot (0-2)
            
        Returns:
            True if cleared successfully
        """
        if not 0 <= slot < self.NUM_PRESETS:
            logger.error(f"Invalid preset slot: {slot}")
            return False
        
        self.presets[slot] = None
        self._save_presets()
        logger.info(f"Cleared preset slot {slot}")
        return True
    
    def get_all_preset_names(self) -> list:
        """
        Get names of all presets
        
        Returns:
            List of preset names (3 items)
        """
        return [self.get_preset_name(i) for i in range(self.NUM_PRESETS)]


# Global preset manager instance
_preset_manager: Optional[PresetManager] = None


def get_preset_manager() -> PresetManager:
    """Get global preset manager instance (singleton)"""
    global _preset_manager
    if _preset_manager is None:
        _preset_manager = PresetManager()
    return _preset_manager
