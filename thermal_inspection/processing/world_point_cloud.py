"""
Accumulated/frozen world geometry for 3D Mapping Fusion. Owns point
positions, colors, and normals - integration during the scan phase,
per-vertex color re-sampling during the live phase, and PLY persistence.
Knows nothing about odometry (see pose_tracker.py for that) or the
scan/track/freeze state machine (see world_mapper.py for that).
"""
from __future__ import annotations

import numpy as np

from thermal_inspection.processing.open3d_support import get_open3d


class WorldPointCloud:
    def __init__(self, voxel_size: float = 0.01):
        # Deliberately does NOT call get_open3d() here - WorldMapper
        # constructs a WorldPointCloud eagerly at app startup regardless of
        # whether the user ever touches 3D Mapping Fusion, so this
        # constructor must succeed even when open3d isn't installed at all
        # (see the Global Constraints' "graceful placeholder, not a hard
        # failure" requirement). The actual o3d.geometry.PointCloud only
        # gets created in _ensure_pcd(), called from methods that need it -
        # those are only reached once the user explicitly starts a scan.
        self.voxel_size = voxel_size
        self._pcd = None
        self.frozen = False

    def _ensure_pcd(self):
        if self._pcd is None:
            o3d = get_open3d()
            self._pcd = o3d.geometry.PointCloud()
        return self._pcd

    def integrate(self, color: np.ndarray, depth_m: np.ndarray, intrinsic, pose: np.ndarray):
        """Back-project a color+depth frame through `pose` (camera-to-world
        4x4) into world space and merge into the accumulated cloud,
        downsampling afterward to bound growth. Scan-phase only."""
        if self.frozen:
            raise RuntimeError("Cannot integrate into a frozen WorldPointCloud - call reset() first")
        o3d = get_open3d()
        self._ensure_pcd()
        import cv2
        color_rgb = cv2.cvtColor(color, cv2.COLOR_BGR2RGB)
        color_img = o3d.geometry.Image(np.ascontiguousarray(color_rgb))
        depth_img = o3d.geometry.Image(np.ascontiguousarray(depth_m.astype(np.float32)))
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_img, depth_img, depth_scale=1.0, depth_trunc=9.0, convert_rgb_to_intensity=False,
        )
        frame_pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, intrinsic)
        frame_pcd.transform(pose)
        self._pcd += frame_pcd
        self._pcd = self._pcd.voxel_down_sample(self.voxel_size)

    def freeze(self):
        """Stop accepting integrate() calls, compute normals for point-to-
        plane ICP (see pose_tracker.track_frame_to_model)."""
        o3d = get_open3d()
        pcd = self._ensure_pcd()
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=self.voxel_size * 2, max_nn=30)
        )
        self.frozen = True

    def update_colors(self, pose: np.ndarray, texture_frame: np.ndarray, intrinsic) -> int:
        """Re-sample this point cloud's colors from a new 2D BGR frame,
        given the camera's current pose (camera-to-world 4x4). Points that
        project outside the frame or land behind the camera keep their
        previous color. Live-phase only. Returns how many points were
        actually updated (diagnostics/tests)."""
        o3d = get_open3d()
        pcd = self._ensure_pcd()
        points = np.asarray(pcd.points)
        if points.shape[0] == 0:
            return 0

        inv_pose = np.linalg.inv(pose)
        ones = np.ones((points.shape[0], 1), dtype=points.dtype)
        points_h = np.hstack([points, ones])
        cam_pts = (inv_pose @ points_h.T).T[:, :3]

        fx, fy = intrinsic.get_focal_length()
        cx, cy = intrinsic.get_principal_point()
        z = cam_pts[:, 2]
        valid = z > 1e-6
        u = np.zeros_like(z)
        v = np.zeros_like(z)
        u[valid] = (cam_pts[valid, 0] * fx / z[valid]) + cx
        v[valid] = (cam_pts[valid, 1] * fy / z[valid]) + cy

        h, w = texture_frame.shape[:2]
        in_bounds = valid & (u >= 0) & (u < w) & (v >= 0) & (v < h)

        colors = np.asarray(pcd.colors)
        if colors.shape[0] != points.shape[0]:
            colors = np.zeros((points.shape[0], 3), dtype=np.float64)

        idx = np.where(in_bounds)[0]
        if idx.shape[0] == 0:
            return 0
        px = u[idx].astype(np.int32)
        py = v[idx].astype(np.int32)
        # texture_frame is BGR uint8 (this codebase's convention) - Open3D wants RGB [0, 1].
        sampled_bgr = texture_frame[py, px].astype(np.float64) / 255.0
        colors[idx, 0] = sampled_bgr[:, 2]
        colors[idx, 1] = sampled_bgr[:, 1]
        colors[idx, 2] = sampled_bgr[:, 0]
        pcd.colors = o3d.utility.Vector3dVector(colors)
        return int(idx.shape[0])

    def reset(self):
        # Safe even if open3d was never imported (self._pcd is already
        # None) - just re-affirms the empty/unfrozen state rather than
        # forcing an import that isn't otherwise needed.
        self._pcd = None
        self.frozen = False

    def save(self, path: str):
        o3d = get_open3d()
        o3d.io.write_point_cloud(path, self._ensure_pcd())

    def load(self, path: str):
        o3d = get_open3d()
        self._pcd = o3d.io.read_point_cloud(path)
        self.frozen = True

    @property
    def points(self) -> np.ndarray:
        return np.asarray(self._pcd.points) if self._pcd is not None else np.zeros((0, 3))

    @property
    def colors(self) -> np.ndarray:
        return np.asarray(self._pcd.colors) if self._pcd is not None else np.zeros((0, 3))

    @property
    def normals(self) -> np.ndarray:
        return np.asarray(self._pcd.normals) if self._pcd is not None else np.zeros((0, 3))

    @property
    def point_count(self) -> int:
        return len(self._pcd.points) if self._pcd is not None else 0
