"""
Task 6 (3D Mapping Fusion end-to-end wiring): unit-level coverage for
InspectionAppWindow's `_on_mapping_start_scan` handler and the
set_mapping_fusion_status/update_mapping_fusion_view forwarding methods.

The critical case here is `_on_mapping_start_scan` catching the
ImportError that WorldMapper.start_scan() propagates from PoseTracker's
own __init__ (see thermal_inspection/processing/open3d_support.py's
get_open3d()) when Open3D isn't installed. This development environment
genuinely does not have open3d installed, so this test exercises the
REAL PoseTracker class and the REAL get_open3d() ImportError - not a
mock of the failure - while stubbing everything else (no full QMainWindow
construction needed, following test_thermal_analysis_push_throttle.py's
"call the method unbound against a lightweight stand-in" pattern).
"""
from unittest.mock import MagicMock

import numpy as np

from thermal_inspection.gui.main_window import InspectionAppWindow as MainWindow
from thermal_inspection.processing.world_mapper import WorldMapper


class _FakeRealSenseBackend:
    """Exposes only get_depth_intrinsics(), as app.rgb_camera's real
    RealSense backend does."""

    def get_depth_intrinsics(self):
        return {"width": 640, "height": 480, "fx": 500.0, "fy": 500.0, "cx": 320.0, "cy": 240.0}


class _FakeApp:
    def __init__(self, rgb_camera=None, world_mapper=None):
        self.rgb_camera = rgb_camera
        self.world_mapper = world_mapper if world_mapper is not None else WorldMapper()
        self._mapping_texture_source = "thermal"


class _FakeMainWindow:
    """Bare stand-in exposing only what the mapping-fusion handlers touch."""

    def __init__(self, app):
        self.app = app
        self.mapping_fusion_panel = MagicMock()


class TestMappingStartScanImportErrorHandling:
    def test_start_scan_without_open3d_does_not_raise(self):
        """The real regression this test guards against: PoseTracker()
        raises ImportError (open3d not installed) inside
        WorldMapper.start_scan() - _on_mapping_start_scan must catch it,
        not let it propagate and crash the app."""
        fake = _FakeMainWindow(_FakeApp(rgb_camera=_FakeRealSenseBackend()))

        MainWindow._on_mapping_start_scan(fake)  # must not raise

        assert fake.app.world_mapper.state == "idle", (
            "start_scan must not have flipped state - it failed before "
            "reaching the state assignment"
        )

    def test_start_scan_surfaces_import_error_as_status_message(self):
        fake = _FakeMainWindow(_FakeApp(rgb_camera=_FakeRealSenseBackend()))

        MainWindow._on_mapping_start_scan(fake)

        fake.mapping_fusion_panel.set_status.assert_called_once_with("idle", "n/a", 0)
        set_text_calls = fake.mapping_fusion_panel._status_label.setText.call_args_list
        assert len(set_text_calls) == 1
        message = set_text_calls[0][0][0]
        assert "open3d" in message.lower()

    def test_start_scan_with_no_realsense_camera_does_not_raise(self):
        """No depth intrinsics available (no RealSense hardware) - a
        distinct failure mode from the ImportError case, must also not
        propagate or crash."""
        fake = _FakeMainWindow(_FakeApp(rgb_camera=None))

        MainWindow._on_mapping_start_scan(fake)  # must not raise

        assert fake.app.world_mapper.state == "idle"

    def test_start_scan_succeeds_with_a_working_pose_tracker_factory(self):
        """Sanity check the happy path still works when PoseTracker
        construction succeeds (simulated here since open3d isn't
        installed) - state must flip to 'scanning'.

        I7: the handler must ALSO push a status update immediately (not
        just rely on the next frame-loop tick, which only runs while
        THREE_D_MAPPING is the active view mode) - so unlike the failure
        paths above, set_status IS expected to be called here now, with
        the fresh post-start_scan state.
        """
        working_world_mapper = WorldMapper(pose_tracker_factory=MagicMock())
        fake = _FakeMainWindow(_FakeApp(
            rgb_camera=_FakeRealSenseBackend(), world_mapper=working_world_mapper,
        ))

        MainWindow._on_mapping_start_scan(fake)

        assert fake.app.world_mapper.state == "scanning"
        fake.mapping_fusion_panel.set_status.assert_called_once_with("scanning", "n/a", 0)


class TestMappingLoadWorld:
    def test_load_without_open3d_does_not_raise(self):
        """WorldPointCloud.load() (and PoseTracker construction) raises
        ImportError when open3d isn't installed - this genuinely-missing
        environment exercises the real ImportError, not a mock of it."""
        fake = _FakeMainWindow(_FakeApp(rgb_camera=_FakeRealSenseBackend()))

        MainWindow._load_mapping_world_from_path(fake, "world.ply")  # must not raise

        assert fake.app.world_mapper.state == "idle"

    def test_load_surfaces_import_error_as_status_message(self):
        fake = _FakeMainWindow(_FakeApp(rgb_camera=_FakeRealSenseBackend()))

        MainWindow._load_mapping_world_from_path(fake, "world.ply")

        fake.mapping_fusion_panel.set_status.assert_called_once_with("idle", "n/a", 0)
        message = fake.mapping_fusion_panel._status_label.setText.call_args_list[0][0][0]
        assert "open3d" in message.lower()

    def test_load_with_no_realsense_camera_does_not_raise(self):
        """No depth intrinsics available - must surface a clear status
        message instead of loading into a world with no working
        PoseTracker (live tracking would silently never work)."""
        fake = _FakeMainWindow(_FakeApp(rgb_camera=None))

        MainWindow._load_mapping_world_from_path(fake, "world.ply")  # must not raise

        assert fake.app.world_mapper.state == "idle"
        message = fake.mapping_fusion_panel._status_label.setText.call_args_list[0][0][0]
        assert "realsense" in message.lower()

    def test_load_succeeds_with_a_working_pose_tracker_factory(self):
        """Happy path: state flips to 'mapped' AND a real PoseTracker gets
        constructed (the actual C1/I4 regression - without
        WorldMapper.load_from_path(), _pose_tracker stayed None forever
        after Load). Stubs world_factory too, since the real
        WorldPointCloud.load() also needs open3d - not installed here."""
        class _FakeWorld:
            def __init__(self, voxel_size=0.01):
                self.loaded_path = None
                self.point_count = 0

            def load(self, path):
                self.loaded_path = path

        working_world_mapper = WorldMapper(pose_tracker_factory=MagicMock(), world_factory=_FakeWorld)
        fake = _FakeMainWindow(_FakeApp(
            rgb_camera=_FakeRealSenseBackend(), world_mapper=working_world_mapper,
        ))

        MainWindow._load_mapping_world_from_path(fake, "world.ply")

        assert fake.app.world_mapper.state == "mapped"
        assert fake.app.world_mapper._pose_tracker is not None
        assert fake.app.world_mapper.world.loaded_path == "world.ply"
        # quality_state buckets a fresh tracking_quality of 0.0 as "lost"
        # (state is "mapped" now, so quality_state no longer reports
        # "n/a") - the honest "no live tracking sample yet" state until
        # the next real tick overwrites it.
        fake.mapping_fusion_panel.set_status.assert_called_once_with("mapped", "lost", 0)


class TestMappingFusionForwardingMethods:
    def test_set_mapping_fusion_status_forwards_to_panel(self):
        fake = _FakeMainWindow(_FakeApp())

        MainWindow.set_mapping_fusion_status(fake, "mapped", "good", 12345)

        fake.mapping_fusion_panel.set_status.assert_called_once_with("mapped", "good", 12345)

    def test_update_mapping_fusion_view_converts_rgb_to_rgba(self):
        fake = _FakeMainWindow(_FakeApp())
        points = np.zeros((5, 3), dtype=np.float64)
        colors_rgb = np.full((5, 3), 0.5, dtype=np.float64)

        MainWindow.update_mapping_fusion_view(fake, points, colors_rgb)

        fake.mapping_fusion_panel.update_point_cloud.assert_called_once()
        call_points, call_colors = fake.mapping_fusion_panel.update_point_cloud.call_args[0]
        assert call_points.dtype == np.float32
        assert call_points.shape == (5, 3)
        assert call_colors.dtype == np.float32
        assert call_colors.shape == (5, 4)
        assert np.allclose(call_colors[:, :3], 0.5)
        assert np.allclose(call_colors[:, 3], 1.0)  # alpha always opaque


class TestMappingSimpleForwardingHandlers:
    def test_finish_scan_forwards_to_world_mapper(self):
        world_mapper = MagicMock()
        fake = _FakeMainWindow(_FakeApp(world_mapper=world_mapper))

        MainWindow._on_mapping_finish_scan(fake)

        world_mapper.finish_scan.assert_called_once_with()

    def test_reset_forwards_to_world_mapper(self):
        world_mapper = MagicMock()
        fake = _FakeMainWindow(_FakeApp(world_mapper=world_mapper))

        MainWindow._on_mapping_reset(fake)

        world_mapper.reset.assert_called_once_with()

    def test_texture_source_changed_updates_app_attribute(self):
        fake = _FakeMainWindow(_FakeApp())

        MainWindow._on_mapping_texture_source_changed(fake, "rgb")

        assert fake.app._mapping_texture_source == "rgb"
