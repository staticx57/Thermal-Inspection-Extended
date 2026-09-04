"""
Regression tests for a resource-leak pattern found across four camera
backends during a general best-practices audit (2026-09-03): open()
wraps the whole method in one try/except, but partial progress before a
failure (a genuinely opened cv2.VideoCapture / running pipeline / claimed
SDK handle) was never released in the except block - only logged and
returned False. A retry after such a failure could then fail again since
the stale handle was still held.

Covers the two backends whose partial-open state (cv2.VideoCapture) is
straightforward to simulate without needing an SDK not installed in this
environment (PySpin, pyrealsense2) - rgb_camera_firefly.py and
realsense_camera.py got the identical fix (calling their own release()
in the except block) but need their real SDKs to exercise directly.
"""
from unittest.mock import MagicMock, patch

import pytest

from thermal_inspection.cameras.gige_camera import GigECamera
from thermal_inspection.cameras.rgb_camera_uvc import RGBCameraUVC


@pytest.mark.unit
class TestUVCCameraOpenFailureCleanup:

    def test_release_called_when_a_later_step_fails(self):
        camera = RGBCameraUVC(device_id=0, resolution=(640, 480), fps=30)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640  # matches requested width/height/fps -> skips the .set() branches
        mock_cap.read.side_effect = RuntimeError("simulated failure after a genuine open")

        with patch("cv2.VideoCapture", return_value=mock_cap):
            result = camera.open()

        assert result is False
        mock_cap.release.assert_called_once()
        assert camera.cap is None
        assert camera.is_open is False


@pytest.mark.unit
class TestGigECameraOpenFailureCleanup:

    def test_release_called_when_a_later_step_fails(self):
        camera = GigECamera(stream_url="rtsp://example.invalid/stream")

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = RuntimeError("simulated failure after a genuine open")

        with patch("cv2.VideoCapture", return_value=mock_cap):
            result = camera.open()

        assert result is False
        mock_cap.release.assert_called_once()
        assert camera.cap is None
        assert camera.is_open is False
