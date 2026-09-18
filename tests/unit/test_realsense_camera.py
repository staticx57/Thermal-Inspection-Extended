"""
Regression test for a real RealSense L515 integration bug (2026-09-08):
get_depth_sensor_options() attached the D400-family (rs.rs400_visual_preset)
name map to ANY device's 'visual_preset' option unconditionally, with no
check of which product line was actually connected. The L515 (an L500-line
solid-state LiDAR) exposes an option also named 'visual_preset' but with a
completely different int-to-meaning mapping (rs.l500_visual_preset) - so an
L515's real preset value 3 ("Low Ambient Light") rendered in the control
panel dropdown mislabeled as "High Accuracy" (a D400-only preset name).

Uses lightweight fakes for the depth sensor/device rather than real
hardware or a full pyrealsense2 mock - only the specific methods
get_depth_sensor_options() actually calls are stubbed.
"""
import pytest

from thermal_inspection.cameras.realsense_camera import (
    RGBCameraRealSense,
    REALSENSE_AVAILABLE,
    _VISUAL_PRESET_NAMES,
    _L500_VISUAL_PRESET_NAMES,
)

pytestmark = pytest.mark.skipif(
    not REALSENSE_AVAILABLE, reason="pyrealsense2 not installed"
)


class _FakeOption:
    def __init__(self, name):
        self.name = name


class _FakeOptionRange:
    min, max, step, default = 0, 6, 1, 1


class _FakeDepthSensor:
    """Only implements the methods get_depth_sensor_options() calls."""

    def __init__(self, current_value=3):
        self._current_value = current_value

    def get_supported_options(self):
        return [_FakeOption('visual_preset')]

    def supports(self, opt):
        return True

    def get_option_range(self, opt):
        return _FakeOptionRange()

    def get_option(self, opt):
        return self._current_value


class _FakeDevice:
    """Only implements get_info(), matching real rs.device's contract for
    the one field get_depth_sensor_options() reads (product_line)."""

    def __init__(self, product_line):
        self._product_line = product_line

    def get_info(self, camera_info_field):
        return self._product_line


class TestVisualPresetNameMapSelection:
    def test_d400_device_gets_d400_preset_names(self):
        cam = RGBCameraRealSense()
        cam._depth_sensor = _FakeDepthSensor()
        cam._device = _FakeDevice("D400")

        options = cam.get_depth_sensor_options()

        assert options['visual_preset']['enum_names'] == _VISUAL_PRESET_NAMES
        assert options['visual_preset']['enum_names'][3] == 'High Accuracy'

    def test_l500_device_gets_l500_preset_names_not_d400(self):
        """The actual regression: an L515 (product_line 'L500') must not
        be labeled with D400-family preset names."""
        cam = RGBCameraRealSense()
        cam._depth_sensor = _FakeDepthSensor()
        cam._device = _FakeDevice("L500")

        options = cam.get_depth_sensor_options()

        assert options['visual_preset']['enum_names'] == _L500_VISUAL_PRESET_NAMES
        assert options['visual_preset']['enum_names'][3] == 'Low Ambient Light'
        assert options['visual_preset']['enum_names'][3] != _VISUAL_PRESET_NAMES[3]

    def test_no_device_falls_back_to_d400_names_without_crashing(self):
        """If product_line can't be read for any reason, this must
        degrade to the historical D400 behavior, never raise."""
        cam = RGBCameraRealSense()
        cam._depth_sensor = _FakeDepthSensor()
        cam._device = None

        options = cam.get_depth_sensor_options()

        assert options['visual_preset']['enum_names'] == _VISUAL_PRESET_NAMES

    def test_device_get_info_raising_falls_back_gracefully(self):
        class _RaisingDevice:
            def get_info(self, field):
                raise RuntimeError("firmware doesn't report this field")

        cam = RGBCameraRealSense()
        cam._depth_sensor = _FakeDepthSensor()
        cam._device = _RaisingDevice()

        options = cam.get_depth_sensor_options()

        assert options['visual_preset']['enum_names'] == _VISUAL_PRESET_NAMES


class TestPresetNameMapsThemselves:
    def test_d400_and_l500_maps_disagree_on_shared_integers(self):
        """Sanity-check the premise of this whole bug: these two maps
        really do assign different meanings to the same integers -
        otherwise none of this would matter."""
        shared_keys = set(_VISUAL_PRESET_NAMES) & set(_L500_VISUAL_PRESET_NAMES)
        assert shared_keys, "test setup: maps should overlap on some keys"
        disagreements = [
            k for k in shared_keys
            if _VISUAL_PRESET_NAMES[k] != _L500_VISUAL_PRESET_NAMES[k]
        ]
        assert disagreements, (
            "D400 and L500 preset maps must genuinely differ for this "
            "bug (and its fix) to matter"
        )
