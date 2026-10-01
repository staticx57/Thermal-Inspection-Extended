"""
3D Mapping geometry against ground truth (needs the real Open3D library).

Every test here uses a synthetic scene rendered from known camera poses, so the assertions are about real geometry -
pose direction, map accuracy, tracking recovery - not just "it ran".
"""
import time

import numpy as np
import pytest

from thermal_inspection.processing.open3d_support import OPEN3D_AVAILABLE

pytestmark = pytest.mark.skipif(not OPEN3D_AVAILABLE, reason="open3d not installed")

from tests.unit.mapping_synth import (  # noqa: E402
    CX, CY, FX, FY, H, PLANES, TRAJECTORY, W, live_track, mapped_world, pose, pose_error, render, scan,
)


def _distance_to_planes(points):
    d = np.full(len(points), np.inf)
    for p0, n in PLANES:
        n = n / np.linalg.norm(n)
        d = np.minimum(d, np.abs((points - p0) @ n))
    return d


class TestOdometryDirection:
    def test_frame_to_frame_returns_the_source_to_target_transform(self):
        """Open3D's odometry maps the *source* (previous) camera frame into the *target* (current) one."""
        from thermal_inspection.processing.pose_tracker import PoseTracker
        tracker = PoseTracker(W, H, FX, FY, CX, CY)
        p0, p1 = pose(), pose(tx=0.06, yaw_deg=2.0)
        c0, d0 = render(p0, noise=0.002)
        c1, d1 = render(p1, noise=0.002, seed=1)
        ok, T, _ = tracker.track_frame_to_frame(c1, d1, c0, d0, np.eye(4))
        assert ok
        assert np.abs(T - np.linalg.inv(p1) @ p0).max() < 0.01


class TestScanPhase:
    def test_estimated_trajectory_matches_ground_truth(self):
        """The bug this pins down: the mapper composed odometry the wrong way round, so a moving camera produced a
        mirrored trajectory (x = -truth). Identical-frame tests could never see it."""
        _, poses = scan(TRAJECTORY)
        for est, truth in zip(poses, TRAJECTORY):
            trans, rot = pose_error(est, truth)
            assert trans < 0.02 and rot < 1.0, f"pose off by {trans:.3f} m / {rot:.2f} deg"

    def test_scanned_map_lies_on_the_real_surfaces(self):
        wm, _ = scan(TRAJECTORY)
        points = wm.world.points
        assert len(points) > 2000
        dist = _distance_to_planes(points)
        assert np.percentile(dist, 95) < 0.03, "a correct map hugs the true planes; a smeared one does not"

    def test_a_frame_odometry_cannot_track_is_not_integrated(self):
        """A blank frame has nothing to lock onto: integrating it at the stale pose would smear the map."""
        wm, _ = scan(TRAJECTORY[:3])
        before = wm.point_count
        pose_before = wm._pose.copy()
        wm.track_and_texture(np.zeros((H, W, 3), np.uint8), np.zeros((H, W), np.float32))
        assert wm.point_count == before
        assert np.allclose(wm._pose, pose_before)
        assert "tracking lost" in wm.status_message.lower()

    def test_tracking_recovers_when_the_camera_returns_to_the_last_good_view(self):
        wm, poses = scan(TRAJECTORY[:4])
        wm.track_and_texture(np.zeros((H, W, 3), np.uint8), np.zeros((H, W), np.float32))   # lost for a frame
        color, depth = render(TRAJECTORY[4], noise=0.002, seed=9)                           # next real view
        wm.track_and_texture(color, depth)
        trans, rot = pose_error(wm._pose, TRAJECTORY[4])
        assert trans < 0.05 and rot < 1.5
        assert "tracking lost" not in wm.status_message.lower()

    def test_a_frame_with_almost_no_valid_depth_counts_as_lost_even_if_odometry_claims_success(self):
        """Open3D can report odometry 'success' on an all-zero frame; there is nothing to track."""
        wm, _ = scan(TRAJECTORY[:3])
        wm.track_and_texture(np.zeros((H, W, 3), np.uint8), np.zeros((H, W), np.float32))
        assert "tracking lost" in wm.status_message.lower()


class TestLiveTracking:
    def test_freeze_gives_the_world_normals(self):
        wm, _ = mapped_world()
        assert wm.world.frozen
        assert len(wm.world.normals) == len(wm.world.points) > 0

    def test_tracks_a_camera_that_moved_a_little(self):
        wm, poses = mapped_world()
        moved = poses[-1] @ pose(tx=0.04, ty=-0.02, yaw_deg=1.5)
        est = live_track(wm, moved)
        trans, rot = pose_error(est, moved)
        assert wm.quality_state in ("good", "degraded")
        assert trans < 0.02 and rot < 1.0, f"{trans:.3f} m / {rot:.2f} deg"

    def test_follows_a_sequence_of_small_moves(self):
        wm, poses = mapped_world()
        truth = poses[-1]
        for i in range(6):
            truth = truth @ pose(tx=0.025, yaw_deg=1.0)
            est = live_track(wm, truth, seed=60 + i)
            trans, rot = pose_error(est, truth)
            assert trans < 0.03 and rot < 1.5, f"step {i}: {trans:.3f} m / {rot:.2f} deg"

    def test_multi_scale_icp_captures_a_larger_jump_than_the_finest_distance(self):
        """Single-scale ICP with a 5 cm correspondence distance cannot recover an 8 cm shift; the coarse-to-fine
        schedule widens the capture range."""
        wm, poses = mapped_world()
        moved = poses[-1] @ pose(tx=0.08, ty=0.03, yaw_deg=2.0)
        est = live_track(wm, moved)
        trans, rot = pose_error(est, moved)
        assert trans < 0.025 and rot < 1.5, f"{trans:.3f} m / {rot:.2f} deg"

    def test_the_map_geometry_does_not_change_while_tracking(self):
        wm, poses = mapped_world()
        before = np.array(wm.world.points, copy=True)
        live_track(wm, poses[-1] @ pose(tx=0.03))
        assert np.array_equal(before, wm.world.points)

    def test_a_view_with_no_overlap_is_reported_lost_and_the_pose_is_kept(self):
        wm, _ = mapped_world()
        kept = wm._pose.copy()
        color = np.full((H, W, 3), 128, np.uint8)
        depth = np.full((H, W), 8.5, np.float32)           # a flat slab far from anything mapped
        wm.track_and_texture(color, depth, texture_frame=color)
        assert wm.quality_state == "lost"
        assert np.allclose(wm._pose, kept), "a lost frame must not move the camera estimate"


class TestImplausibleJumps:
    def test_a_huge_jump_from_a_wrong_initial_guess_is_not_accepted_as_tracking(self):
        """ICP on big flat surfaces can slide along a plane to a wrong answer with a respectable fitness. A step of
        metres between two ticks is impossible motion, so it must count as lost (and trigger re-localization)."""
        from thermal_inspection.processing.world_mapper import WorldMapper
        wm, poses = mapped_world()
        other = WorldMapper(voxel_size=0.02, relocalize_async=False, relocalize_after_lost_ticks=99)
        other.state, other.world, other._pose_tracker = "mapped", wm.world, wm._pose_tracker
        wrong = pose(tx=1.5)
        other._pose = wrong.copy()
        live_track(other, poses[-1], seed=93)
        assert np.allclose(other._pose, wrong), "the pose must not jump metres on a single tick"
        assert other.quality_state == "lost"

    def test_a_small_step_is_still_accepted(self):
        wm, poses = mapped_world()
        est = live_track(wm, poses[-1] @ pose(tx=0.05, yaw_deg=2.0))
        assert wm.quality_state in ("good", "degraded")
        assert pose_error(est, poses[-1] @ pose(tx=0.05, yaw_deg=2.0))[0] < 0.03


class TestRecolouring:
    def test_world_takes_the_live_texture_colours(self):
        wm, poses = mapped_world()
        before = np.array(wm.world.colors, copy=True)
        color, depth = render(poses[-1], noise=0.002, seed=70)
        wm.track_and_texture(color, depth, texture_frame=255 - color)
        after = wm.world.colors
        changed = np.abs(after - before).sum(axis=1) > 1e-6
        assert changed.mean() > 0.2
        assert np.abs(after - before).max() > 0.2

    def test_points_hidden_behind_a_nearer_surface_are_not_painted_with_its_colour(self):
        """No occlusion test = a point behind the front surface projects to the same pixel and steals its colour."""
        from thermal_inspection.processing.open3d_support import get_open3d
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        o3d = get_open3d()
        intr = o3d.camera.PinholeCameraIntrinsic(W, H, FX, FY, CX, CY)
        world = WorldPointCloud(voxel_size=0.01)
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 2.0]]))   # near, and behind it
        pcd.colors = o3d.utility.Vector3dVector(np.zeros((2, 3)))
        world._pcd = pcd
        texture = np.full((H, W, 3), 255, np.uint8)
        depth = np.full((H, W), 1.0, np.float32)            # the camera sees the near surface at 1 m
        updated = world.update_colors(np.eye(4), texture, intr, depth_m=depth)
        colors = world.colors
        assert updated == 1
        assert colors[0].sum() > 2.9 and colors[1].sum() == 0.0

    def test_without_depth_behaviour_is_unchanged(self):
        from thermal_inspection.processing.open3d_support import get_open3d
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        o3d = get_open3d()
        intr = o3d.camera.PinholeCameraIntrinsic(W, H, FX, FY, CX, CY)
        world = WorldPointCloud()
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 2.0]]))
        world._pcd = pcd
        assert world.update_colors(np.eye(4), np.full((H, W, 3), 255, np.uint8), intr) == 2


class TestPersistenceAndRelocalization:
    def test_save_load_round_trip_keeps_geometry_colours_and_normals(self, tmp_path):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        wm, _ = mapped_world()
        path = str(tmp_path / "world.ply")
        wm.world.save(path)
        loaded = WorldPointCloud()
        loaded.load(path)
        assert loaded.frozen and loaded.point_count == wm.world.point_count
        assert np.allclose(np.sort(loaded.points, axis=0), np.sort(wm.world.points, axis=0), atol=1e-4)
        assert len(loaded.normals) == loaded.point_count
        assert loaded.colors.shape == wm.world.colors.shape

    def test_a_world_saved_without_normals_gets_them_on_load(self, tmp_path):
        from thermal_inspection.processing.open3d_support import get_open3d
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        o3d = get_open3d()
        wm, _ = mapped_world()
        bare = o3d.geometry.PointCloud()
        bare.points = o3d.utility.Vector3dVector(wm.world.points)
        path = str(tmp_path / "bare.ply")
        o3d.io.write_point_cloud(path, bare)
        loaded = WorldPointCloud()
        loaded.load(path)
        assert len(loaded.normals) == loaded.point_count

    def test_saving_an_empty_world_raises_a_clear_error(self, tmp_path):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        with pytest.raises(ValueError):
            WorldPointCloud().save(str(tmp_path / "empty.ply"))

    def test_loading_a_missing_file_raises(self, tmp_path):
        from thermal_inspection.processing.world_point_cloud import WorldPointCloud
        with pytest.raises((ValueError, OSError, RuntimeError)):
            WorldPointCloud().load(str(tmp_path / "nope.ply"))

    def test_relocalizes_after_load_from_a_different_pose(self, tmp_path):
        """A loaded world has no known camera pose. ICP from the origin cannot find a camera pointing elsewhere;
        global registration must."""
        from thermal_inspection.processing.world_mapper import WorldMapper
        wm, poses = mapped_world()
        path = str(tmp_path / "world.ply")
        wm.world.save(path)

        fresh = WorldMapper(voxel_size=0.02, relocalize_async=False, relocalize_after_lost_ticks=1)
        fresh.load_from_path(path, W, H, FX, FY, CX, CY)
        assert fresh.state == "mapped"
        true_pose = poses[-1]
        est = None
        for i in range(3):                                  # ICP attempt, then re-localization, then tracking
            est = live_track(fresh, true_pose, seed=80 + i)
        trans, rot = pose_error(est, true_pose)
        assert fresh.quality_state in ("good", "degraded"), fresh.quality_state
        assert trans < 0.05 and rot < 3.0, f"{trans:.3f} m / {rot:.2f} deg"

    def test_relocalization_runs_off_the_frame_loop_and_is_applied_when_ready(self):
        from thermal_inspection.processing.world_mapper import WorldMapper
        wm, poses = mapped_world()
        other = WorldMapper(voxel_size=0.02, relocalize_after_lost_ticks=1)        # asynchronous by default
        other.state, other.world, other._pose_tracker = "mapped", wm.world, wm._pose_tracker
        other._pose = pose(tx=1.5)                                                   # a badly wrong starting guess
        true_pose = poses[-1]
        live_track(other, true_pose, seed=90)                # tick 1: ICP fails -> starts the background worker
        deadline = time.time() + 30
        while other.relocalizing and time.time() < deadline:
            time.sleep(0.05)
        assert not other.relocalizing, "re-localization did not finish"
        est = live_track(other, true_pose, seed=91)          # next tick applies the result and tracks
        trans, rot = pose_error(est, true_pose)
        assert trans < 0.05 and rot < 3.0, f"{trans:.3f} m / {rot:.2f} deg"

    def test_a_result_from_before_a_reset_is_dropped(self):
        from thermal_inspection.processing.world_mapper import WorldMapper
        wm, poses = mapped_world()
        other = WorldMapper(voxel_size=0.02, relocalize_after_lost_ticks=1)
        other.state, other.world, other._pose_tracker = "mapped", wm.world, wm._pose_tracker
        other._pose = pose(tx=1.5)
        live_track(other, poses[-1], seed=92)                # starts a worker...
        other._reset_tracking_state()                        # ...then the scan is reset underneath it
        time.sleep(1.0)
        with other._reloc_lock:
            assert other._reloc_result is None


class TestWorkingResolution:
    def test_large_frames_are_tracked_at_a_reduced_resolution_with_scaled_intrinsics(self):
        from thermal_inspection.processing.world_mapper import WorldMapper
        big = 4                                              # frames 4x the working width cap below
        wm = WorldMapper(voxel_size=0.02, max_working_width=W)
        wm.start_scan(W * big, H * big, FX * big, FY * big, CX * big, CY * big)
        intr = wm._pose_tracker.intrinsic
        assert (intr.width, intr.height) == (W, H)
        assert np.allclose(intr.get_focal_length(), (FX, FY), atol=1e-6)
        for est_truth in TRAJECTORY[:5]:
            color, depth = render(est_truth, noise=0.002, seed=3, scale=big)
            wm.track_and_texture(color, depth)
            trans, rot = pose_error(wm._pose, est_truth)
            assert trans < 0.03 and rot < 1.5
