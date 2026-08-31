"""
Pytest Configuration and Shared Fixtures

This module provides common fixtures used across all test modules.
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Shared QApplication
# =============================================================================
#
# Several test modules previously each defined their own module-scoped `qapp`
# fixture (`QApplication.instance() or QApplication([])`). QApplication is a
# process-wide singleton, but PyQt's Python wrapper still owns the underlying
# C++ object — so once the module that happened to hold the *only* live
# Python reference finished and its fixture's local variable was garbage
# collected, PyQt destroyed the C++ QApplication along with it. Every QObject
# touched afterward (including the global CameraPluginHost singleton) then
# raised "wrapped C/C++ object has been deleted", with the failure appearing
# in whichever unrelated test module happened to run next — order-dependent
# and confusing to debug.
#
# A single session-scoped fixture with a persistent module-level reference
# fixes this for every test file at once: the QApplication is created once,
# held alive for the whole session, and never torn down mid-run.
_qapp_instance = None


@pytest.fixture(scope="session")
def qapp():
    global _qapp_instance
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        pytest.skip("PyQt6 not installed")
    if _qapp_instance is None:
        _qapp_instance = QApplication.instance() or QApplication([])
    return _qapp_instance


# =============================================================================
# Thermal Frame Fixtures
# =============================================================================

@pytest.fixture
def thermal_frame_8bit():
    """Create a sample 8-bit thermal frame (640x512)."""
    # Simulate a thermal scene with a hot spot in the center
    frame = np.ones((512, 640), dtype=np.uint8) * 128  # Background at mid-gray

    # Add a hot spot (circular region)
    y, x = np.ogrid[:512, :640]
    center_y, center_x = 256, 320
    radius = 50
    mask = (x - center_x)**2 + (y - center_y)**2 <= radius**2
    frame[mask] = 200  # Hot spot

    # Add a cold spot
    cold_center_y, cold_center_x = 400, 500
    cold_mask = (x - cold_center_x)**2 + (y - cold_center_y)**2 <= 30**2
    frame[cold_mask] = 50  # Cold spot

    return frame


@pytest.fixture
def thermal_frame_16bit():
    """Create a sample 16-bit radiometric thermal frame (640x512).

    Values are in T-Linear format: Kelvin * 100
    Room temperature (~25°C = 298.15K) = 29815
    """
    # Background at room temperature (25°C = 29815 in T-Linear)
    frame = np.ones((512, 640), dtype=np.uint16) * 29815

    # Add a hot spot (50°C = 32315 in T-Linear)
    y, x = np.ogrid[:512, :640]
    center_y, center_x = 256, 320
    radius = 50
    mask = (x - center_x)**2 + (y - center_y)**2 <= radius**2
    frame[mask] = 32315  # 50°C hot spot

    # Add a cold spot (10°C = 28315 in T-Linear)
    cold_center_y, cold_center_x = 400, 500
    cold_mask = (x - cold_center_x)**2 + (y - cold_center_y)**2 <= 30**2
    frame[cold_mask] = 28315  # 10°C cold spot

    return frame


@pytest.fixture
def thermal_frame_small():
    """Create a small thermal frame for fast tests (64x64)."""
    frame = np.random.randint(100, 200, size=(64, 64), dtype=np.uint8)
    # Add distinct hot spot
    frame[25:35, 25:35] = 250
    return frame


@pytest.fixture
def empty_frame():
    """Create an empty (all zeros) frame."""
    return np.zeros((512, 640), dtype=np.uint8)


@pytest.fixture
def uniform_frame():
    """Create a uniform temperature frame (no variation)."""
    return np.ones((512, 640), dtype=np.uint8) * 128


# =============================================================================
# RGB Frame Fixtures
# =============================================================================

@pytest.fixture
def rgb_frame():
    """Create a sample RGB frame (640x480)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add some color variation
    frame[:, :, 0] = 100  # Blue channel
    frame[:, :, 1] = 150  # Green channel
    frame[:, :, 2] = 200  # Red channel
    return frame


@pytest.fixture
def rgb_frame_matching_thermal():
    """Create an RGB frame matching thermal resolution (640x512)."""
    frame = np.zeros((512, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = 100
    frame[:, :, 1] = 150
    frame[:, :, 2] = 200
    return frame


# =============================================================================
# ROI Fixtures
# =============================================================================

@pytest.fixture
def sample_roi_rect():
    """Create a sample rectangular ROI definition."""
    return {
        'id': 'roi_test_1',
        'type': 'rectangle',
        'x': 100,
        'y': 100,
        'width': 200,
        'height': 150,
        'label': 'Test ROI'
    }


@pytest.fixture
def sample_roi_polygon():
    """Create a sample polygon ROI definition."""
    return {
        'id': 'roi_test_2',
        'type': 'polygon',
        'points': [(100, 100), (300, 100), (300, 250), (200, 300), (100, 250)],
        'label': 'Polygon ROI'
    }


@pytest.fixture
def sample_rois():
    """Create a list of sample ROIs."""
    return [
        {'id': 'roi_1', 'type': 'rectangle', 'x': 50, 'y': 50, 'width': 100, 'height': 100},
        {'id': 'roi_2', 'type': 'rectangle', 'x': 200, 'y': 200, 'width': 150, 'height': 100},
        {'id': 'roi_3', 'type': 'rectangle', 'x': 400, 'y': 100, 'width': 80, 'height': 80},
    ]


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def default_analyzer_config():
    """Default configuration for ThermalAnalyzer."""
    return {
        'temperature_unit': 'C',
        'hot_spot_threshold': 0.8,
        'hot_spot_min_area': 100,
        'max_hot_spots': 5,
        'cold_spot_threshold': 0.2,
        'cold_spot_min_area': 100,
        'max_cold_spots': 5,
        'anomaly_sensitivity': 0.7,
        'radiometric': False
    }


@pytest.fixture
def radiometric_analyzer_config():
    """Configuration for radiometric ThermalAnalyzer."""
    return {
        'temperature_unit': 'C',
        'hot_spot_threshold': 0.8,
        'hot_spot_min_area': 100,
        'max_hot_spots': 5,
        'cold_spot_threshold': 0.2,
        'cold_spot_min_area': 100,
        'max_cold_spots': 5,
        'anomaly_sensitivity': 0.7,
        'radiometric': True
    }


# =============================================================================
# Mock Objects
# =============================================================================

@pytest.fixture
def mock_thermal_camera(mocker):
    """Create a mock thermal camera."""
    camera = mocker.MagicMock()
    camera.is_connected.return_value = True
    camera.get_frame.return_value = (True, np.ones((512, 640), dtype=np.uint8) * 128)
    camera.get_resolution.return_value = (640, 512)
    camera.is_radiometric_enabled.return_value = False
    return camera


@pytest.fixture
def mock_rgb_camera(mocker):
    """Create a mock RGB camera."""
    camera = mocker.MagicMock()
    camera.is_connected.return_value = True
    camera.get_frame.return_value = (True, np.ones((480, 640, 3), dtype=np.uint8) * 128)
    camera.get_resolution.return_value = (640, 480)
    return camera


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file."""
    config_file = tmp_path / "test_config.json"
    config_file.write_text('{"test_key": "test_value"}')
    return config_file


@pytest.fixture
def sample_spot_meters():
    """Create sample spot meter data."""
    return [
        {'id': 'sp1', 'x': 100, 'y': 100, 'label': 'SP1', 'temperature': 25.5},
        {'id': 'sp2', 'x': 200, 'y': 200, 'label': 'SP2', 'temperature': 30.2},
        {'id': 'sp3', 'x': 300, 'y': 150, 'label': 'SP3', 'temperature': 22.1},
    ]


# =============================================================================
# Session-scoped Fixtures (expensive setup, reused across tests)
# =============================================================================

@pytest.fixture(scope='session')
def large_thermal_frame():
    """Create a large thermal frame for performance tests (1920x1080)."""
    np.random.seed(42)  # Reproducible
    frame = np.random.randint(50, 200, size=(1080, 1920), dtype=np.uint8)
    return frame
