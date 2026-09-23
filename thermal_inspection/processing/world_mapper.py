"""
Thin state-machine orchestrator for 3D Mapping Fusion. The only class
app.py talks to directly - owns one PoseTracker (pose_tracker.py) and one
WorldPointCloud (world_point_cloud.py), wires per-frame calls between them.
Neither of those two knows about the other or about this state machine.
"""
from __future__ import annotations

import cv2
import numpy as np

from thermal_inspection.processing.pose_tracker import PoseTracker
from thermal_inspection.processing.world_point_cloud import WorldPointCloud


class WorldMapper:
    def __init__(self, voxel_size: float = 0.01,
                 quality_good_threshold: float = 0.3,
                 quality_degraded_threshold: float = 0.1,
                 pose_tracker_factory=PoseTracker,
                 world_factory=WorldPointCloud):
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

    def start_scan(self, width: int, height: int, fx: float, fy: float, cx: float, cy: float):
        """Begin a new scan - resets any previous world."""
        self._pose_tracker = self._pose_tracker_factory(width, height, fx, fy, cx, cy)
        self.world.reset()
        self._pose = np.eye(4)
        self._prev_color = None
        self._prev_depth = None
        self.tracking_quality = 0.0
        self.state = "scanning"

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
        """
        self._pose_tracker = self._pose_tracker_factory(width, height, fx, fy, cx, cy)
        self.world.load(path)
        self._pose = np.eye(4)
        self._prev_color = None
        self._prev_depth = None
        self.tracking_quality = 0.0
        self.state = "mapped"

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
        self.state = "mapped"

    def reset(self):
        self.world.reset()
        self._pose = np.eye(4)
        self.tracking_quality = 0.0
        self.state = "idle"

    def track_and_texture(self, color: np.ndarray, depth_m: np.ndarray, texture_frame: np.ndarray = None):
        """Call once per (throttled) frame. Scan phase: tracks + integrates
        geometry every call. Live phase (mapped): tracks against the frozen
        world and, if quality allows, re-textures it from texture_frame."""
        if self.state == "scanning":
            if self._prev_color is not None:
                success, transform, quality = self._pose_tracker.track_frame_to_frame(
                    color, depth_m, self._prev_color, self._prev_depth, np.eye(4)
                )
                if success:
                    self._pose = self._pose @ transform
                    self.tracking_quality = quality
            self.world.integrate(color, depth_m, self._pose_tracker.intrinsic, self._pose)
            self._prev_color, self._prev_depth = color, depth_m
        elif self.state == "mapped":
            success, transform, quality = self._pose_tracker.track_frame_to_model(
                color, depth_m, self.world.points, self.world.normals, self._pose
            )
            self.tracking_quality = quality
            if success and quality >= self._quality_degraded:
                self._pose = transform
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
                    self.world.update_colors(self._pose, texture_frame, intrinsic)
        else:
            raise RuntimeError(f"track_and_texture() called in state '{self.state}', expected 'scanning' or 'mapped'")

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
