"""
Regression tests for VideoWidget.update_frame's frame-buffer lifetime,
found during a systematic rendering-performance investigation
(2026-09-03): the BGR->RGB conversion result was being copied twice -
once implicitly (a fresh cv2.cvtColor allocation) and once explicitly
(qimage.copy()) - even though cv2.cvtColor always returns a freshly
allocated array that's never a view into the caller's frame or any
reused buffer. Removed the redundant copy for that path, keeping the
converted array alive via self._qimage_backing_frame instead (needed
because resizeEvent re-derives a pixmap from self._last_qimage well
after update_frame() returns - a local variable would have let the
backing array get garbage-collected before that).

These tests verify actual displayed pixel content (not just "doesn't
crash"), since a lifetime bug here would show up as stale or corrupted
pixels, not an exception.
"""
import numpy as np
import pytest

from thermal_inspection.gui.widgets.video_widget import VideoWidget


def _pixmap_pixel(widget, x, y):
    image = widget._last_qpixmap.toImage()
    color = image.pixelColor(x, y)
    return (color.red(), color.green(), color.blue())


@pytest.mark.unit
class TestVideoWidgetFrameBuffer:

    def test_displayed_pixel_matches_bgr_to_rgb_conversion(self, qapp):
        widget = VideoWidget()
        widget.resize(64, 64)
        frame = np.zeros((64, 64, 3), dtype=np.uint8)
        frame[:, :] = (10, 20, 200)  # BGR: blue=10, green=20, red=200

        widget.update_frame(frame)

        assert _pixmap_pixel(widget, 5, 5) == (200, 20, 10)  # RGB order

    def test_second_frame_replaces_first_with_no_stale_pixels(self, qapp):
        """Guards against a lifetime bug: if the backing array for the
        first frame were freed too early or reused, the second frame
        could show corrupted or stale-looking data instead of its own
        actual content."""
        widget = VideoWidget()
        widget.resize(64, 64)

        frame1 = np.full((64, 64, 3), (255, 0, 0), dtype=np.uint8)  # BGR pure blue
        widget.update_frame(frame1)
        assert _pixmap_pixel(widget, 5, 5) == (0, 0, 255)

        frame2 = np.full((64, 64, 3), (0, 255, 0), dtype=np.uint8)  # BGR pure green
        widget.update_frame(frame2)
        assert _pixmap_pixel(widget, 5, 5) == (0, 255, 0)

    def test_resize_rederives_pixmap_from_still_valid_backing_frame(self, qapp):
        """The specific path this fix has to keep working: resizeEvent
        rebuilds a pixmap from self._last_qimage well after update_frame()
        returns - the backing array it depends on must still be alive."""
        widget = VideoWidget()
        widget.resize(64, 64)
        frame = np.full((64, 64, 3), (10, 20, 200), dtype=np.uint8)  # BGR
        widget.update_frame(frame)
        widget.overlay.frame_size = (64, 64)  # != (640, 512), required to hit the rescale branch

        widget.resize(128, 128)

        assert _pixmap_pixel(widget, 5, 5) == (200, 20, 10)
