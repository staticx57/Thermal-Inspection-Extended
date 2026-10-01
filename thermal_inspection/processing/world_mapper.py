"""
Thin state-machine orchestrator for 3D Mapping Fusion. The only class
app.py talks to directly - owns one PoseTracker (pose_tracker.py) and one
WorldPointCloud (world_point_cloud.py), wires per-frame calls between them.
Neither of those two knows about the other or about this state machine.

States: idle -> scanning -> mapped. While scanning, every frame is tracked against the previous one and integrated;
while mapped the world is frozen and each tick tracks the camera against it and re-textures it. If live tracking is
lost (and always right after loading a saved world, whose camera pose is unknown) a background re-localization looks
for the camera in the world so tracking can resume from wherever it is pointing.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

import cv2
import numpy as np

from thermal_inspection.processing import imu_prior, world_units
from thermal_inspection.processing.world_thermal import MeasureResult, Marker, ProbeResult
from thermal_inspection.processing.pose_tracker import PoseTracker
from thermal_inspection.processing.world_point_cloud import WorldPointCloud

logger = logging.getLogger(__name__)


def _locked(method):
    """Serialize lifecycle calls (GUI thread) with the per-frame tick (worker thread)."""
    def wrapper(self, *args, **kwargs):
        with self._state_lock:
            return method(self, *args, **kwargs)
    wrapper.__name__ = method.__name__
    wrapper.__doc__ = method.__doc__
    return wrapper


class WorldMapper:
    def __init__(self, voxel_size: float = 0.01,
                 quality_good_threshold: float = 0.3,
                 quality_degraded_threshold: float = 0.1,
                 pose_tracker_factory=PoseTracker,
                 world_factory=WorldPointCloud,
                 max_working_width: int = 640,
                 relocalize_after_lost_ticks: int = 3,
                 relocalize_async: bool = True,
                 max_scan_step_m: float = 0.5,
                 scan_quality_floor: float = 0.2,
                 max_live_step_m: float = 0.5,
                 max_live_step_deg: float = 45.0,
                 max_gravity_error_deg: float = 10.0,
                 min_valid_depth_fraction: float = 0.05):
        self.state = "idle"
        self.tracking_quality = 0.0
        self._pose_tracker_factory = pose_tracker_factory
        self._pose_tracker = None
        self.world = world_factory(voxel_size=voxel_size)
        self._pose = np.eye(4)
        self._prev_color = None
        self._prev_depth = None
        self._quality_good = quality_good_threshold
        self._quality_degraded = quality_degraded_threshold

        # Tracking and integration run at a working resolution no wider than this: a RealSense colour stream can be
        # 1920x1080, which would be ~2 million points per frame through Open3D. Intrinsics are scaled to match.
        self._max_working_width = int(max_working_width)
        self._max_gravity_error_deg = float(max_gravity_error_deg)
        self._keyframe_min_step_m = 0.02
        self._keyframe_min_deg = 2.0
        self._scale = 1.0
        self._relocalize_after = int(relocalize_after_lost_ticks)
        self._relocalize_async = relocalize_async
        self._max_scan_step_m = float(max_scan_step_m)
        self._scan_quality_floor = float(scan_quality_floor)
        # A plausible camera cannot move further than this between two ticks. Point-to-plane ICP on scenes made of
        # big flat surfaces can slide along a plane to a wrong answer that still scores a respectable fitness; a
        # jump this large from the previous estimate is treated as lost tracking (-> re-localization) instead.
        self._max_live_step_m = float(max_live_step_m)
        self._max_live_step_deg = float(max_live_step_deg)
        # Frames with (almost) no valid depth - lens covered, pointed at the sky/a window - have nothing to track,
        # yet Open3D's odometry can still report "success" on them.
        self._min_valid_depth_fraction = float(min_valid_depth_fraction)

        self._scan_quality_history = deque(maxlen=30)
        self._scan_lost_frames = 0
        self._lost_ticks = 0
        self.relocalizing = False
        self._generation = 0            # bumped on start_scan/load/reset: stale background results are dropped
        self._reloc_result = None
        self._reloc_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._slot_lock = threading.Lock()
        self._slot = None               # newest submitted frame awaiting the worker
        self._worker = None
        self.last_error = None
        self._error_count = 0
        self._static_color_diff = 6.0   # mean |dI| (0-255) and mean |dZ| (m) below which the camera counts as held still
        self._static_depth_diff = 0.015

    # ------------------------------------------------------------------
    # Working resolution
    # ------------------------------------------------------------------

    def _working_intrinsics(self, width: int, height: int, fx: float, fy: float, cx: float, cy: float):
        self._scale = min(1.0, self._max_working_width / float(width)) if self._max_working_width > 0 else 1.0
        if self._scale >= 1.0:
            return int(width), int(height), fx, fy, cx, cy
        s = self._scale
        return int(round(width * s)), int(round(height * s)), fx * s, fy * s, cx * s, cy * s

    def _to_working(self, color, depth_m):
        """Resize an input frame pair to the working resolution (depth with nearest-neighbour: no invented
        in-between depths across edges)."""
        intrinsic = self._pose_tracker.intrinsic
        w, h = int(intrinsic.width), int(intrinsic.height)
        if color is not None and color.shape[:2] != (h, w):
            color = cv2.resize(color, (w, h), interpolation=cv2.INTER_AREA)
        if depth_m is not None and depth_m.shape[:2] != (h, w):
            depth_m = cv2.resize(depth_m, (w, h), interpolation=cv2.INTER_NEAREST)
        return color, depth_m

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _reset_tracking_state(self):
        self._pose = np.eye(4)
        self._prev_color = None
        self._prev_depth = None
        self._kf_pose = np.eye(4)       # pose of the reference (key)frame _prev_color/_prev_depth
        self._imu_since_kf = np.eye(3)  # gyro rotation accumulated since that key-frame (camera frame)
        self._scan_preview = None
        self._gravity_world = None      # world-frame 'up' (unit vector) from the accelerometer at scan start
        self.imu_active = False         # True once IMU data has been supplied to this world
        self._scan_preview = None       # (points, colours) COPIES published by the worker while scanning
        self._scan_preview_time = 0.0
        self.temp_unit = "C"            # display unit for temperatures in text: 'C' | 'F' | 'K' (set by the app)
        self.tracking_quality = 0.0
        self._scan_quality_history.clear()
        self._scan_lost_frames = 0
        self._lost_ticks = 0
        self.relocalizing = False
        self._generation += 1
        with self._reloc_lock:
            self._reloc_result = None

    @_locked
    def start_scan(self, width: int, height: int, fx: float, fy: float, cx: float, cy: float):
        """Begin a new scan - resets any previous world."""
        self._pose_tracker = self._pose_tracker_factory(*self._working_intrinsics(width, height, fx, fy, cx, cy))
        self.world.reset()
        self._reset_tracking_state()
        self.state = "scanning"

    @_locked
    def load_from_path(self, path: str, width: int, height: int,
                        fx: float, fy: float, cx: float, cy: float):
        """Load a previously-saved world AND construct a working
        PoseTracker for it, mirroring what start_scan() does.

        Without this, _pose_tracker stayed None after a Load - every
        subsequent live track_and_texture() call in the 'mapped' branch
        called self._pose_tracker.track_frame_to_model(...) on None,
        raising AttributeError (silently swallowed by the caller's broad
        except at the app.py call site). Live tracking after Load never
        actually worked.

        Constructs the PoseTracker BEFORE touching the file, so a missing
        open3d install (PoseTracker.__init__ raises ImportError - see
        pose_tracker.py) fails fast without a partial/inconsistent load.
        world.load() can raise the same ImportError; either way this
        propagates to the caller uncaught, same contract as start_scan().

        The camera's pose in the loaded world is unknown (it is not saved), so the first live ticks try ICP from the
        world origin and, failing that, fall back to global re-localization - the camera may be pointing anywhere.
        """
        self._pose_tracker = self._pose_tracker_factory(*self._working_intrinsics(width, height, fx, fy, cx, cy))
        self.world.load(path)
        self._reset_tracking_state()
        self._lost_ticks = max(0, self._relocalize_after - 1)   # one failed ICP attempt, then re-localize
        self.state = "mapped"

    @_locked
    def finish_scan(self):
        if self.state != "scanning":
            raise RuntimeError(f"finish_scan() called in state '{self.state}', expected 'scanning'")
        self.world.freeze()
        # tracking_quality up to this point is the scan-phase odometry
        # metric (np.trace of an information matrix - unbounded, typically
        # in the thousands), an entirely different scale than the live-phase
        # ICP fitness (0-1) that quality_state compares against the same
        # thresholds once state == "mapped". Without this reset, the first
        # read of quality_state right after finish_scan() (before any live
        # track_and_texture() call has overwritten it) would misreport a
        # huge stale odometry number as a false-confident "good". Reset to
        # a neutral 0.0 so there's no stale cross-scale value visible even
        # momentarily - quality_state's own good/degraded/lost bucketing
        # then correctly reads this as "lost" (the honest state: no live
        # tracking sample yet) until the next real tick overwrites it.
        self.tracking_quality = 0.0
        self._lost_ticks = 0
        self.state = "mapped"

    @_locked
    def reset(self):
        self.world.reset()
        self._reset_tracking_state()
        self.state = "idle"

    # ------------------------------------------------------------------
    # Per-frame
    # ------------------------------------------------------------------

    @_locked
    def track_and_texture(self, color: np.ndarray, depth_m: np.ndarray, texture_frame: np.ndarray = None,
                          temp_c: np.ndarray = None, imu=None):
        """Call once per (throttled) frame. Scan phase: tracks + integrates
        geometry every call. Live phase (mapped): tracks against the frozen
        world and, if quality allows, re-textures it from texture_frame."""
        if self.state == "scanning":
            self._scan_tick(color, depth_m, imu)
        elif self.state == "mapped":
            self._live_tick(color, depth_m, texture_frame, temp_c, imu)
        else:
            raise RuntimeError(f"track_and_texture() called in state '{self.state}', expected 'scanning' or 'mapped'")

    def submit_frame(self, color, depth_m, texture_frame=None, temp_c=None, imu=None):
        """Non-blocking track_and_texture(): hands the frame to a background worker and returns at once. Only the
        newest pending frame is kept - tracking (odometry is ~1 s at 640x480) must never stall the caller's
        display loop, and a stale frame is worth nothing once a newer one exists."""
        with self._slot_lock:
            if self._slot is not None and self._slot[4] is not None and imu is not None:
                imu = self._slot[4].then(imu)       # the dropped frame's rotation still happened: keep it
            self._slot = (color, depth_m, texture_frame, temp_c, imu)
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(target=self._work, name="world-track", daemon=True)
            self._worker.start()

    def _work(self):
        while True:
            with self._slot_lock:
                frame, self._slot = self._slot, None
                if frame is None:
                    return          # slot empty: worker exits; submit_frame() starts a new one
            if self.state not in ("scanning", "mapped"):
                continue            # Reset/Start raced with a queued frame: it belongs to a world that no longer exists
            try:
                self.track_and_texture(*frame)
                self.last_error = None
                self._error_count = 0
            except Exception as e:      # a tracking error must not kill the worker
                self.last_error = e
                self._error_count += 1
                if self._error_count == 1 or self._error_count % 50 == 0:
                    logger.warning(f"3D Mapping Fusion track_and_texture failed ({self._error_count} consecutive): {e}")

    def _held_still(self, color, depth_m) -> bool:
        """Cheap check (a 1/8-sampled comparison against the key-frame) that the camera has not moved, so the ~1 s
        odometry can be skipped while the camera is held still."""
        kc, kd = self._prev_color, self._prev_depth
        if kc is None or kc.shape != color.shape:
            return False
        # colour is compared after removing each image's mean: a held-still camera's auto-exposure drifts by 10+ levels
        ca = color[::8, ::8].astype(np.float32)
        cb = kc[::8, ::8].astype(np.float32)
        c = np.abs((ca - ca.mean()) - (cb - cb.mean())).mean()
        a, b = depth_m[::8, ::8], kd[::8, ::8]
        both = (a > 0) & (b > 0)
        if both.mean() < 0.2:
            return False
        d = float(np.median(np.abs(a[both] - b[both])))      # median: a few flickering pixels must not matter
        return c < self._static_color_diff and d < self._static_depth_diff

    def _has_usable_depth(self, depth_m) -> bool:
        return depth_m is not None and float((depth_m > 0).mean()) >= self._min_valid_depth_fraction

    def _scan_tick(self, color, depth_m, imu=None):
        color, depth_m = self._to_working(color, depth_m)
        if not self._has_usable_depth(depth_m):
            self._scan_lost_frames += 1
            self.tracking_quality = 0.0
            return
        if self._prev_color is None:
            self.world.integrate(color, depth_m, self._pose_tracker.intrinsic, self._pose)
            self._prev_color, self._prev_depth, self._kf_pose = color, depth_m, self._pose.copy()
            self._imu_since_kf = np.eye(3)
            self._publish_scan_preview(force=True)
            if imu is not None and imu_prior.is_quasi_static(imu.gravity_cam):
                self._gravity_world = imu_prior.gravity_world_from_pose(self._pose, imu.gravity_cam)
            return

        init = np.eye(4)
        if imu is not None:
            self.imu_active = True
            self._imu_since_kf = self._imu_since_kf @ imu.delta_R
            init = imu_prior.rotation_prior_transform(self._imu_since_kf)   # head-start for fast pans
            if self._gravity_world is None and imu_prior.is_quasi_static(imu.gravity_cam):
                self._gravity_world = imu_prior.gravity_world_from_pose(self._pose, imu.gravity_cam)

        if self._held_still(color, depth_m):
            self._scan_lost_frames = 0      # nothing moved: the estimate stands, nothing new to integrate
            self._imu_since_kf = np.eye(3)  # and the camera is back at the key-frame: drop accumulated gyro bias
            return
        success, transform, quality = self._pose_tracker.track_frame_to_frame(
            color, depth_m, self._prev_color, self._prev_depth, init
        )
        ok = bool(success)
        if ok and float(np.linalg.norm(np.asarray(transform)[:3, 3])) > self._max_scan_step_m:
            ok = False      # an implausible jump between consecutive frames is a tracking failure, not motion
        if ok and len(self._scan_quality_history) >= 5:
            typical = float(np.median(self._scan_quality_history))
            ok = quality >= self._scan_quality_floor * typical   # far less constrained than usual: don't trust it
        if ok and imu is not None:
            candidate = self._kf_pose @ np.linalg.inv(np.asarray(transform))
            if imu_prior.gravity_error_deg(candidate, imu.gravity_cam, self._gravity_world) > self._max_gravity_error_deg:
                ok = False      # the tilt this pose implies contradicts gravity: a tracking slip, not motion

        if not ok:
            # Don't integrate at a pose we couldn't establish - that smears the map. Keep the last good frame as
            # the reference, so tracking can pick up again when the camera returns to (or near) that view.
            self._scan_lost_frames += 1
            self.tracking_quality = 0.0
            return

        # Open3D's odometry maps the reference camera's coordinates into the current one (source -> target), so the
        # camera-to-world pose is the reference pose times the INVERSE: pose = kf_pose @ inv(T).
        self._pose = self._kf_pose @ np.linalg.inv(np.asarray(transform))
        self.tracking_quality = quality
        self._scan_quality_history.append(quality)
        self._scan_lost_frames = 0
        # Key-frame tracking: only adopt a new reference (and integrate) once the camera has really moved. Chaining
        # frame-to-frame accumulates a little error every frame, so a held-still camera would random-walk away and
        # smear the map; against a fixed key-frame the estimate does not drift while stationary.
        step = float(np.linalg.norm(np.asarray(transform)[:3, 3]))
        cos = np.clip((np.trace(np.asarray(transform)[:3, :3]) - 1.0) / 2.0, -1.0, 1.0)
        if step >= self._keyframe_min_step_m or np.degrees(np.arccos(cos)) >= self._keyframe_min_deg:
            self.world.integrate(color, depth_m, self._pose_tracker.intrinsic, self._pose)
            self._prev_color, self._prev_depth, self._kf_pose = color, depth_m, self._pose.copy()
            self._imu_since_kf = np.eye(3)
            self._publish_scan_preview()

    def _live_tick(self, color, depth_m, texture_frame, temp_c=None, imu=None):
        self._apply_relocalization_result()
        color, depth_m = self._to_working(color, depth_m)
        if not self._has_usable_depth(depth_m):
            self.tracking_quality = 0.0
            self._lost_ticks += 1
            return
        init_pose = self._pose
        if imu is not None:
            self.imu_active = True
            init_pose = imu_prior.pose_with_rotation_prior(self._pose, imu.delta_R)   # head-start for fast pans
        success, transform, quality = self._pose_tracker.track_frame_to_model(
            color, depth_m, self.world.points, self.world.normals, init_pose,
            world_key=self.world.revision,
        )
        self.tracking_quality = quality
        plausible = success and self._step_is_plausible(transform)
        if plausible and imu is not None and imu_prior.gravity_error_deg(
                np.asarray(transform), imu.gravity_cam, self._gravity_world) > self._max_gravity_error_deg:
            plausible = False       # tilt contradicts gravity: the match slid along a surface, don't accept it
        if plausible and quality >= self._quality_degraded:
            self._pose = transform
            self._lost_ticks = 0
            if texture_frame is not None:
                intrinsic = self._pose_tracker.intrinsic
                # WorldPointCloud.update_colors() projects world points
                # using THIS intrinsic's (fx, fy, cx, cy) - the u, v
                # pixel coordinates it computes are only valid in an
                # array sized (intrinsic.height, intrinsic.width).
                # texture_frame can arrive at a completely different
                # resolution (e.g. colorized_thermal at the thermal
                # camera's native size vs. this intrinsic captured from
                # RealSense's color stream at scan start) - indexing
                # into it with those u/v values would silently sample
                # the wrong pixels (roughly a scale mismatch, only a
                # sub-rectangle ever getting real color) with no error
                # at all. Resize here, once, so update_colors' own u/v
                # math and the array it indexes always agree on
                # resolution, regardless of what the caller passed in.
                target_w, target_h = int(intrinsic.width), int(intrinsic.height)
                th, tw = texture_frame.shape[:2]
                if (tw, th) != (target_w, target_h):
                    texture_frame = cv2.resize(
                        texture_frame, (target_w, target_h),
                        interpolation=cv2.INTER_LINEAR,
                    )
                # depth_m lets update_colors skip world points hidden behind nearer surfaces
                self.world.update_colors(self._pose, texture_frame, intrinsic, depth_m=depth_m)
            if temp_c is not None:
                # temperatures (degrees C) must line up with the depth grid the pose was tracked on
                intrinsic = self._pose_tracker.intrinsic
                target = (int(intrinsic.width), int(intrinsic.height))
                if (temp_c.shape[1], temp_c.shape[0]) != target:
                    temp_c = cv2.resize(temp_c.astype(np.float32), target, interpolation=cv2.INTER_LINEAR)
                self.world.update_temperatures(self._pose, temp_c, intrinsic, depth_m=depth_m)
        else:
            if success and not plausible:
                self.tracking_quality = 0.0     # a fitness that comes with an impossible jump is not real tracking
            self._lost_ticks += 1
            if self._lost_ticks >= self._relocalize_after:
                self._start_relocalization(depth_m)

    def _step_is_plausible(self, new_pose) -> bool:
        """True if the camera moved no more than a real camera can between two ticks."""
        delta = np.linalg.inv(self._pose) @ np.asarray(new_pose)
        step = float(np.linalg.norm(delta[:3, 3]))
        cos = np.clip((np.trace(delta[:3, :3]) - 1.0) / 2.0, -1.0, 1.0)
        return step <= self._max_live_step_m and float(np.degrees(np.arccos(cos))) <= self._max_live_step_deg

    # ------------------------------------------------------------------
    # Re-localization (global registration, off the frame loop)
    # ------------------------------------------------------------------

    def _start_relocalization(self, depth_m):
        tracker = self._pose_tracker
        if self.relocalizing or not hasattr(tracker, "relocalize") or self.world.point_count == 0:
            return
        self.relocalizing = True
        generation = self._generation
        depth = np.array(depth_m, copy=True)
        points = np.array(self.world.points, copy=True)
        normals = np.array(self.world.normals, copy=True)
        key = self.world.revision

        def work():
            try:
                result = tracker.relocalize(depth, points, normals, world_key=key)
            except Exception as e:                      # never let a worker thread kill the app
                logger.warning(f"3D Mapping re-localization failed: {e}")
                result = (False, None, 0.0)
            with self._reloc_lock:
                if generation == self._generation:      # the world/scan may have changed while this ran
                    self._reloc_result = result
                    self.relocalizing = False

        if self._relocalize_async:
            threading.Thread(target=work, name="world-relocalize", daemon=True).start()
        else:
            work()
            self._apply_relocalization_result()

    def _apply_relocalization_result(self):
        with self._reloc_lock:
            result, self._reloc_result = self._reloc_result, None
        if not result:
            return
        ok, pose, fitness = result
        if ok and pose is not None:
            self._pose = np.asarray(pose)
            self.tracking_quality = fitness
            self._lost_ticks = 0
            logger.info(f"3D Mapping: camera re-localized in the world (fitness {fitness:.2f})")

    # ------------------------------------------------------------------
    # Status for the UI
    # ------------------------------------------------------------------

    def thermal_summary(self, hotspot_count: int = 3) -> str:
        """Multi-line text for the panel: temperature range and coverage, the hottest distinct places (with position
        in the world frame and distance from the camera now) and - when a saved world was loaded - the biggest
        changes since it. Empty when no temperatures have been recorded. Temperatures use `temp_unit`; distances
        are always shown in metric and imperial."""
        layer = self.world.thermal
        if self.state != "mapped" or not (layer.has_data or layer.has_baseline):
            return ""
        pts = self.world.points
        cam = np.asarray(self._pose)[:3, 3]
        u = self.temp_unit

        def place(entry, delta=False):
            value, xyz, _ = entry
            shown = world_units.format_delta(value, u) if delta else world_units.format_temp(value, u)
            return (f"  {shown}  ({xyz[0]:+.2f}, {xyz[1]:+.2f}, {xyz[2]:+.2f}) m, "
                    f"{world_units.format_distance(float(np.linalg.norm(xyz - cam)))} away")

        lines = []
        st = layer.stats()
        if st:
            lines.append(f"Live: {world_units.format_temp(st['min'], u)} to {world_units.format_temp(st['max'], u)} "
                         f"(mean {world_units.format_temp(st['mean'], u)}), {st['coverage']:.0%} of the world measured")
        hot = layer.hotspots(pts, count=hotspot_count, mode="peak")
        if hot:
            lines.append("Hottest places (peak):")
            lines += [place(h) for h in hot]
        if layer.has_baseline and layer.has_data:
            warm, cool = layer.changes(pts, count=hotspot_count)
            if warm:
                lines.append("Warmer than the loaded world:")
                lines += [place(w, delta=True) for w in warm]
            if cool:
                lines.append("Cooler than the loaded world:")
                lines += [place(c, delta=True) for c in cool]
            if not warm and not cool:
                lines.append("No change vs the loaded world.")
        return "\n".join(lines)

    # ------------------------------------------------------------------ viewer-facing queries
    # Read-only. Deliberately NOT under _state_lock: the tracking worker holds that lock for the whole of a tick
    # (up to ~1 s of odometry) and these are called from the GUI thread. The arrays they read are not resized while
    # the world is mapped, so a concurrent in-place temperature/colour update at worst yields a slightly stale value.

    def _publish_scan_preview(self, force: bool = False, min_interval_s: float = 0.4):
        """Called by the tracking worker (the only thread that mutates the world while scanning): copy the cloud so
        the display thread can draw it without touching memory Open3D may reallocate on the next integrate."""
        now = time.monotonic()
        if not force and now - self._scan_preview_time < min_interval_s:
            return
        self._scan_preview_time = now
        pts = np.array(self.world.points, dtype=np.float32, copy=True)
        cols = np.array(self.world.colors, dtype=np.float32, copy=True)
        if len(cols) != len(pts):
            cols = np.full((len(pts), 3), 0.7, np.float32)
        self._scan_preview = (pts, cols)

    def camera_pose(self) -> np.ndarray:
        """Copy of the current camera-to-world pose (4x4)."""
        return np.array(self._pose, dtype=float, copy=True)

    def preview_cloud(self, max_points: int, mode: str = "colour"):
        """(points float32 (M,3), colours float32 (M,3) RGB 0-1, indices int64 (M,)) for the viewer, decimated to at
        most max_points by an even stride. indices[i] is the point's index in the FULL world arrays, so a pick on the
        preview resolves to an exact reading (probe/measure take full-world indices)."""
        if self.state == "scanning":
            # the world is being modified by the tracking worker: only ever read its published copy
            snap = self._scan_preview
            if snap is None:
                return np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32), np.zeros(0, np.int64)
            pts, cols = snap
        else:
            pts = self.world.points
            cols = self.viewport_colors(mode)
        n = pts.shape[0]
        if n > max_points > 0:
            idx = np.linspace(0, n - 1, max_points).astype(np.int64)
        else:
            idx = np.arange(n, dtype=np.int64)
        return pts[idx].astype(np.float32), np.asarray(cols)[idx].astype(np.float32), idx

    def probe(self, index: int):
        """Everything known about one world point (a ProbeResult), or None for an invalid index."""
        pts = self.world.points
        if not 0 <= int(index) < pts.shape[0]:
            return None
        i = int(index)
        layer = self.world.thermal

        def at(arr):
            if arr is None or arr.size != pts.shape[0]:
                return None
            v = float(arr[i])
            return v if np.isfinite(v) else None

        temp, peak = at(layer.latest), at(layer.peak)
        change = None
        if layer.has_baseline and temp is not None:
            base = at(layer.baseline)
            change = None if base is None else temp - base
        xyz = pts[i]
        cam = np.asarray(self._pose)[:3, 3] if self.state == "mapped" else None
        dist = None if cam is None else float(np.linalg.norm(xyz - cam))
        return ProbeResult(i, (float(xyz[0]), float(xyz[1]), float(xyz[2])), dist, temp, peak, change,
                           has_temp=temp is not None or peak is not None)

    def measure(self, index_a: int, index_b: int):
        """Straight-line distance between two world points and their temperature difference (b - a), or None."""
        pts = self.world.points
        n = pts.shape[0]
        if not (0 <= int(index_a) < n and 0 <= int(index_b) < n):
            return None
        a, b = self.probe(index_a), self.probe(index_b)
        d = float(np.linalg.norm(pts[int(index_a)] - pts[int(index_b)]))
        both = a.temp is not None and b.temp is not None
        return MeasureResult(int(index_a), int(index_b), d, (b.temp - a.temp) if both else None)

    def markers(self, count: int = 5):
        """Hotspots (peak temperature) and, when a saved world was loaded, the biggest warm-ups and cool-downs, as
        Marker entries for the viewer. Labels: H1.. hottest, W1.. warmer, C1.. cooler."""
        layer = self.world.thermal
        if self.state != "mapped" or not (layer.has_data or layer.has_baseline):
            return []
        pts = self.world.points
        out = [Marker(f"H{k}", tuple(xyz), t, "hot", idx)
               for k, (t, xyz, idx) in enumerate(layer.hotspots(pts, count=count, mode="peak"), 1)]
        if layer.has_baseline and layer.has_data:
            warm, cool = layer.changes(pts, count=count)
            out += [Marker(f"W{k}", tuple(xyz), d, "warm", idx) for k, (d, xyz, idx) in enumerate(warm, 1)]
            out += [Marker(f"C{k}", tuple(xyz), d, "cool", idx) for k, (d, xyz, idx) in enumerate(cool, 1)]
        return out

    def legend(self, mode: str):
        """(lo, hi) in degrees C for the viewer's colour legend (a symmetric difference range for 'change'), or None
        when the mode is the texture colours or there is nothing measured to show."""
        if mode == "colour":
            return None
        return self.world.thermal.scale(mode)

    def viewport_colors(self, mode: str):
        """Colours for the 3D viewport: the world's texture colours, or a temperature/peak/change colouring. Falls
        back to the texture colours when the requested layer has nothing to show yet."""
        if mode != "colour":
            c = self.world.thermal.colorize(mode)
            if c is not None and len(c) == self.world.point_count:
                return c
        return self.world.colors

    @property
    def point_count(self) -> int:
        return self.world.point_count

    @property
    def quality_state(self) -> str:
        if self.state != "mapped":
            return "n/a"
        if self.tracking_quality >= self._quality_good:
            return "good"
        if self.tracking_quality >= self._quality_degraded:
            return "degraded"
        return "lost"

    @property
    def status_message(self) -> str:
        """One line of guidance for the panel ('' when there is nothing to add)."""
        if self.state == "scanning":
            if self._scan_lost_frames:
                return (f"Scan tracking lost ({self._scan_lost_frames} frames skipped, nothing added) - "
                        "slow down and move back toward the last good view.")
            return "Scanning - move the camera slowly so consecutive views overlap."
        if self.state == "mapped":
            if self.relocalizing:
                return "Looking for the camera in the world - point it at a mapped area."
            state = self.quality_state
            if state == "lost":
                return "Tracking lost - point the camera back at a mapped area, or Reset World."
            if state == "degraded":
                return "Tracking degraded - move more slowly or show more of the mapped area."
        return ""
