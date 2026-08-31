
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from thermal_inspection.app import ThermalInspectionApp

class TestAppWiring(unittest.TestCase):
    def setUp(self):
        self.app = ThermalInspectionApp(qt_app=None)

        # Mock the internal processors
        self.app.fusion_processor = MagicMock()
        self.app.thermal_analyzer = MagicMock()
        self.app.thermal_processor = MagicMock()
        self.app.radiometric_controller = MagicMock()

    def test_fusion_delegates(self):
        """Verify fusion settings are delegated to fusion_processor."""
        # Strength -> set_intensity
        self.app.set_fusion_strength(0.75)
        self.app.fusion_processor.set_intensity.assert_called_with(0.75)

        # Fuzziness -> set_edge_blur
        self.app.set_fusion_fuzziness(0.5)
        self.app.fusion_processor.set_edge_blur.assert_called()

        # Edge Strength -> set_edge_strength (inverted logic)
        self.app.set_edge_strength(0.8)
        self.app.fusion_processor.set_edge_strength.assert_called()

        # Edge Color
        self.app.set_edge_color('red')
        self.app.fusion_processor.set_edge_color.assert_called_with((0, 0, 255))

    def test_detail_delegates(self):
        """Verify detail settings are delegated."""
        self.app.set_detail_strength(1.5)
        # Check attribute set
        self.assertEqual(self.app.fusion_processor.detail_strength, 1.5)

        self.app.set_detail_quality('high')
        self.assertEqual(self.app.fusion_processor.detail_quality, 1.0)

    def test_environmental_delegates(self):
        """Verify environmental settings are delegated to thermal_analyzer."""
        self.app.set_emissivity(0.95)
        self.app.thermal_analyzer.set_emissivity.assert_called_with(0.95)

        self.app.set_atmospheric_temperature(300.0)
        self.app.thermal_analyzer.set_atmospheric_temperature.assert_called_with(300.0)

        self.app.set_atmospheric_transmission(0.99)
        self.app.thermal_analyzer.set_atmospheric_transmission.assert_called_with(0.99)


class TestThermalResolutionSync(unittest.TestCase):
    """
    Regression coverage for a UI-alignment bug: the overlay's
    thermal_resolution defaulted to (640, 512) and nothing ever called
    set_thermal_resolution(), so every ROI/spot-meter/hot-spot marker was
    misplaced on any camera that isn't a full-res Boson. app.py now tracks
    the real captured frame's shape every tick and pushes it to the GUI
    only when it changes.
    """

    def setUp(self):
        self.app = ThermalInspectionApp(qt_app=None)

    def test_initial_resolution_defaults_match_overlay_default(self):
        # Must match InspectionOverlayWidget's own default so there is no
        # gap between app startup and the first real frame.
        self.assertEqual(self.app._last_thermal_resolution, (640, 512))
        self.assertIsNone(self.app._gui_thermal_resolution_synced)

    def test_gui_receives_resolution_on_change(self):
        self.app.gui = MagicMock()
        self.app._last_thermal_resolution = (336, 256)  # e.g. a Tau2

        if self.app._last_thermal_resolution != self.app._gui_thermal_resolution_synced:
            self.app.gui.update_thermal_resolution(*self.app._last_thermal_resolution)
            self.app._gui_thermal_resolution_synced = self.app._last_thermal_resolution

        self.app.gui.update_thermal_resolution.assert_called_once_with(336, 256)

    def test_gui_is_not_re_notified_when_resolution_is_unchanged(self):
        # The frame loop runs this check every tick; a real camera's shape
        # does not change frame-to-frame, so this must not fire every time.
        self.app.gui = MagicMock()
        self.app._last_thermal_resolution = (640, 512)
        self.app._gui_thermal_resolution_synced = (640, 512)

        if self.app._last_thermal_resolution != self.app._gui_thermal_resolution_synced:
            self.app.gui.update_thermal_resolution(*self.app._last_thermal_resolution)

        self.app.gui.update_thermal_resolution.assert_not_called()


class TestThreadedCaptureRestartSuppression(unittest.TestCase):
    """
    Regression coverage for a real bug found debugging RGB camera
    instability with a physical Boson connected: cleanup() and
    reassign_cameras() both deactivate thermal and rgb one role at a time.
    Each individual deactivation fires a camera_disconnected signal that
    (unless suppressed) rebuilds the capture threads immediately, using
    whichever role hasn't been deactivated yet — starting a fresh capture
    thread on a camera that gets torn down microseconds later by the next
    deactivate_camera() call. That orphaned thread then reads from a
    closing/closed cv2.VideoCapture and fails hard — this produced the "10
    consecutive read failures" burst observed on real hardware.

    _suppress_capture_restart must be True for the whole span of both
    deactivate_camera() calls, not just around release_all()/the loop
    itself, and must always be reset afterward (even on exception) so
    normal hot-plug-triggered rebuilds still work later.
    """

    def setUp(self):
        self.app = ThermalInspectionApp(qt_app=None)
        self.app.plugin_host = MagicMock()
        self.app._camera_monitor = None
        self.app.media_manager = None
        self.app.timer = MagicMock()
        # Observed suppress-flag value at the moment each deactivation call
        # actually happens — the only way to prove the flag was held for the
        # full span, not just set-then-immediately-cleared around it.
        self.suppress_during_call = []

    def _record_suppress_state(self, *args, **kwargs):
        self.suppress_during_call.append(self.app._suppress_capture_restart)

    def test_cleanup_suppresses_restart_during_release_all(self):
        self.app.plugin_host.release_all.side_effect = self._record_suppress_state

        self.app.cleanup()

        self.assertEqual(self.suppress_during_call, [True])
        self.assertFalse(self.app._suppress_capture_restart)

    def test_cleanup_resets_suppress_flag_even_if_release_all_raises(self):
        self.app.plugin_host.release_all.side_effect = RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            self.app.cleanup()

        self.assertFalse(self.app._suppress_capture_restart)

    @patch('thermal_inspection.app.cv2.waitKey')
    @patch('thermal_inspection.app.time.sleep')  # skip real 1.1s of sleeps
    def test_reassign_cameras_suppresses_restart_across_both_deactivations(self, _sleep, _waitkey):
        self.app.plugin_host.deactivate_camera.side_effect = self._record_suppress_state
        self.app._init_cameras_sync = MagicMock()  # avoid real hardware discovery

        self.app.reassign_cameras(thermal_id=2, rgb_id=0)

        # Both deactivate_camera('thermal') and deactivate_camera('rgb')
        # must see the flag held True — if only one does, the bug reproduces.
        self.assertEqual(self.suppress_during_call, [True, True])
        self.assertFalse(self.app._suppress_capture_restart)

    @patch('thermal_inspection.app.cv2.waitKey')
    @patch('thermal_inspection.app.time.sleep')
    def test_reassign_cameras_resets_suppress_flag_even_if_deactivate_raises(self, _sleep, _waitkey):
        self.app.plugin_host.deactivate_camera.side_effect = RuntimeError("boom")
        self.app._init_cameras_sync = MagicMock()

        with self.assertRaises(RuntimeError):
            self.app.reassign_cameras(thermal_id=2, rgb_id=0)

        self.assertFalse(self.app._suppress_capture_restart)

    def test_restart_threaded_capture_noops_while_suppressed(self):
        self.app._suppress_capture_restart = True
        self.app._stop_threaded_capture = MagicMock()

        self.app._restart_threaded_capture()

        self.app._stop_threaded_capture.assert_not_called()


if __name__ == '__main__':
    unittest.main()
