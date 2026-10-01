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
from thermal_inspection.processing.world_thermal import SIDECAR_SUFFIX, WorldThermalLayer


class WorldPointCloud:
    def __init__(self, voxel_size: float = 0.01, merge_every: int = 8):
        # Deliberately does NOT call get_open3d() here - WorldMapper
        # constructs a WorldPointCloud eagerly at app startup regardless of
        # whether the user ever touches 3D Mapping Fusion, so this
        # constructor must succeed even when open3d isn't installed at all
        # (see the Global Constraints' "graceful placeholder, not a hard
        # failure" requirement). The actual o3d.geometry.PointCloud only
        # gets created in _ensure_pcd(), called from methods that need it -
        # those are only reached once the user explicitly starts a scan.
        self.voxel_size = voxel_size
        self.merge_every = max(1, int(merge_every))
        self._pcd = None
        self.frozen = False
        # Bumped whenever the set of points changes (integrate/freeze/load/reset). Lets consumers that cache
        # something derived from the geometry (the tracker's per-scale ICP targets) know when to rebuild.
        self.revision = 0
        self._since_merge = 0
        self.thermal = WorldThermalLayer()      # per-point temperatures; indexes line up with the frozen points

    def _ensure_pcd(self):
        if self._pcd is None:
            o3d = get_open3d()
            self._pcd = o3d.geometry.PointCloud()
        return self._pcd

    def integrate(self, color: np.ndarray, depth_m: np.ndarray, intrinsic, pose: np.ndarray):
        """Back-project a color+depth frame through `pose` (camera-to-world
        4x4) into world space and merge into the accumulated cloud. Scan-phase only.

        Each frame is voxel-downsampled on its own first (cheap: it's one frame), then appended; the whole
        accumulated cloud is only re-downsampled every `merge_every` frames to merge overlapping voxels. Doing the
        full-cloud downsample on every frame cost time proportional to the entire map, growing through the scan."""
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
        frame_pcd = frame_pcd.voxel_down_sample(self.voxel_size)
        self._pcd += frame_pcd
        self._since_merge += 1
        if self._since_merge >= self.merge_every:
            self._pcd = self._pcd.voxel_down_sample(self.voxel_size)
            self._since_merge = 0
        self.revision += 1

    def freeze(self):
        """Stop accepting integrate() calls, compute normals for point-to-
        plane ICP (see pose_tracker.track_frame_to_model)."""
        o3d = get_open3d()
        pcd = self._ensure_pcd()
        if self._since_merge and len(pcd.points):
            self._pcd = pcd = pcd.voxel_down_sample(self.voxel_size)
            self._since_merge = 0
        self._estimate_normals(pcd)
        self.frozen = True
        self.thermal.reset(len(pcd.points))
        self.revision += 1

    def _estimate_normals(self, pcd):
        o3d = get_open3d()
        if len(pcd.points) == 0:
            return
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=self.voxel_size * 2, max_nn=30)
        )

    def update_colors(self, pose: np.ndarray, texture_frame: np.ndarray, intrinsic,
                      depth_m: np.ndarray = None, depth_tolerance: float = 0.03) -> int:
        """Re-sample this point cloud's colors from a new 2D BGR frame,
        given the camera's current pose (camera-to-world 4x4). Points that
        project outside the frame or land behind the camera keep their
        previous color. Live-phase only. Returns how many points were
        actually updated (diagnostics/tests).

        depth_m (the live depth frame, same resolution as texture_frame) enables an occlusion test: a world point
        is only recoloured if the live depth at its pixel agrees with the point's own distance from the camera
        (within depth_tolerance plus 2% of range). Without it, a point hidden BEHIND a nearer surface projects to
        the same pixel as that surface and is painted with the wrong colour."""
        o3d = get_open3d()
        pcd = self._ensure_pcd()
        points = np.asarray(pcd.points)
        if points.shape[0] == 0:
            return 0

        inv_pose = np.linalg.inv(pose)
        cam_pts = points @ inv_pose[:3, :3].T + inv_pose[:3, 3]

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

        if depth_m is not None and depth_m.shape[:2] == (h, w):
            idx_all = np.where(in_bounds)[0]
            observed = depth_m[v[idx_all].astype(np.int32), u[idx_all].astype(np.int32)]
            agrees = (observed > 0) & (np.abs(observed - z[idx_all]) <= depth_tolerance + 0.02 * z[idx_all])
            in_bounds = np.zeros_like(in_bounds)
            in_bounds[idx_all[agrees]] = True

        colors = np.asarray(pcd.colors)
        if colors.shape[0] != points.shape[0]:
            colors = np.zeros((points.shape[0], 3), dtype=np.float64)
        else:
            colors = colors.copy()

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

    def update_temperatures(self, pose: np.ndarray, temp_c: np.ndarray, intrinsic, depth_m: np.ndarray = None) -> int:
        """Record live temperature readings (degrees C, same grid as depth_m/the intrinsic) onto the frozen world.
        Returns how many points were updated."""
        if self._pcd is None or not self.frozen:
            return 0
        fx, fy = intrinsic.get_focal_length()
        cx, cy = intrinsic.get_principal_point()
        return self.thermal.update(self.points, pose, temp_c, (fx, fy, cx, cy), depth_m)

    def reset(self):
        # Safe even if open3d was never imported (self._pcd is already
        # None) - just re-affirms the empty/unfrozen state rather than
        # forcing an import that isn't otherwise needed.
        self._pcd = None
        self.frozen = False
        self._since_merge = 0
        self.thermal.reset(0)
        self.revision += 1

    def save(self, path: str):
        o3d = get_open3d()
        pcd = self._ensure_pcd()
        if len(pcd.points) == 0:
            raise ValueError("Nothing to save - the world is empty")
        if not o3d.io.write_point_cloud(path, pcd):
            raise OSError(f"Open3D could not write the world to {path}")
        if self.thermal.has_data or self.thermal.has_baseline:
            # temperatures can't live in a PLY with Open3D, so they go in a sidecar next to it
            self.thermal.save(path + SIDECAR_SUFFIX)

    def load(self, path: str):
        """Load a saved world and make it ready for live tracking: frozen, with normals (a world saved before
        Finish, or by another tool, may have none - point-to-plane ICP needs them)."""
        o3d = get_open3d()
        pcd = o3d.io.read_point_cloud(path)
        if len(pcd.points) == 0:
            raise ValueError(f"{path} contains no points")
        if not pcd.has_normals():
            self._estimate_normals(pcd)
        self._pcd = pcd
        self.frozen = True
        self._since_merge = 0
        self.thermal.reset(len(pcd.points))
        import os
        if os.path.exists(path + SIDECAR_SUFFIX):
            self.thermal.load(path + SIDECAR_SUFFIX, len(pcd.points))
        self.revision += 1

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
