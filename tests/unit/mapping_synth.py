"""
Synthetic RGB-D scene for 3D Mapping tests: textured planes ray-cast from known camera poses (camera-to-world 4x4).

Ground truth makes it possible to test what identical-frame tests never can: that the recovered camera motion has the
right *direction and size*, that a scanned map lies on the real surfaces, and that tracking recovers a moved camera.
"""
import numpy as np

W, H, FX, FY, CX, CY = 160, 120, 130.0, 130.0, 80.0, 60.0

# planes: (point on plane, normal). A back wall, a slanted floor, a side wall - enough 3D structure to constrain all 6 DoF
PLANES = [
    (np.array([0.0, 0.0, 2.5]), np.array([0.0, 0.0, -1.0])),                     # back wall
    (np.array([0.0, 0.6, 0.0]), np.array([0.0, -0.94, -0.34])),                  # slanted floor
    (np.array([-1.0, 0.0, 0.0]), np.array([0.92, 0.0, -0.39])),                  # side wall
]


def texture(p):
    """A smooth but feature-rich colour field over world position p (N,3) -> uint8 BGR (N,3)."""
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    r = 128 + 70 * np.sin(9 * x + 3 * z) + 50 * np.sin(17 * y - 5 * x)
    g = 128 + 70 * np.sin(11 * y + 4 * z) + 50 * np.sin(13 * x + 7 * y)
    b = 128 + 70 * np.sin(7 * z - 6 * y) + 50 * np.sin(19 * x - 9 * z)
    return np.clip(np.stack([b, g, r], axis=1), 0, 255).astype(np.uint8)


def render(pose, noise=0.0, seed=0, scale=1, with_points=False):
    """(bgr uint8 HxWx3, depth float32 HxW in metres) seen by a camera at `pose` (camera-to-world).
    scale > 1 renders the same view at scale x the resolution (intrinsics scaled to match)."""
    h, w = H * scale, W * scale
    v, u = np.mgrid[0:h, 0:w]
    dirs = np.stack([(u - CX * scale) / (FX * scale), (v - CY * scale) / (FY * scale),
                     np.ones_like(u, dtype=np.float64)], axis=-1).reshape(-1, 3)
    R, t = pose[:3, :3], pose[:3, 3]
    d_world = dirs @ R.T
    best_t = np.full(len(dirs), np.inf)
    for p0, n in PLANES:
        denom = d_world @ n
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = ((p0 - t) @ n) / denom
        ok = (tt > 0.2) & (denom != 0) & (tt < best_t)
        best_t = np.where(ok, tt, best_t)
    hit = np.isfinite(best_t)
    depth = np.where(hit, best_t, 0.0)                      # dirs have z == 1 so ray parameter == camera-z depth
    pts = t + d_world * np.where(hit, best_t, 0.0)[:, None]
    color = np.zeros((len(dirs), 3), np.uint8)
    color[hit] = texture(pts[hit])
    if noise:
        rng = np.random.default_rng(seed)
        depth = depth + hit * rng.normal(0, noise, depth.shape)
    if with_points:
        return color.reshape(h, w, 3), depth.reshape(h, w).astype(np.float32), pts.reshape(h, w, 3)
    return color.reshape(h, w, 3), depth.reshape(h, w).astype(np.float32)


def pose(tx=0.0, ty=0.0, tz=0.0, yaw_deg=0.0, pitch_deg=0.0):
    """Camera-to-world pose: rotate by yaw (about y) then pitch (about x), translate."""
    cy_, sy_ = np.cos(np.radians(yaw_deg)), np.sin(np.radians(yaw_deg))
    cp, sp = np.cos(np.radians(pitch_deg)), np.sin(np.radians(pitch_deg))
    Ry = np.array([[cy_, 0, sy_], [0, 1, 0], [-sy_, 0, cy_]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    T = np.eye(4)
    T[:3, :3] = Ry @ Rx
    T[:3, 3] = [tx, ty, tz]
    return T


def hot_temperature(points_xyz):
    """Ground-truth temperature field: an 80 C patch on the back wall (x > 0.35, y < 0.2), 25 C elsewhere."""
    p = np.asarray(points_xyz)
    hot = (p[..., 0] > 0.35) & (p[..., 1] < 0.2) & (np.abs(p[..., 2] - 2.5) < 0.05)
    return np.where(hot, 80.0, 25.0).astype(np.float32)


# ---- helpers shared by the geometry tests -------------------------------------------------------------------------

TRAJECTORY = [pose(tx=0.03 * i, yaw_deg=1.0 * i) for i in range(8)]


def pose_error(estimated, truth):
    """(translation error in metres, rotation error in degrees) between two camera-to-world poses."""
    delta = np.linalg.inv(truth) @ estimated
    trans = float(np.linalg.norm(delta[:3, 3]))
    cos = np.clip((np.trace(delta[:3, :3]) - 1.0) / 2.0, -1.0, 1.0)
    return trans, float(np.degrees(np.arccos(cos)))


def scan(trajectory=TRAJECTORY, **mapper_kwargs):
    """Scan the synthetic scene along `trajectory`; returns (WorldMapper, estimated poses)."""
    from thermal_inspection.processing.world_mapper import WorldMapper
    wm = WorldMapper(voxel_size=0.02, **mapper_kwargs)
    wm.start_scan(W, H, FX, FY, CX, CY)
    poses = []
    for i, p in enumerate(trajectory):
        color, depth = render(p, noise=0.002, seed=i)
        wm.track_and_texture(color, depth)
        poses.append(wm._pose.copy())
    return wm, poses


def mapped_world(trajectory=TRAJECTORY, **mapper_kwargs):
    wm, poses = scan(trajectory, **mapper_kwargs)
    wm.finish_scan()
    return wm, poses


def live_track(wm, true_pose, seed=50, noise=0.002, texture_frame=None):
    """One live tick from a camera at `true_pose`; returns the mapper's new pose estimate."""
    color, depth = render(true_pose, noise=noise, seed=seed)
    wm.track_and_texture(color, depth, texture_frame=color if texture_frame is None else texture_frame)
    return wm._pose.copy()
