"""
Unit Tests for PaletteManager

Tests the thermal color palette management including:
- Palette initialization and types
- Palette application to thermal frames
- Global palette switching
- Per-ROI palette overrides
"""

import pytest
import numpy as np
from thermal_inspection.processing.palette_manager import PaletteManager, PaletteType, PaletteConfig


class TestPaletteManagerInit:
    """Tests for PaletteManager initialization."""

    @pytest.mark.unit
    def test_default_initialization(self):
        """Test manager initializes with default settings."""
        manager = PaletteManager()
        assert manager is not None
        assert manager.global_palette is not None
        assert isinstance(manager.global_palette, PaletteConfig)

    @pytest.mark.unit
    def test_initialization_with_config(self):
        """Test manager initializes with configuration dictionary."""
        config = {"default_palette": "ironbow", "gamma": 1.2}
        manager = PaletteManager(config=config)
        assert manager.global_palette.palette_type == PaletteType.IRONBOW
        assert manager.global_palette.gamma == 1.2


class TestPaletteTypes:
    """Tests for palette type enumeration."""

    @pytest.mark.unit
    def test_palette_types_exist(self):
        """Test that common palette types are defined."""
        assert PaletteType.WHITE_HOT is not None
        assert PaletteType.IRONBOW is not None
        assert PaletteType.RAINBOW is not None
        assert PaletteType.VIRIDIS is not None

    @pytest.mark.unit
    def test_palette_count(self):
        """Test that multiple palettes are available."""
        palette_count = len(list(PaletteType))
        assert palette_count >= 10  # Should have at least 10 palettes

    @pytest.mark.unit
    def test_palette_type_values(self):
        """Test that palette types have string values."""
        assert PaletteType.IRONBOW.value == "ironbow"
        assert PaletteType.WHITE_HOT.value == "white_hot"


class TestPaletteApplication:
    """Tests for applying palettes to thermal frames."""

    @pytest.mark.unit
    def test_apply_palette_basic(self, thermal_frame_8bit):
        """Test basic palette application."""
        manager = PaletteManager()
        colored = manager.apply_palette(thermal_frame_8bit)

        assert colored is not None
        assert colored.shape == (512, 640, 3)  # Should be 3-channel color
        assert colored.dtype == np.uint8

    @pytest.mark.unit
    def test_apply_different_palettes(self, thermal_frame_8bit):
        """Test applying different palettes produces different results."""
        manager = PaletteManager()

        # Apply with white_hot (default)
        white_hot_config = PaletteConfig(palette_type=PaletteType.WHITE_HOT)
        white_result = manager.apply_palette(thermal_frame_8bit, white_hot_config)

        # Apply with ironbow
        ironbow_config = PaletteConfig(palette_type=PaletteType.IRONBOW)
        iron_result = manager.apply_palette(thermal_frame_8bit, ironbow_config)

        # Results should be different
        assert not np.array_equal(white_result, iron_result)

    @pytest.mark.unit
    def test_apply_palette_preserves_spatial_dims(self, thermal_frame_small):
        """Test that palette application preserves spatial dimensions."""
        manager = PaletteManager()
        colored = manager.apply_palette(thermal_frame_small)

        assert colored.shape[0] == thermal_frame_small.shape[0]
        assert colored.shape[1] == thermal_frame_small.shape[1]

    @pytest.mark.unit
    def test_apply_palette_to_16bit(self, thermal_frame_16bit):
        """Test palette application to 16-bit frame."""
        manager = PaletteManager()

        # Should handle 16-bit by normalizing to 8-bit range
        colored = manager.apply_palette(thermal_frame_16bit)

        assert colored is not None
        assert colored.shape == (512, 640, 3)

    @pytest.mark.unit
    def test_apply_palette_with_none(self):
        """Test palette application returns None for None input."""
        manager = PaletteManager()
        result = manager.apply_palette(None)
        assert result is None


class TestPaletteSwitching:
    """Tests for switching between palettes."""

    @pytest.mark.unit
    def test_set_global_palette(self):
        """Test setting global palette by type enum."""
        manager = PaletteManager()

        manager.set_global_palette(PaletteType.RAINBOW)
        assert manager.global_palette.palette_type == PaletteType.RAINBOW

        manager.set_global_palette(PaletteType.VIRIDIS)
        assert manager.global_palette.palette_type == PaletteType.VIRIDIS

    @pytest.mark.unit
    def test_set_global_palette_with_kwargs(self):
        """Test setting global palette with additional config."""
        manager = PaletteManager()

        manager.set_global_palette(PaletteType.IRONBOW, gamma=1.5, invert=True)
        assert manager.global_palette.palette_type == PaletteType.IRONBOW
        assert manager.global_palette.gamma == 1.5
        assert manager.global_palette.invert is True

    @pytest.mark.unit
    def test_get_available_palettes(self):
        """Test getting list of available palettes."""
        manager = PaletteManager()
        palettes = manager.get_available_palettes()

        assert isinstance(palettes, list)
        assert len(palettes) > 0
        assert all(isinstance(p, str) for p in palettes)

    @pytest.mark.unit
    def test_get_global_palette(self):
        """Test getting global palette configuration."""
        manager = PaletteManager()
        global_palette = manager.get_global_palette()
        
        assert isinstance(global_palette, PaletteConfig)


class TestROIPaletteOverrides:
    """Tests for per-ROI palette overrides."""

    @pytest.mark.unit
    def test_set_roi_palette(self):
        """Test setting palette override for specific ROI."""
        manager = PaletteManager()

        manager.set_roi_palette("roi_1", PaletteType.RAINBOW)
        
        assert manager.has_roi_palette("roi_1")
        roi_palette = manager.get_roi_palette("roi_1")
        assert roi_palette.palette_type == PaletteType.RAINBOW

    @pytest.mark.unit
    def test_clear_roi_palette(self):
        """Test clearing ROI palette override."""
        manager = PaletteManager()

        manager.set_roi_palette("roi_1", PaletteType.RAINBOW)
        manager.clear_roi_palette("roi_1")

        # Should return None after clearing
        assert manager.get_roi_palette("roi_1") is None
        assert not manager.has_roi_palette("roi_1")

    @pytest.mark.unit
    def test_clear_all_roi_palettes(self):
        """Test clearing all ROI palette overrides."""
        manager = PaletteManager()

        manager.set_roi_palette("roi_1", PaletteType.RAINBOW)
        manager.set_roi_palette("roi_2", PaletteType.VIRIDIS)
        manager.clear_all_roi_palettes()

        assert not manager.has_roi_palette("roi_1")
        assert not manager.has_roi_palette("roi_2")


class TestPaletteConfig:
    """Tests for PaletteConfig dataclass."""

    @pytest.mark.unit
    def test_palette_config_defaults(self):
        """Test PaletteConfig has sensible defaults."""
        config = PaletteConfig(palette_type=PaletteType.IRONBOW)
        
        assert config.auto_contrast is True
        assert config.gamma == 1.0
        assert config.invert is False

    @pytest.mark.unit
    def test_palette_config_custom(self):
        """Test PaletteConfig with custom values."""
        config = PaletteConfig(
            palette_type=PaletteType.RAINBOW,
            auto_contrast=False,
            contrast_min=0.1,
            contrast_max=0.9,
            gamma=1.5,
            invert=True
        )
        
        assert config.palette_type == PaletteType.RAINBOW
        assert config.auto_contrast is False
        assert config.contrast_min == 0.1
        assert config.contrast_max == 0.9
        assert config.gamma == 1.5
        assert config.invert is True


class TestPaletteLUT:
    """Tests for palette lookup tables."""

    @pytest.mark.unit
    def test_get_current_palette_lut(self):
        """Test getting current palette LUT."""
        manager = PaletteManager()
        lut = manager.get_current_palette_lut()

        assert lut is not None
        assert lut.shape == (256, 3)  # 256 colors, BGR

    @pytest.mark.unit
    def test_palette_cache_populated(self):
        """Test that palette cache is populated on init."""
        manager = PaletteManager()
        
        # Most palette types should be in cache
        assert len(manager.palette_cache) > 20


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.unit
    def test_empty_frame(self, empty_frame):
        """Test palette application to empty frame."""
        manager = PaletteManager()
        colored = manager.apply_palette(empty_frame)

        assert colored is not None
        # All zeros should map to min color
        assert np.all(colored == colored[0, 0])  # Uniform color

    @pytest.mark.unit
    def test_single_value_frame(self):
        """Test palette application to uniform frame."""
        manager = PaletteManager()
        frame = np.ones((100, 100), dtype=np.uint8) * 128
        colored = manager.apply_palette(frame)

        # Should be uniform color (may vary due to auto_contrast)
        assert colored is not None
        assert colored.shape == (100, 100, 3)

    @pytest.mark.unit
    def test_extreme_values(self):
        """Test palette handles extreme values (0 and 255)."""
        manager = PaletteManager()
        frame = np.array([[0, 255], [128, 64]], dtype=np.uint8)
        colored = manager.apply_palette(frame)

        assert colored is not None
        assert colored.shape == (2, 2, 3)
