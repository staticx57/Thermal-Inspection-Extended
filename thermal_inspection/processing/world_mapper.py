"""
Thin state-machine orchestrator for 3D Mapping Fusion. The only class
app.py talks to directly - owns one PoseTracker (pose_tracker.py) and one
WorldPointCloud (world_point_cloud.py), wires per-frame calls between them.
Neither of those two knows about the other or about this state machine.
"""
from __future__ import annotations

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

    def finish_scan(self):
        if self.state != "scanning":
            raise RuntimeError(f"finish_scan() called in state '{self.state}', expected 'scanning'")
        self.world.freeze()
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
                    self.world.update_colors(self._pose, texture_frame, self._pose_tracker.intrinsic)
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
