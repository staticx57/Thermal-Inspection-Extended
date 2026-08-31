import queue
import threading
import logging
from typing import Optional, Any, Callable, Tuple

from thermal_inspection.utils.media_recorder import VideoRecorder, SnapshotManager
from thermal_inspection.utils.config import get_config

logger = logging.getLogger(__name__)


class MediaManager:
    """
    Encapsulates video recording and snapshot capture logic.
    """
    def __init__(self):
        self.recording_enabled: bool = False
        self._record_queue: queue.Queue = queue.Queue(maxsize=64)
        self._record_writer_thread: Optional[threading.Thread] = None
        self._last_display_frame = None

        # Load config and create recorders
        try:
            cfg = get_config()
            recording_cfg = cfg.get('recording', {
                'output_path': 'recordings/',
                'filename_pattern': 'inspection_%Y%m%d_%H%M%S',
                'video_codec': 'mp4v',
                'save_roi_metadata': True,
                'save_thermal': False,
                'save_rgb': False,
            })
            snapshot_cfg = cfg.get('snapshots', {
                'output_path': 'snapshots/',
                'filename_pattern': 'snapshot_%Y%m%d_%H%M%S',
                'format': 'png',
                'quality': 95,
                'save_metadata': True,
            })
            self.video_recorder = VideoRecorder(recording_cfg)
            self.snapshot_manager = SnapshotManager(snapshot_cfg)
            logger.info("MediaManager: VideoRecorder and SnapshotManager initialized")
        except Exception as e:
            logger.warning(f"MediaManager: media recorders not available: {e}")
            self.video_recorder = None
            self.snapshot_manager = None

    def toggle_recording(self, enabled: bool, fps: int = 30, frame_shape: Tuple[int, int, int] = (512, 640, 3)):
        """
        Starts or stops video recording.
        """
        if enabled == self.recording_enabled:
            return

        if enabled:
            if self.video_recorder is None:
                logger.warning("toggle_recording(True): no VideoRecorder — recording disabled")
                return

            if not self.video_recorder.start_recording(frame_shape, fps=fps):
                logger.error("VideoRecorder.start_recording() failed")
                return

            # Clear out queue
            while not self._record_queue.empty():
                try:
                    self._record_queue.get_nowait()
                except queue.Empty:
                    break

            self._record_writer_thread = threading.Thread(
                target=self._record_writer_loop, daemon=True, name="VideoRecordWriter"
            )
            self._record_writer_thread.start()
            self.recording_enabled = True
            logger.info("Recording started")
        else:
            self.recording_enabled = False
            self._record_queue.put(None)
            if self._record_writer_thread and self._record_writer_thread.is_alive():
                self._record_writer_thread.join(timeout=10.0)
            self._record_writer_thread = None

            if self.video_recorder:
                self.video_recorder.stop_recording()
            logger.info("Recording stopped")

    def _record_writer_loop(self):
        while True:
            try:
                item = self._record_queue.get(timeout=2.0)
            except queue.Empty:
                if not self.recording_enabled:
                    break
                continue

            if item is None:
                break

            if self.video_recorder and self.video_recorder.is_recording():
                fusion_frame, thermal_frame, rgb_frame, rois, stats = item
                self.video_recorder.write_frame(
                    fusion_frame,
                    thermal_frame=thermal_frame,
                    rgb_frame=rgb_frame,
                    rois=rois,
                    thermal_stats=stats
                )

        logger.debug("VideoRecordWriter thread exiting")

    def enqueue_frame(self, display_frame, thermal_frame, rgb_frame, rois, stats):
        """
        Called from the frame loop to enqueue frames for recording.
        """
        if not self.recording_enabled:
            return

        try:
            # We must copy frames so they aren't modified while in the queue
            disp_copy = display_frame.copy() if display_frame is not None else None
            therm_copy = thermal_frame.copy() if thermal_frame is not None else None
            rgb_copy = rgb_frame.copy() if rgb_frame is not None else None

            item = (disp_copy, therm_copy, rgb_copy, rois, stats)
            self._record_queue.put_nowait(item)
        except queue.Full:
            logger.warning("Record queue is full, dropping frame")

    def capture_snapshot(self, frame, rois=None, stats=None, gui_invoke_fn: Optional[Callable[[str, Any], None]] = None):
        """
        Asynchronously captures a snapshot.
        """
        if self.snapshot_manager is None:
            logger.warning("capture_snapshot: no SnapshotManager available")
            return

        if frame is None:
            logger.warning("capture_snapshot: no display frame available yet")
            return

        rois = rois or []
        frame_copy = frame.copy()

        def _write():
            try:
                path = self.snapshot_manager.capture_snapshot(
                    frame_copy, rois=rois, thermal_stats=stats
                )
                if path:
                    logger.info(f"Snapshot saved: {path}")
                    if gui_invoke_fn:
                        gui_invoke_fn("show_snapshot_notification", path)
            except Exception as exc:
                logger.error(f"Snapshot save failed: {exc}")

        threading.Thread(target=_write, daemon=True, name="SnapshotWriter").start()

    def cleanup(self):
        """
        Stops recording if active and performs cleanup.
        """
        if self.recording_enabled:
            self.toggle_recording(False)
