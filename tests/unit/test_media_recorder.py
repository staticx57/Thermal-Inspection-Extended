"""
Unit tests for VideoRecorder (utils/media_recorder.py) - previously had
zero test coverage, found during a general best-practices audit
(2026-09-03). Covers two confirmed bugs from that audit:

- stop_recording() used to release the video writers and clear
  self.recording only after the metadata JSON save succeeded, both
  inside the same try block - a metadata save failure (bad value, disk
  full, permissions) left the writers un-released (leaked file handles,
  an unfinalized video file) and self.recording stuck True forever,
  silently blocking every future start_recording() call for the rest of
  the process.
- start_recording() checked the fusion writer's isOpened() but not the
  thermal/RGB writers' - a failed-to-open thermal/RGB writer was left in
  place, and write_frame()'s own isOpened() check would then skip every
  write with no log at all.
"""
import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from thermal_inspection.utils.media_recorder import VideoRecorder


def _make_recorder(tmp_path, **config_overrides):
    config = {"output_path": str(tmp_path), "save_roi_metadata": True}
    config.update(config_overrides)
    return VideoRecorder(config)


@pytest.mark.unit
class TestStopRecordingCleanup:

    def test_cleanup_and_recording_flag_reset_even_if_metadata_save_fails(self, tmp_path):
        recorder = _make_recorder(tmp_path)
        with patch("cv2.VideoWriter") as mock_writer_cls:
            mock_writer = MagicMock()
            mock_writer.isOpened.return_value = True
            mock_writer_cls.return_value = mock_writer

            assert recorder.start_recording((480, 640), fps=30) is True
            assert recorder.recording is True

            # Force the metadata JSON save to fail - a non-serializable
            # value is the most realistic real-world trigger (e.g. a
            # stray numpy scalar or object slipping into thermal_stats).
            recorder.metadata["frames"].append({"bad_value": object()})

            result = recorder.stop_recording()

            assert result is False
            # The bug: these used to stay True/non-released after a
            # metadata-save exception.
            assert recorder.recording is False
            mock_writer.release.assert_called_once()
            assert recorder.fusion_writer is None

    def test_cleanup_runs_on_successful_stop_too(self, tmp_path):
        recorder = _make_recorder(tmp_path)
        with patch("cv2.VideoWriter") as mock_writer_cls:
            mock_writer = MagicMock()
            mock_writer.isOpened.return_value = True
            mock_writer_cls.return_value = mock_writer

            recorder.start_recording((480, 640), fps=30)
            result = recorder.stop_recording()

            assert result is True
            assert recorder.recording is False
            mock_writer.release.assert_called_once()

            # A real, valid JSON metadata file must exist alongside the
            # (mocked) video file.
            metadata_files = list(tmp_path.glob("*.json"))
            assert len(metadata_files) == 1
            json.loads(metadata_files[0].read_text())  # must parse without error


@pytest.mark.unit
class TestStartRecordingWriterFailures:

    def test_failed_thermal_writer_is_not_left_silently_broken(self, tmp_path):
        recorder = _make_recorder(tmp_path, save_thermal=True)

        def fake_video_writer(path, *args, **kwargs):
            writer = MagicMock()
            # Simulate only the thermal writer failing to open - the
            # fusion writer (created first, a different path) still
            # succeeds. Match the exact filename suffix media_recorder
            # itself produces, not a bare substring - tmp_path's own
            # directory name contains this test's name, which contains
            # "thermal", so a plain "in" check would false-positive on
            # the fusion writer's path too.
            writer.isOpened.return_value = not str(path).endswith("_thermal.avi")
            return writer

        with patch("cv2.VideoWriter", side_effect=fake_video_writer):
            result = recorder.start_recording((480, 640), fps=30)

        assert result is True  # fusion writer (the required one) still opened
        assert recorder.thermal_writer is None, (
            "a failed-to-open thermal writer must not be left in place silently"
        )

    def test_failed_rgb_writer_is_not_left_silently_broken(self, tmp_path):
        recorder = _make_recorder(tmp_path, save_rgb=True)

        def fake_video_writer(path, *args, **kwargs):
            writer = MagicMock()
            writer.isOpened.return_value = not str(path).endswith("_rgb.avi")
            return writer

        with patch("cv2.VideoWriter", side_effect=fake_video_writer):
            result = recorder.start_recording((480, 640), fps=30)

        assert result is True
        assert recorder.rgb_writer is None

    def test_successful_writers_all_kept(self, tmp_path):
        recorder = _make_recorder(tmp_path, save_thermal=True, save_rgb=True)
        with patch("cv2.VideoWriter") as mock_writer_cls:
            mock_writer = MagicMock()
            mock_writer.isOpened.return_value = True
            mock_writer_cls.return_value = mock_writer

            result = recorder.start_recording((480, 640), fps=30)

        assert result is True
        assert recorder.thermal_writer is not None
        assert recorder.rgb_writer is not None
