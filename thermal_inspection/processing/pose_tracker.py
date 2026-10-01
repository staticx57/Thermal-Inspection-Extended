"""
Pure camera-pose estimation for 3D Mapping Fusion (see world_mapper.py for
the orchestrator that drives this, and world_point_cloud.py for where the
tracked geometry actually lives). Knows nothing about how the world is
stored or rendered - just: given two RGB-D inputs (or an RGB-D frame plus a
target point cloud), what's the relative camera transform between them.

Three tracking operations, matching three Open3D algorithms:
- track_frame_to_frame: RGB-D odometry between two full color+depth images
  (scan phase, consecutive frames). Returns the SOURCE(previous)->TARGET(current)
  transform - the caller must invert it to advance a camera-to-world pose.
- track_frame_to_model: multi-scale, robust point-to-plane ICP of the current
  frame's depth cloud against the frozen world (live phase). Coarse-to-fine so
  it converges from a larger starting error than single-scale ICP can, and the
  world's per-scale targets are cached so each tick only pays for the frame.
- relocalize: global registration (FPFH features + RANSAC, then ICP refinement)
  to find the camera in the world from nothing - after loading a saved world,
  or when tracking has been lost. Much slower than tracking; callers run it off
  the frame loop.
"""
from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np

from thermal_inspection.processing.open3d_support import get_open3d

# Coarse -> fine ICP schedule: (voxel size m, max correspondence distance m, max iterations).
# The finest level's correspondence distance is the caller's max_correspondence_distance (default 0.05), the
# coarser ones are multiples of it, so the capture range (how far off the initial guess may be) is ~3x wider.
_ICP_SCHEDULE = ((0.04, 3.0, 25), (0.02, 1.6, 20), (0.01, 1.0, 15))


class PoseTracker:
    def __init__(self, width: int, height: int, fx: float, fy: float, cx: float, cy: float):
        o3d = get_open3d()
        self.intrinsic = o3d.camera.PinholeCameraIntrinsic(width, height, fx, fy, cx, cy)
        self._odometry_option = o3d.pipelines.odometry.OdometryOption()
        self._world_key = None          # identity of the world the cached targets were built from
        self._targets = None            # per-ICP-level downsampled target clouds (with normals)
        self._reloc_world_key = None
        self._reloc_target = None       # (downsampled target cloud, its FPFH features)

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    def _to_rgbd(self, color_bgr: np.ndarray, depth_m: np.ndarray, max_depth_m: float):
        o3d = get_open3d()
        color_rgb = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2RGB)
        color_img = o3d.geometry.Image(np.ascontiguousarray(color_rgb))
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        return o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_img, depth_img, depth_scale=1.0, depth_trunc=max_depth_m,
            convert_rgb_to_intensity=False,
        )

    def _depth_cloud(self, depth_m: np.ndarray, voxel: float, max_depth_m: float = 9.0):
        """This frame's depth as a point cloud in camera coordinates, voxel-downsampled."""
        o3d = get_open3d()
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        cloud = o3d.geometry.PointCloud.create_from_depth_image(
            depth_img, self.intrinsic, depth_scale=1.0, depth_trunc=max_depth_m
        )
        return cloud.voxel_down_sample(voxel) if voxel > 0 else cloud

    # ------------------------------------------------------------------
    # Scan phase
    # ------------------------------------------------------------------

    def track_frame_to_frame(self, color: np.ndarray, depth_m: np.ndarray,
                              prev_color: np.ndarray, prev_depth_m: np.ndarray,
                              init_transform: np.ndarray,
                              max_depth_m: float = 9.0) -> Tuple[bool, np.ndarray, float]:
        """RGB-D odometry between two frames.

        Returns (success, 4x4 transform, quality). The transform maps the PREVIOUS camera's coordinates into the
        CURRENT camera's (Open3D's source -> target): to advance a camera-to-world pose, use
        ``new_pose = old_pose @ inv(transform)``. On failure the transform is init_transform unchanged and quality
        is 0.0. quality is the trace of Open3D's information matrix - larger means better-constrained, but it is
        not bounded, so compare it against earlier frames rather than against a fixed number."""
        o3d = get_open3d()
        source_rgbd = self._to_rgbd(prev_color, prev_depth_m, max_depth_m)
        target_rgbd = self._to_rgbd(color, depth_m, max_depth_m)
        success, transform, info = o3d.pipelines.odometry.compute_rgbd_odometry(
            source_rgbd, target_rgbd, self.intrinsic, init_transform,
            o3d.pipelines.odometry.RGBDOdometryJacobianFromHybridTerm(),
            self._odometry_option,
        )
        if not success:
            return False, init_transform, 0.0
        quality = float(np.trace(np.asarray(info)))
        return True, np.asarray(transform), quality

    # ------------------------------------------------------------------
    # Live phase
    # ------------------------------------------------------------------

    def _target_levels(self, world_points: np.ndarray, world_normals: np.ndarray, world_key, scale: float):
        """Per-level downsampled target clouds, cached for as long as world_key is unchanged."""
        key = (world_key, round(scale, 3))
        if world_key is not None and self._targets is not None and self._world_key == key:
            return self._targets
        o3d = get_open3d()
        full = o3d.geometry.PointCloud()
        full.points = o3d.utility.Vector3dVector(np.asarray(world_points, dtype=np.float64))
        full.normals = o3d.utility.Vector3dVector(np.asarray(world_normals, dtype=np.float64))
        levels = []
        for voxel, _, _ in _ICP_SCHEDULE:
            levels.append(full.voxel_down_sample(voxel * scale))
        self._targets, self._world_key = levels, key
        return levels

    def track_frame_to_model(self, color: np.ndarray, depth_m: np.ndarray,
                              world_points: np.ndarray, world_normals: np.ndarray,
                              init_transform: np.ndarray,
                              max_correspondence_distance: float = 0.05,
                              world_key=None) -> Tuple[bool, np.ndarray, float]:
        """Multi-scale point-to-plane ICP of this frame's depth against the frozen world.

        Returns (success, camera-to-world 4x4, fitness) where fitness (0-1) is the fraction of this frame's points
        that find a world surface within max_correspondence_distance at the finest scale. On failure
        (fitness == 0) the transform is init_transform unchanged. Pass a world_key that changes whenever the
        world's points do (WorldPointCloud.revision) to reuse the per-scale targets between calls.
        """
        o3d = get_open3d()
        reg = o3d.pipelines.registration
        scale = max_correspondence_distance / 0.05
        targets = self._target_levels(world_points, world_normals, world_key, scale)
        estimation = reg.TransformationEstimationPointToPlane(reg.TukeyLoss(k=max_correspondence_distance))

        transform = np.asarray(init_transform, dtype=np.float64)
        result = None
        for (voxel, corr, iters), target in zip(_ICP_SCHEDULE, targets):
            if len(target.points) == 0:
                continue
            source = self._depth_cloud(depth_m, voxel * scale)
            if len(source.points) == 0:
                return False, init_transform, 0.0
            result = reg.registration_icp(
                source, target, max_correspondence_distance * corr, transform, estimation,
                reg.ICPConvergenceCriteria(max_iteration=iters),
            )
            transform = np.asarray(result.transformation)
        if result is None or result.fitness <= 0.0:
            return False, init_transform, 0.0
        return True, transform, float(result.fitness)

    # ------------------------------------------------------------------
    # Re-localization
    # ------------------------------------------------------------------

    def _reloc_features(self, world_points, world_normals, world_key, voxel):
        o3d = get_open3d()
        if world_key is not None and self._reloc_target is not None and self._reloc_world_key == (world_key, voxel):
            return self._reloc_target
        full = o3d.geometry.PointCloud()
        full.points = o3d.utility.Vector3dVector(np.asarray(world_points, dtype=np.float64))
        target = full.voxel_down_sample(voxel)
        target.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2.0, max_nn=30))
        features = o3d.pipelines.registration.compute_fpfh_feature(
            target, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5.0, max_nn=100))
        self._reloc_target, self._reloc_world_key = (target, features), (world_key, voxel)
        return self._reloc_target

    def relocalize(self, depth_m: np.ndarray, world_points: np.ndarray, world_normals: np.ndarray,
                   world_key=None, voxel: float = 0.05,
                   min_fitness: float = 0.3) -> Tuple[bool, Optional[np.ndarray], float]:
        """Find the camera in the world from scratch (no initial guess).

        Global registration - FPFH feature matching with RANSAC - gives a coarse camera-to-world pose, refined by
        ICP. Returns (success, pose, fitness); success needs a refined fitness of at least min_fitness. Takes from
        a few hundred milliseconds to a few seconds depending on the world's size, so it belongs off the frame loop
        (WorldMapper runs it in a worker thread).
        """
        o3d = get_open3d()
        reg = o3d.pipelines.registration
        source = self._depth_cloud(depth_m, voxel)
        if len(source.points) < 200:
            return False, None, 0.0
        source.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2.0, max_nn=30))
        source_fpfh = reg.compute_fpfh_feature(
            source, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5.0, max_nn=100))
        target, target_fpfh = self._reloc_features(world_points, world_normals, world_key, voxel)
        if len(target.points) < 200:
            return False, None, 0.0

        distance = voxel * 1.5
        coarse = reg.registration_ransac_based_on_feature_matching(
            source, target, source_fpfh, target_fpfh, True, distance,
            reg.TransformationEstimationPointToPoint(False), 3,
            [reg.CorrespondenceCheckerBasedOnEdgeLength(0.9), reg.CorrespondenceCheckerBasedOnDistance(distance)],
            reg.RANSACConvergenceCriteria(60000, 0.999),
        )
        if coarse.fitness <= 0.0:
            return False, None, 0.0
        ok, refined, fitness = self.track_frame_to_model(
            np.zeros((1, 1, 3), np.uint8), depth_m, world_points, world_normals,
            np.asarray(coarse.transformation), world_key=world_key,
        )
        if not ok or fitness < min_fitness:
            return False, None, float(fitness)
        return True, refined, float(fitness)
