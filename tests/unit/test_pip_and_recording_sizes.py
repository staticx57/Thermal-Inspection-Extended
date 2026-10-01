"""
PIP composes on a canvas big enough to keep the inset's own detail, and recording copes with the
resulting (or any changed) frame size instead of silently dropping frames.
"""

import cv2
import numpy as np
import pytest

from thermal_inspection.processing.fusion_processor import FusionProcessor


def _checker(h, w, cell=4):
    """High-frequency pattern: loses obvious detail if it is shrunk and re-enlarged."""
    yy, xx = np.mgrid[0:h, 0:w]
    v = (((yy // cell) + (xx // cell)) % 2 * 255).astype(np.uint8)
    return cv2.cvtColor(v, cv2.COLOR_GRAY2BGR)


@pytest.mark.unit
class TestPipCanvas:
    def test_small_sensor_with_larger_rgb_inset_gets_a_bigger_canvas(self):
        fp = FusionProcessor()
        thermal = np.full((256, 320, 3), 90, np.uint8)       # 320x256 Boson
        rgb = _checker(480, 640)                              # 640x480 RGB as the inset
        fp.set_fusion_priority('thermal') if hasattr(fp, 'set_fusion_priority') else None
        fp.fusion_priority = 'thermal'                        # thermal is main, RGB is the inset
        out = fp._picture_in_picture(thermal, rgb, pip_size=0.25)
        assert out.shape[1] > thermal.shape[1], "canvas should be enlarged so the inset isn't ~80px wide"
        assert out.shape[1] <= 1280
        assert abs(out.shape[1] / out.shape[0] - 320 / 256) < 0.01

    def test_inset_keeps_detail_instead_of_being_shrunk_to_a_thumbnail(self):
        fp = FusionProcessor()
        fp.fusion_priority = 'thermal'
        thermal = np.full((256, 320, 3), 90, np.uint8)
        rgb = _checker(480, 640, cell=4)
        out = fp._picture_in_picture(thermal, rgb, pip_size=0.25)
        h, w = out.shape[:2]
        inset = out[10:10 + int(h * 0.25), w - int(w * 0.25) - 10: w - 10]      # top-right slot
        # A checker survives as strong local contrast only if the inset kept real resolution
        gray = cv2.cvtColor(inset, cv2.COLOR_BGR2GRAY).astype(np.float32)
        assert float(np.abs(np.diff(gray, axis=1)).mean()) > 20

    def test_no_enlargement_when_the_inset_has_no_extra_detail(self):
        fp = FusionProcessor()
        fp.fusion_priority = 'rgb'                            # RGB main; a tiny thermal inset is
        rgb = np.full((480, 640, 3), 50, np.uint8)            # smaller than its 160px slot, so there
        thermal = np.full((80, 100, 3), 90, np.uint8)         # is nothing to gain from a bigger canvas
        out = fp._picture_in_picture(thermal, rgb, pip_size=0.25)
        assert out.shape == rgb.shape


@pytest.mark.unit
class TestRecorderConformsFrames:
    def _recorder(self, monkeypatch, tmp_path):
        from thermal_inspection.utils import media_recorder

        written = {"fusion": []}

        class FakeWriter:
            def __init__(self, path, fourcc, fps, size):
                self.size, self.open = size, True
                self.tag = "fusion"
            def isOpened(self):
                return self.open
            def write(self, frame):
                # what real OpenCV enforces: a mismatched frame is silently dropped
                if (frame.shape[1], frame.shape[0]) == self.size and frame.ndim == 3:
                    written[self.tag].append(frame.shape)
            def release(self):
                self.open = False

        monkeypatch.setattr(media_recorder.cv2, "VideoWriter", FakeWriter)
        rec = media_recorder.MediaRecorder({"output_path": str(tmp_path), "save_roi_metadata": False}) \
            if hasattr(media_recorder, "MediaRecorder") else media_recorder.VideoRecorder(
                {"output_path": str(tmp_path), "save_roi_metadata": False})
        return rec, written

    def test_frames_of_a_different_size_are_resized_not_dropped(self, monkeypatch, tmp_path):
        rec, written = self._recorder(monkeypatch, tmp_path)
        assert rec.start_recording((256, 320))                 # writers opened at 320x256
        rec.write_frame(np.zeros((256, 320, 3), np.uint8))     # same size
        rec.write_frame(np.zeros((512, 640, 3), np.uint8))     # e.g. PIP switched to a bigger canvas
        rec.write_frame(np.zeros((128, 160), np.uint8))        # smaller, single-channel
        assert len(written["fusion"]) == 3, "every frame must reach the writer at its size"
        assert all(s == (256, 320, 3) for s in written["fusion"])
