import numpy as np
import pytest


class _FakeIntrinsic:
    """Fake camera intrinsic that supports get_focal_length(),
    get_principal_point(), and the .width/.height attributes real
    Open3D PinholeCameraIntrinsic objects expose (see C3 fix in
    WorldMapper.track_and_texture, which resizes texture_frame to match
    these before handing it to WorldPointCloud.update_colors)."""
    def __init__(self, width, height, fx, fy, cx, cy):
        self.width = width
        self.height = height
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
        self.intrinsic = _FakeIntrinsic(width, height, fx, fy, cx, cy)

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
        self.colors = np.zeros((0, 3))
        self.last_texture_shape = None
        self.loaded_path = None

    def integrate(self, color, depth_m, intrinsic, pose):
        self.integrate_calls += 1
        self._point_count += 10

    def freeze(self):
        self.frozen = True

    def update_colors(self, pose, texture_frame, intrinsic):
        self.update_colors_calls += 1
        self.last_texture_shape = texture_frame.shape
        return 5

    def reset(self):
        self.frozen = False
        self._point_count = 0

    def load(self, path):
        self.loaded_path = path
        self.frozen = True
        self._point_count = 42

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


class TestTextureResolutionMatchesIntrinsic:
    """C3: WorldPointCloud.update_colors() projects points using the
    intrinsic's own (fx, fy, cx, cy) and indexes into texture_frame using
    texture_frame.shape - those must agree on resolution, or points get
    sampled from the wrong pixels with no error at all. This test uses a
    texture_frame at a DIFFERENT resolution than the intrinsic captured at
    start_scan() - exactly the real-world case (colorized_thermal at the
    thermal camera's native size vs. RealSense's color-stream intrinsic) -
    and asserts WorldMapper resizes it before handing it to
    WorldPointCloud.update_colors()."""

    def test_mismatched_texture_is_resized_to_intrinsic_resolution(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)  # intrinsic: 64x48
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.5)

        depth = np.ones((48, 64), dtype=np.float32)
        color = np.zeros((48, 64, 3), dtype=np.uint8)
        # Deliberately a completely different resolution from the 64x48
        # intrinsic - this is the bug: a thermal-resolution texture handed
        # to a RealSense-color-resolution intrinsic's u/v math.
        mismatched_texture = np.zeros((512, 640, 3), dtype=np.uint8)

        mapper.track_and_texture(color, depth, texture_frame=mismatched_texture)

        assert mapper.world.update_colors_calls == 1
        # (height, width, channels) - must match the intrinsic (64x48), not
        # the texture_frame's original (640x512) shape.
        assert mapper.world.last_texture_shape[:2] == (48, 64)

    def test_already_matching_texture_is_left_alone(self):
        mapper = _make_mapper(quality_good_threshold=0.3, quality_degraded_threshold=0.1)
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.finish_scan()
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.5)

        depth = np.ones((48, 64), dtype=np.float32)
        color = np.zeros((48, 64, 3), dtype=np.uint8)
        matching_texture = np.full((48, 64, 3), 7, dtype=np.uint8)

        mapper.track_and_texture(color, depth, texture_frame=matching_texture)

        assert mapper.world.last_texture_shape == (48, 64, 3)


class TestFinishScanResetsTrackingQuality:
    """I8: scan-phase quality (np.trace of an odometry info matrix -
    unbounded, typically thousands) and live-phase quality (ICP fitness,
    0-1) are incomparable numbers compared against the same thresholds.
    finish_scan() must reset tracking_quality so a huge stale scan-phase
    number never briefly reads as a false 'good' before the first live
    tick overwrites it."""

    def test_finish_scan_resets_quality_to_zero(self):
        mapper = _make_mapper()
        mapper.start_scan(64, 48, 50.0, 50.0, 32.0, 24.0)
        # Simulate a real scan-phase quality value - large, unbounded,
        # nowhere near the 0-1 ICP fitness scale.
        mapper.tracking_quality = 4321.0

        mapper.finish_scan()

        assert mapper.tracking_quality == 0.0
        # Bucketed as "lost" (honest: no live sample yet), never a
        # leftover false "good" from the scan-phase number.
        assert mapper.quality_state == "lost"


class TestLoadFromPath:
    """I4: the Load path must construct a working PoseTracker, not just
    load geometry and flip state - otherwise every live track_and_texture()
    call after Load hits self._pose_tracker.track_frame_to_model() on
    None."""

    def test_load_from_path_constructs_pose_tracker_and_sets_mapped(self):
        mapper = _make_mapper()

        mapper.load_from_path("world.ply", 64, 48, 50.0, 50.0, 32.0, 24.0)

        assert mapper.state == "mapped"
        assert mapper.world.loaded_path == "world.ply"
        assert mapper._pose_tracker is not None
        assert mapper._pose_tracker.init_args == (64, 48, 50.0, 50.0, 32.0, 24.0)

    def test_live_tracking_works_immediately_after_load(self):
        """The actual regression: track_and_texture() in the 'mapped'
        branch must not raise/AttributeError right after Load."""
        mapper = _make_mapper()
        mapper.load_from_path("world.ply", 64, 48, 50.0, 50.0, 32.0, 24.0)
        mapper.world.points = np.zeros((10, 3))
        mapper.world.normals = np.zeros((10, 3))
        mapper._pose_tracker.next_result = (True, np.eye(4), 0.5)

        color = np.zeros((48, 64, 3), dtype=np.uint8)
        depth = np.ones((48, 64), dtype=np.float32)
        mapper.track_and_texture(color, depth, texture_frame=color)  # must not raise

        assert mapper.quality_state == "good"
