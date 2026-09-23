import numpy as np
import pytest


class _FakeIntrinsic:
    """Fake camera intrinsic that supports get_focal_length() and get_principal_point()."""
    def __init__(self, fx, fy, cx, cy):
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy

    def get_focal_length(self):
        return self.fx, self.fy

    def get_principal_point(self):
        return self.cx, self.cy


class _FakePoseTracker:
    """Records calls, returns a canned (success, transform, quality)."""
    def __init__(self, width, height, fx, fy, cx, cy):
        self.init_args = (width, height, fx, fy, cx, cy)
        self.frame_to_frame_calls = 0
        self.frame_to_model_calls = 0
        self.next_result = (True, np.eye(4), 0.5)
        self.intrinsic = _FakeIntrinsic(fx, fy, cx, cy)

    def track_frame_to_frame(self, color, depth_m, prev_color, prev_depth_m, init_transform):
        self.frame_to_frame_calls += 1
        return self.next_result

    def track_frame_to_model(self, color, depth_m, world_points, world_normals, init_transform,
                              max_correspondence_distance=0.05):
        self.frame_to_model_calls += 1
        return self.next_result


class _FakeWorldPointCloud:
    def __init__(self, voxel_size=0.01):
        self.voxel_size = voxel_size
        self.frozen = False
        self.integrate_calls = 0
        self.update_colors_calls = 0
        self._point_count = 0
        self.points = np.zeros((0, 3))
        self.normals = np.zeros((0, 3))

    def integrate(self, color, depth_m, intrinsic, pose):
        self.integrate_calls += 1
        self._point_count += 10

    def freeze(self):
        self.frozen = True

    def update_colors(self, pose, texture_frame, intrinsic):
        self.update_colors_calls += 1
        return 5

    def reset(self):
        self.frozen = False
        self._point_count = 0

    @property
    def point_count(self):
        return self._point_count


def _make_mapper(**overrides):
    from thermal_inspection.processing.world_mapper import WorldMapper
    kwargs = dict(pose_tracker_factory=_FakePoseTracker, world_factory=_FakeWorldPointCloud)
    kwargs.update(overrides)
    return WorldMapper(**kwargs)


class TestStateMachine:
    def test_starts_idle(self):
        mapper = _make_mapper()
        assert mapper.state == "idle"

    def test_start_scan_transitions_to_scanning(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        assert mapper.state == "scanning"

    def test_finish_scan_transitions_to_mapped_and_freezes_world(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        assert mapper.state == "mapped"
        assert mapper.world.frozen

    def test_finish_scan_raises_when_not_scanning(self):
        mapper = _make_mapper()
        with pytest.raises(RuntimeError, match="scanning"):
            mapper.finish_scan()

    def test_reset_returns_to_idle(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper.reset()
        assert mapper.state == "idle"
        assert not mapper.world.frozen


class TestTrackAndTextureScanPhase:
    def test_calls_integrate_every_frame(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)

        mapper.track_and_texture(color, depth)
        mapper.track_and_texture(color, depth)

        assert mapper.world.integrate_calls == 2

    def test_raises_when_called_in_idle_state(self):
        mapper = _make_mapper()
        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        with pytest.raises(RuntimeError, match="idle"):
            mapper.track_and_texture(color, depth)


class TestTrackAndTextureLivePhase:
    def test_good_quality_updates_colors(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.5)  # >= good threshold

        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        mapper.track_and_texture(color, depth, texture_frame=color)

        assert mapper.world.update_colors_calls == 1
        assert mapper.quality_state == "good"

    def test_lost_quality_skips_color_update(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.02)  # below degraded threshold

        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        mapper.track_and_texture(color, depth, texture_frame=color)

        assert mapper.world.update_colors_calls == 0
        assert mapper.quality_state == "lost"

    def test_degraded_quality_still_updates_but_flags_degraded(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.2)  # between thresholds

        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        mapper.track_and_texture(color, depth, texture_frame=color)

        assert mapper.world.update_colors_calls == 1
        assert mapper.quality_state == "degraded"
