#!/usr/bin/env python3
"""
Media Recorder for Thermal Inspection Fusion Tool
Handles video recording, playback, and snapshot capture with ROI metadata.
"""

import cv2
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import logging

from roi_manager import ROI

logger = logging.getLogger(__name__)


class VideoRecorder:
    """
    Records thermal+RGB fusion video with optional ROI metadata.
    Supports multiple stream recording (thermal, RGB, fusion).
    """

    def __init__(self, config: Dict):
        """
        Initialize video recorder.

        Args:
            config: Recording configuration from config.json
        """
        self.config = config
        self.recording = False

        # Video writers for different streams
        self.fusion_writer: Optional[cv2.VideoWriter] = None
        self.thermal_writer: Optional[cv2.VideoWriter] = None
        self.rgb_writer: Optional[cv2.VideoWriter] = None

        # Recording metadata
        self.output_path: Optional[Path] = None
        self.metadata: Dict = {}
        self.frame_count: int = 0
        self.start_time: Optional[datetime] = None

        # ROI metadata tracking
        self.roi_metadata: List[Dict] = []

        # Ensure output directory exists
        output_dir = Path(config.get('output_path', 'recordings/'))
        output_dir.mkdir(parents=True, exist_ok=True)

    def start_recording(self, frame_shape: Tuple[int, int], fps: int = 30) -> bool:
        """
        Start video recording.

        Args:
            frame_shape: (height, width) of frames to record
            fps: Frames per second

        Returns:
            True if recording started successfully
        """
        if self.recording:
            logger.warning("Recording already in progress")
            return False

        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime(self.config.get('filename_pattern', 'inspection_%Y%m%d_%H%M%S'))
            output_dir = Path(self.config.get('output_path', 'recordings/'))
            output_dir.mkdir(parents=True, exist_ok=True)

            self.output_path = output_dir / f"{timestamp}.avi"

            # Video codec
            fourcc_str = self.config.get('video_codec', 'mp4v')
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)

            height, width = frame_shape[:2]
            frame_size = (width, height)

            # Initialize fusion writer (always enabled)
            self.fusion_writer = cv2.VideoWriter(
                str(self.output_path),
                fourcc,
                fps,
                frame_size
            )

            if not self.fusion_writer.isOpened():
                logger.error("Failed to open fusion video writer")
                return False

            # Initialize thermal/RGB writers if enabled
            if self.config.get('save_thermal', False):
                thermal_path = output_dir / f"{timestamp}_thermal.avi"
                self.thermal_writer = cv2.VideoWriter(
                    str(thermal_path),
                    fourcc,
                    fps,
                    frame_size
                )

            if self.config.get('save_rgb', False):
                rgb_path = output_dir / f"{timestamp}_rgb.avi"
                self.rgb_writer = cv2.VideoWriter(
                    str(rgb_path),
                    fourcc,
                    fps,
                    frame_size
                )

            # Initialize metadata
            self.start_time = datetime.now()
            self.frame_count = 0
            self.roi_metadata = []
            self.metadata = {
                'start_time': self.start_time.isoformat(),
                'fps': fps,
                'frame_shape': list(frame_shape),
                'codec': fourcc_str,
                'frames': []
            }

            self.recording = True
            logger.info(f"Recording started: {self.output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            self.cleanup()
            return False

    def write_frame(self, fusion_frame: np.ndarray,
                   thermal_frame: Optional[np.ndarray] = None,
                   rgb_frame: Optional[np.ndarray] = None,
                   rois: Optional[List[ROI]] = None,
                   thermal_stats: Optional[Dict] = None) -> bool:
        """
        Write a frame to the video.

        Args:
            fusion_frame: Fusion display frame (required)
            thermal_frame: Raw thermal frame (optional)
            rgb_frame: Raw RGB frame (optional)
            rois: List of ROIs in this frame (optional)
            thermal_stats: Thermal analysis statistics (optional)

        Returns:
            True if frame was written successfully
        """
        if not self.recording:
            return False

        try:
            # Write fusion frame
            if self.fusion_writer and self.fusion_writer.isOpened():
                self.fusion_writer.write(fusion_frame)

            # Write thermal frame if enabled
            if self.thermal_writer and self.thermal_writer.isOpened() and thermal_frame is not None:
                # Ensure thermal frame is 3-channel
                if len(thermal_frame.shape) == 2:
                    thermal_frame = cv2.cvtColor(thermal_frame, cv2.COLOR_GRAY2BGR)
                self.thermal_writer.write(thermal_frame)

            # Write RGB frame if enabled
            if self.rgb_writer and self.rgb_writer.isOpened() and rgb_frame is not None:
                self.rgb_writer.write(rgb_frame)

            # Save frame metadata if enabled
            if self.config.get('save_roi_metadata', True):
                frame_meta = {
                    'frame_number': self.frame_count,
                    'timestamp': (datetime.now() - self.start_time).total_seconds()
                }

                # Add ROI data
                if rois:
                    frame_meta['rois'] = [
                        {
                            'roi_id': roi.roi_id,
                            'type': roi.roi_type.value,
                            'label': roi.label,
                            'bounds': list(roi.bounds),
                            'source': roi.source.value
                        }
                        for roi in rois
                    ]

                # Add thermal statistics
                if thermal_stats:
                    frame_meta['thermal_stats'] = thermal_stats

                self.metadata['frames'].append(frame_meta)

            self.frame_count += 1
            return True

        except Exception as e:
            logger.error(f"Failed to write frame: {e}")
            return False

    def stop_recording(self) -> bool:
        """
        Stop video recording and save metadata.

        Returns:
            True if recording stopped successfully
        """
        if not self.recording:
            return False

        try:
            # Finalize metadata
            self.metadata['end_time'] = datetime.now().isoformat()
            self.metadata['total_frames'] = self.frame_count
            self.metadata['duration'] = (datetime.now() - self.start_time).total_seconds()

            # Save metadata JSON
            if self.config.get('save_roi_metadata', True):
                metadata_path = self.output_path.with_suffix('.json')
                with open(metadata_path, 'w') as f:
                    json.dump(self.metadata, f, indent=2)
                logger.info(f"Metadata saved: {metadata_path}")

            # Release video writers
            self.cleanup()

            self.recording = False
            logger.info(f"Recording stopped: {self.frame_count} frames, {self.metadata['duration']:.1f}s")
            return True

        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return False

    def cleanup(self):
        """Release all video writers."""
        if self.fusion_writer:
            self.fusion_writer.release()
            self.fusion_writer = None

        if self.thermal_writer:
            self.thermal_writer.release()
            self.thermal_writer = None

        if self.rgb_writer:
            self.rgb_writer.release()
            self.rgb_writer = None

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.recording


class VideoPlayer:
    """
    Plays back recorded thermal inspection videos with ROI metadata.
    Supports frame-by-frame navigation and speed control.
    """

    def __init__(self, video_path: str):
        """
        Initialize video player.

        Args:
            video_path: Path to video file
        """
        self.video_path = Path(video_path)
        self.capture: Optional[cv2.VideoCapture] = None
        self.metadata: Optional[Dict] = None

        # Playback state
        self.playing = False
        self.paused = False
        self.current_frame: int = 0
        self.total_frames: int = 0
        self.fps: float = 30.0
        self.speed: float = 1.0  # Playback speed multiplier

        # Load video and metadata
        self._load_video()
        self._load_metadata()

    def _load_video(self) -> bool:
        """Load video file."""
        if not self.video_path.exists():
            logger.error(f"Video file not found: {self.video_path}")
            return False

        try:
            self.capture = cv2.VideoCapture(str(self.video_path))

            if not self.capture.isOpened():
                logger.error(f"Failed to open video: {self.video_path}")
                return False

            # Get video properties
            self.total_frames = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.capture.get(cv2.CAP_PROP_FPS)

            logger.info(f"Loaded video: {self.video_path} ({self.total_frames} frames @ {self.fps} fps)")
            return True

        except Exception as e:
            logger.error(f"Failed to load video: {e}")
            return False

    def _load_metadata(self):
        """Load ROI metadata JSON if available."""
        metadata_path = self.video_path.with_suffix('.json')

        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                logger.info(f"Loaded metadata: {metadata_path}")
            except Exception as e:
                logger.warning(f"Failed to load metadata: {e}")
                self.metadata = None
        else:
            logger.info("No metadata file found")
            self.metadata = None

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], Optional[Dict]]:
        """
        Read next frame with metadata.

        Returns:
            (success, frame, frame_metadata)
        """
        if not self.capture or not self.capture.isOpened():
            return False, None, None

        try:
            ret, frame = self.capture.read()

            if ret:
                self.current_frame += 1

                # Get frame metadata if available
                frame_meta = None
                if self.metadata and 'frames' in self.metadata:
                    if self.current_frame - 1 < len(self.metadata['frames']):
                        frame_meta = self.metadata['frames'][self.current_frame - 1]

                return True, frame, frame_meta
            else:
                return False, None, None

        except Exception as e:
            logger.error(f"Failed to read frame: {e}")
            return False, None, None

    def seek_frame(self, frame_number: int) -> bool:
        """
        Seek to specific frame.

        Args:
            frame_number: Frame number to seek to (0-indexed)

        Returns:
            True if seek was successful
        """
        if not self.capture or not self.capture.isOpened():
            return False

        try:
            if 0 <= frame_number < self.total_frames:
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                self.current_frame = frame_number
                return True
            else:
                logger.warning(f"Frame number out of range: {frame_number}")
                return False

        except Exception as e:
            logger.error(f"Failed to seek frame: {e}")
            return False

    def get_progress(self) -> float:
        """Get playback progress (0.0 to 1.0)."""
        if self.total_frames > 0:
            return self.current_frame / self.total_frames
        return 0.0

    def set_speed(self, speed: float):
        """Set playback speed multiplier."""
        self.speed = max(0.1, min(speed, 10.0))  # Clamp between 0.1x and 10x

    def pause(self):
        """Pause playback."""
        self.paused = True

    def resume(self):
        """Resume playback."""
        self.paused = False

    def is_paused(self) -> bool:
        """Check if paused."""
        return self.paused

    def cleanup(self):
        """Release video capture."""
        if self.capture:
            self.capture.release()
            self.capture = None


class SnapshotManager:
    """
    Manages snapshot capture with overlays, ROIs, and metadata.
    """

    def __init__(self, config: Dict):
        """
        Initialize snapshot manager.

        Args:
            config: Snapshot configuration from config.json
        """
        self.config = config

        # Ensure output directory exists
        output_dir = Path(config.get('output_path', 'snapshots/'))
        output_dir.mkdir(parents=True, exist_ok=True)

    def capture_snapshot(self, frame: np.ndarray,
                        rois: Optional[List[ROI]] = None,
                        thermal_stats: Optional[Dict] = None,
                        hot_spots: Optional[List] = None,
                        cold_spots: Optional[List] = None,
                        anomalies: Optional[List] = None) -> Optional[str]:
        """
        Capture snapshot with optional metadata.

        Args:
            frame: Frame to save
            rois: List of ROIs
            thermal_stats: Thermal analysis statistics
            hot_spots: List of hot spots
            cold_spots: List of cold spots
            anomalies: List of anomalies

        Returns:
            Path to saved snapshot, or None if failed
        """
        try:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime(self.config.get('filename_pattern', 'snapshot_%Y%m%d_%H%M%S'))
            output_dir = Path(self.config.get('output_path', 'snapshots/'))
            output_dir.mkdir(parents=True, exist_ok=True)

            # Determine format
            img_format = self.config.get('format', 'png').lower()
            snapshot_path = output_dir / f"{timestamp}.{img_format}"

            # Save image
            quality = self.config.get('quality', 95)
            if img_format == 'png':
                cv2.imwrite(str(snapshot_path), frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            elif img_format in ['jpg', 'jpeg']:
                cv2.imwrite(str(snapshot_path), frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            else:
                cv2.imwrite(str(snapshot_path), frame)

            # Save metadata if enabled
            if self.config.get('save_metadata', True):
                metadata = {
                    'timestamp': datetime.now().isoformat(),
                    'format': img_format,
                    'shape': list(frame.shape)
                }

                # Add ROI data
                if rois:
                    metadata['rois'] = [
                        {
                            'roi_id': roi.roi_id,
                            'type': roi.roi_type.value,
                            'label': roi.label,
                            'bounds': list(roi.bounds)
                        }
                        for roi in rois
                    ]

                # Add thermal statistics
                if thermal_stats:
                    metadata['thermal_stats'] = thermal_stats

                # Add hot spots
                if hot_spots:
                    metadata['hot_spots'] = [
                        {
                            'temperature': hs.temperature,
                            'center': list(hs.center),
                            'area': hs.area
                        }
                        for hs in hot_spots
                    ]

                # Add cold spots
                if cold_spots:
                    metadata['cold_spots'] = [
                        {
                            'temperature': cs.temperature,
                            'center': list(cs.center),
                            'area': cs.area
                        }
                        for cs in cold_spots
                    ]

                # Add anomalies
                if anomalies:
                    metadata['anomalies'] = [
                        {
                            'type': anom.anomaly_type,
                            'description': anom.description,
                            'location': list(anom.location),
                            'confidence': anom.confidence
                        }
                        for anom in anomalies
                    ]

                # Save metadata JSON
                metadata_path = snapshot_path.with_suffix('.json')
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

            logger.info(f"Snapshot saved: {snapshot_path}")
            return str(snapshot_path)

        except Exception as e:
            logger.error(f"Failed to capture snapshot: {e}")
            return None
