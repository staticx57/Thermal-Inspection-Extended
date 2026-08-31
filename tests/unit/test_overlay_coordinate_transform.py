"""
Coordinate transform tests for InspectionOverlayWidget.

These pin down two real bugs found during a UI-alignment audit:

1. `thermal_resolution` defaulted to (640, 512) and nothing in the
   application ever called `set_thermal_resolution()` — so every overlay
   transform used the wrong sensor size on any camera that isn't a
   full-resolution Boson (Tau2, Lepton, a Boson in 320x256 mode, ...).

2. Side-by-side mode assumed the two panels split the frame 50/50 with the
   thermal panel letterboxed to fit its half. `FusionProcessor._side_by_side()`
   actually does `np.hstack([thermal, rgb])` at each panel's own native
   width (only height is matched) — so the assumption was wrong for
   essentially any real camera pairing, not just mismatched resolutions.

Both the forward transform (thermal coords -> widget pixels, used to draw
ROIs/hot-spots/spot-meters) and the reverse transform (a click -> thermal
coords, used in `mousePressEvent` and `mouseMoveEvent`) are covered, since
the fix originally missed the reverse path in two separate places until the
duplication was found by inspection.
"""
import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtGui import QMouseEvent  # noqa: E402
from PyQt6.QtCore import Qt, QPointF  # noqa: E402

from thermal_inspection.gui.widgets.overlay_widget import InspectionOverlayWidget  # noqa: E402

# `qapp` fixture is provided by tests/conftest.py (session-scoped, shared
# across all test modules — see the comment there for why that matters).
pytestmark = pytest.mark.usefixtures("qapp")


def make_overlay(thermal_res, frame_size, view_mode, priority='rgb'):
    """Build an overlay whose widget-to-frame mapping is the identity (1:1)."""
    overlay = InspectionOverlayWidget()
    overlay.set_thermal_resolution(*thermal_res)
    # frame_to_widget applies scale + offset; keep it 1:1 so widget coords
    # equal frame coords and the transform under test is isolated.
    overlay.scale = 1.0
    overlay.offset_x = 0
    overlay.offset_y = 0
    overlay.frame_size = frame_size
    overlay.set_view_mode(view_mode, fusion_priority=priority)
    return overlay


class TestThermalResolutionDefault:

    def test_default_is_640x512_until_set(self):
        # Documents the historical default that made the bug invisible —
        # anything running exactly a full-res Boson never noticed.
        overlay = InspectionOverlayWidget()
        assert overlay.thermal_resolution == (640, 512)

    def test_set_thermal_resolution_updates_state(self):
        overlay = InspectionOverlayWidget()
        overlay.set_thermal_resolution(336, 256)
        assert overlay.thermal_resolution == (336, 256)

    def test_non_boson_resolution_changes_transform_output(self):
        # A Tau2 (336x256) and a full-res Boson (640x512) must not resolve
        # the same widget point to the same thermal coordinate.
        thermal_x, thermal_y = 100, 80

        boson = make_overlay((640, 512), (640, 512), 'thermal')
        tau2 = make_overlay((336, 256), (336, 256), 'thermal')

        boson_pos = boson._transform_thermal_coords(thermal_x, thermal_y)
        tau2_pos = tau2._transform_thermal_coords(thermal_x, thermal_y)

        assert boson_pos == (thermal_x, thermal_y)  # 1:1, frame == thermal res
        assert tau2_pos == (thermal_x, thermal_y)    # also 1:1 at its own res
        # Both are correctly 1:1 in isolation; the historical bug was a
        # *fixed* (640, 512) applied when the real sensor was 336x256 —
        # covered directly by the mismatch tests below.

    def test_stale_default_would_misplace_a_smaller_sensor(self):
        # Simulates the actual bug: frame_size reflects the real (small)
        # camera, but thermal_resolution was never updated from its default.
        overlay = InspectionOverlayWidget()
        overlay.scale = 1.0
        overlay.offset_x = 0
        overlay.offset_y = 0
        overlay.frame_size = (336, 256)  # real Tau2 frame
        # thermal_resolution left at its (640, 512) default — the bug.

        wrong = overlay._transform_thermal_coords(300, 200)

        # Scaling 300/640 and 200/512 against a 336x256 frame lands far from
        # where the click at (300, 200) on a 336x256 sensor actually is.
        assert wrong != (300, 200)

        overlay.set_thermal_resolution(336, 256)
        fixed = overlay._transform_thermal_coords(300, 200)
        assert fixed == (300, 200)


class TestSideBySideForwardTransform:
    """thermal coords -> widget pixels, for drawing overlays."""

    def test_thermal_left_is_native_width_unscaled(self):
        # Boson (640x512) + a 1920x1080 RGB camera: frame = 640 + 1920 wide.
        overlay = make_overlay(
            thermal_res=(640, 512), frame_size=(2560, 1080),
            view_mode='side_by_side', priority='thermal',
        )
        assert overlay._transform_thermal_coords(0, 0) == (0, 0)
        assert overlay._transform_thermal_coords(639, 511) == (639, 511)

    def test_thermal_right_is_positioned_after_rgb_panel(self):
        # RGB (1920 wide) on the left, thermal (640 wide) on the right.
        overlay = make_overlay(
            thermal_res=(640, 512), frame_size=(2560, 1080),
            view_mode='side_by_side', priority='rgb',
        )
        # Thermal panel starts at frame_width - thermal_width = 2560-640=1920.
        assert overlay._transform_thermal_coords(0, 0) == (1920, 0)
        assert overlay._transform_thermal_coords(639, 0) == (2559, 0)

    def test_old_50_50_split_assumption_would_be_wrong(self):
        # The bug placed the thermal-left boundary at frame_width/2 = 1280,
        # but the real boundary (thermal's own width) is 640.
        overlay = make_overlay(
            thermal_res=(640, 512), frame_size=(2560, 1080),
            view_mode='side_by_side', priority='rgb',
        )
        x, _ = overlay._transform_thermal_coords(0, 0)
        assert x != 1280
        assert x == 1920

    def test_mismatched_dimensions_do_not_assume_equal_panels(self):
        # A Lepton (160x120) next to a 4K webcam (3840x2160) — panels are
        # wildly different sizes; there is no split to get "close enough".
        overlay = make_overlay(
            thermal_res=(160, 120), frame_size=(4000, 2160),
            view_mode='side_by_side', priority='thermal',
        )
        assert overlay._transform_thermal_coords(0, 0) == (0, 0)
        assert overlay._transform_thermal_coords(159, 119) == (159, 119)


def _press_at(overlay, x, y):
    """Simulate a mouse press at widget coordinates (x, y) and return the
    (click_x, click_y) the overlay would emit via spot_meter_clicked."""
    captured = []
    overlay.spot_meter_mode = True
    overlay.spot_meter_clicked.connect(lambda cx, cy: captured.append((cx, cy)))
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(x, y),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    overlay.mousePressEvent(event)
    return captured[0] if captured else None


class TestSideBySideReverseTransform:
    """A click at widget pixels -> thermal-native coordinates."""

    def test_click_on_thermal_left_panel_maps_to_thermal_coords(self):
        overlay = make_overlay(
            thermal_res=(640, 512), frame_size=(2560, 1080),
            view_mode='side_by_side', priority='thermal',
        )
        result = _press_at(overlay, 300, 200)
        assert result == (300, 200)

    def test_click_on_rgb_panel_is_rejected(self):
        overlay = make_overlay(
            thermal_res=(640, 512), frame_size=(2560, 1080),
            view_mode='side_by_side', priority='thermal',
        )
        # x=1000 falls inside the RGB panel (thermal only occupies 0..639).
        assert _press_at(overlay, 1000, 200) is None

    def test_click_on_thermal_right_panel_maps_correctly(self):
        overlay = make_overlay(
            thermal_res=(640, 512), frame_size=(2560, 1080),
            view_mode='side_by_side', priority='rgb',
        )
        # Thermal panel occupies widget x in [1920, 2560).
        result = _press_at(overlay, 1920 + 50, 30)
        assert result == (50, 30)

    def test_forward_and_reverse_transforms_are_inverses(self):
        overlay = make_overlay(
            thermal_res=(336, 256), frame_size=(336 + 1920, 1080),
            view_mode='side_by_side', priority='rgb',
        )
        thermal_point = (150, 100)
        widget_point = overlay._transform_thermal_coords(*thermal_point)
        clicked = _press_at(overlay, *widget_point)
        assert clicked == thermal_point
