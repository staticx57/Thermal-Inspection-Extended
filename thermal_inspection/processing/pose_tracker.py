"""
Pure camera-pose estimation for 3D Mapping Fusion (see world_mapper.py for
the orchestrator that drives this, and world_point_cloud.py for where the
tracked geometry actually lives). Knows nothing about how the world is
stored or rendered - just: given two RGB-D inputs (or an RGB-D frame plus a
target point cloud), what's the relative camera transform between them.

Two distinct tracking modes, matching two distinct Open3D algorithms:
- track_frame_to_frame: RGB-D odometry between two full color+depth images
  (scan phase, consecutive frames).
- track_frame_to_model: point-to-plane ICP of the current frame's point
  cloud against an already-built target point cloud with normals (live
  phase, tracking against the frozen world).
"""
from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np

from thermal_inspection.processing.open3d_support import get_open3d


class PoseTracker:
    def __init__(self, width: int, height: int, fx: float, fy: float, cx: float, cy: float):
        o3d = get_open3d()
        self.intrinsic = o3d.camera.PinholeCameraIntrinsic(width, height, fx, fy, cx, cy)
        self._odometry_option = o3d.pipelines.odometry.OdometryOption()

    def _to_rgbd(self, color_bgr: np.ndarray, depth_m: np.ndarray, max_depth_m: float):
        o3d = get_open3d()
        color_rgb = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2RGB)
        color_img = o3d.geometry.Image(np.ascontiguousarray(color_rgb))
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        return o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_img, depth_img, depth_scale=1.0, depth_trunc=max_depth_m,
            convert_rgb_to_intensity=False,
        )

    def track_frame_to_frame(self, color: np.ndarray, depth_m: np.ndarray,
                              prev_color: np.ndarray, prev_depth_m: np.ndarray,
                              init_transform: np.ndarray,
                              max_depth_m: float = 9.0) -> Tuple[bool, np.ndarray, float]:
        """RGB-D odometry from prev_color/prev_depth_m to color/depth_m.
        Returns (success, 4x4 transform, quality). On failure, transform is
        init_transform unchanged and quality is 0.0."""
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

    def track_frame_to_model(self, color: np.ndarray, depth_m: np.ndarray,
                              world_points: np.ndarray, world_normals: np.ndarray,
                              init_transform: np.ndarray,
                              max_correspondence_distance: float = 0.05) -> Tuple[bool, np.ndarray, float]:
        """Point-to-plane ICP of this frame's depth-derived point cloud
        against the frozen world (world_points/world_normals). Returns
        (success, 4x4 transform, fitness). On failure (fitness == 0),
        transform is init_transform unchanged."""
        o3d = get_open3d()
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        source_pcd = o3d.geometry.PointCloud.create_from_depth_image(
            depth_img, self.intrinsic, depth_scale=1.0, depth_trunc=9.0
        )
        target_pcd = o3d.geometry.PointCloud()
        target_pcd.points = o3d.utility.Vector3dVector(world_points)
        target_pcd.normals = o3d.utility.Vector3dVector(world_normals)

        result = o3d.pipelines.registration.registration_icp(
            source_pcd, target_pcd, max_correspondence_distance, init_transform,
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
        )
        if result.fitness <= 0.0:
            return False, init_transform, 0.0
        return True, np.asarray(result.transformation), float(result.fitness)
