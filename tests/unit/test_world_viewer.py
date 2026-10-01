"""World viewer: picking maths (pure), and the widget under an offscreen Qt."""
import numpy as np
import pytest

from thermal_inspection.gui.widgets import world_viewer as wv
from thermal_inspection.processing.world_thermal import Marker, MeasureResult, ProbeResult

W, H = 400.0, 300.0


def _mvp():
    """A simple perspective looking down +y (GL scene), camera at the origin, 60 deg horizontal fov."""
    f = 1.0 / np.tan(np.radians(30))
    near, far = 0.1, 100.0
    aspect = W / H
    proj = np.array([[f, 0, 0, 0], [0, f * aspect, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)], [0, 0, -1, 0]])
    # view: scene +y (forward) -> camera -z, scene +z (up) -> camera +y, scene +x -> camera +x
    view = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
    return proj @ view


class TestCoordinates:
    def test_world_gl_round_trip(self):
        p = np.array([[1.0, 2.0, 3.0], [-1.0, 0.5, 2.0]])
        assert np.allclose(wv.from_gl(wv.to_gl(p)), p)
        assert np.allclose(wv.from_gl(wv.to_gl(p[0])), p[0])

    def test_world_y_down_becomes_gl_z_up(self):
        assert wv.to_gl(np.array([0.0, 1.0, 2.0]))[2] == -1.0           # 1 m below -> negative z
        assert wv.to_gl(np.array([0.0, 0.0, 2.0]))[1] == 2.0            # forward -> +y


class TestProjection:
    def test_point_ahead_lands_at_centre(self):
        xy, depth, vis = wv.project_to_screen(np.array([[0.0, 5.0, 0.0]]), _mvp(), W, H)
        assert vis[0] and np.allclose(xy[0], [W / 2, H / 2], atol=1e-6) and depth[0] > 0

    def test_right_of_centre_is_larger_x_and_up_is_smaller_y(self):
        xy, _, _ = wv.project_to_screen(np.array([[1.0, 5.0, 0.0], [0.0, 5.0, 1.0]]), _mvp(), W, H)
        assert xy[0, 0] > W / 2 and xy[1, 1] < H / 2

    def test_behind_camera_and_off_screen_not_visible(self):
        _, _, vis = wv.project_to_screen(np.array([[0.0, -5.0, 0.0], [50.0, 5.0, 0.0]]), _mvp(), W, H)
        assert not vis.any()


class TestPicking:
    def _cloud(self):
        return np.array([[0.0, 5.0, 0.0], [0.5, 5.0, 0.0], [0.0, 5.0, 0.5], [0.0, -3.0, 0.0]])

    def test_picks_nearest_within_radius(self):
        pts = self._cloud()
        xy, _, _ = wv.project_to_screen(pts, _mvp(), W, H)
        assert wv.pick_nearest(pts, _mvp(), (W, H), tuple(xy[1] + [3, 2])) == 1

    def test_miss_when_too_far(self):
        pts = self._cloud()
        assert wv.pick_nearest(pts, _mvp(), (W, H), (5.0, 5.0)) is None

    def test_behind_camera_point_ignored(self):
        pts = self._cloud()[3:]
        assert wv.pick_nearest(pts, _mvp(), (W, H), (W / 2, H / 2)) is None

    def test_near_surface_wins_when_two_points_overlap_on_screen(self):
        # two points on the same ray: the closer to the camera is the one you see
        pts = np.array([[0.0, 8.0, 0.0], [0.0, 3.0, 0.0]])
        assert wv.pick_nearest(pts, _mvp(), (W, H), (W / 2, H / 2)) == 1

    def test_empty(self):
        assert wv.pick_nearest(np.zeros((0, 3)), _mvp(), (W, H), (1, 1)) is None


class TestResolvePick:
    def _setup(self):
        world = np.array([[0.0, 0.0, 5.0], [0.3, 0.0, 5.0]])      # world coords (x right, y down, z forward)
        gl_pts = wv.to_gl(world)
        indices = np.array([100, 200])
        marker = Marker("H1", (0.3, 0.0, 5.0), 80.0, "hot", 777)  # sits on the second cloud point but has its own index
        return gl_pts, indices, [marker]

    def test_snap_prefers_marker_within_radius(self):
        gl_pts, indices, markers = self._setup()
        xy, _, _ = wv.project_to_screen(gl_pts, _mvp(), W, H)
        cursor = tuple(xy[1] + [16, 0])                          # 16 px off: outside the 12 px pick radius, inside the 22 px snap radius
        r = wv.resolve_pick(gl_pts, indices, markers, _mvp(), (W, H), cursor, snap=True)
        assert r.source == "marker" and r.index == 777

    def test_snap_off_uses_plain_point_only(self):
        gl_pts, indices, markers = self._setup()
        xy, _, _ = wv.project_to_screen(gl_pts, _mvp(), W, H)
        r = wv.resolve_pick(gl_pts, indices, markers, _mvp(), (W, H), tuple(xy[1] + [2, 0]), snap=False)
        assert r.source == "cloud" and r.index == 200
        assert wv.resolve_pick(gl_pts, indices, markers, _mvp(), (W, H), tuple(xy[1] + [16, 0]), snap=False) is None

    def test_cloud_pick_returns_full_world_index_and_world_xyz(self):
        gl_pts, indices, _ = self._setup()
        xy, _, _ = wv.project_to_screen(gl_pts, _mvp(), W, H)
        r = wv.resolve_pick(gl_pts, indices, [], _mvp(), (W, H), tuple(xy[0]), snap=True)
        assert r.index == 100 and r.xyz == pytest.approx((0.0, 0.0, 5.0))

    def test_nothing_hit(self):
        gl_pts, indices, markers = self._setup()
        assert wv.resolve_pick(gl_pts, indices, markers, _mvp(), (W, H), (1.0, 1.0)) is None


def test_frustum_has_apex_and_rectangle():
    seg = wv.frustum_lines(np.eye(4))
    assert seg.shape == (16, 3)                                   # 4 edges to the corners + 4 rectangle sides, as pairs
    assert np.allclose(seg[0], [0, 0, 0])                         # apex at the camera position


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestWidget:
    def _viewer(self, qapp):
        v = wv.WorldViewer()
        v.resize(800, 600)
        return v

    def test_constructs_and_accepts_data(self, qapp):
        v = self._viewer(qapp)
        pts = np.random.default_rng(0).uniform(-1, 1, (500, 3)).astype(np.float32)
        v.set_world(pts, np.full((500, 3), 0.5, np.float32), np.arange(500) * 3)
        v.set_markers([Marker("H1", (0.0, 0.0, 1.0), 80.0, "hot", 5)])
        v.set_camera_pose(np.eye(4), "good")
        v.set_legend("peak", 20.0, 80.0, "F")
        assert "176.0" in v._legend_hi.text() and "68.0" in v._legend_lo.text()
        assert v._legend.isHidden() is False
        v.set_legend("colour", None, None)
        assert v._legend.isHidden()

    def test_probe_card_shows_units_and_distances(self, qapp):
        v = self._viewer(qapp)
        v.show_probe(ProbeResult(3, (0.5, -0.2, 2.0), 1.25, 80.0, 90.0, 5.0, True), "F")
        t = v._card.text()
        assert "176.0" in t and "194.0" in t and "+9.0" in t       # temp, peak (F), change (delta scaled by 1.8)
        assert "1.25 m (4 ft 1 in)" in t
        v.show_probe(ProbeResult(3, (0, 0, 2.0), None, None, None, None, False), "C")
        assert "No temperature recorded" in v._card.text()
        v.show_probe(None)
        assert v._card.isHidden()

    def test_measure_card(self, qapp):
        v = self._viewer(qapp)
        v.show_measure(MeasureResult(1, 2, 0.38, 12.0), "C")
        assert "38 cm (1 ft 3 in)" in v._card.text() and "+12.0" in v._card.text()
        v.show_measure(MeasureResult(1, 2, 2.0, None), "C")
        assert "Temperature difference" not in v._card.text()

    def test_click_emits_probe_with_full_world_index(self, qapp):
        v = self._viewer(qapp)
        if v._view is None:
            pytest.skip("no GL")
        pts = np.array([[0.0, 0.0, 3.0], [1.0, 0.0, 3.0], [-1.0, 0.0, 3.0]], np.float32)
        v.set_world(pts, np.ones((3, 3), np.float32), np.array([11, 22, 33]))
        mvp, size = v._current_mvp()
        xy, _, vis = wv.project_to_screen(v._points_gl, mvp, *size)
        k = int(np.where(vis)[0][0])
        got = []
        v.probe_requested.connect(got.append)
        from PyQt6.QtCore import QPointF, Qt
        v._on_click(QPointF(float(xy[k, 0]), float(xy[k, 1])), Qt.KeyboardModifier.NoModifier)
        assert got == [[11, 22, 33][k]]

    def test_measure_flow_two_clicks_then_restart(self, qapp):
        v = self._viewer(qapp)
        if v._view is None:
            pytest.skip("no GL")
        pts = np.array([[0.0, 0.0, 3.0], [0.4, 0.0, 3.0]], np.float32)
        v.set_world(pts, np.ones((2, 3), np.float32), np.array([1, 2]))
        mvp, size = v._current_mvp()
        xy, _, vis = wv.project_to_screen(v._points_gl, mvp, *size)
        if not vis.all():
            pytest.skip("points not both on screen at the default camera")
        from PyQt6.QtCore import QPointF, Qt
        done = []
        v.measure_completed.connect(lambda a, b: done.append((a, b)))
        v.set_measure_mode(True)
        v._on_click(QPointF(*xy[0]), Qt.KeyboardModifier.NoModifier)
        assert done == []
        v._on_click(QPointF(*xy[1]), Qt.KeyboardModifier.NoModifier)
        assert done == [(1, 2)]
        v._on_click(QPointF(*xy[0]), Qt.KeyboardModifier.NoModifier)          # third click starts over, no new result
        assert done == [(1, 2)]
        v.set_measure_mode(False)

    def test_escape_cancels_measure(self, qapp):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeyEvent
        from PyQt6.QtCore import QEvent
        v = self._viewer(qapp)
        v.set_measure_mode(True)
        v._measure_a = wv.PickResult(1, (0, 0, 1), "cloud")
        v.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        assert v._measure_a is None

    def test_snap_toggle_round_trips(self, qapp):
        v = self._viewer(qapp)
        assert v.snap_enabled
        seen = []
        v.snap_changed.connect(seen.append)
        v.set_snap_enabled(False)
        assert not v.snap_enabled and seen == [False]

    def test_unit_change_rerenders_open_card(self, qapp):
        v = self._viewer(qapp)
        v.show_probe(ProbeResult(3, (0.5, -0.2, 2.0), 1.25, 80.0, 90.0, 5.0, True), "C")
        assert "80.0" in v._card.text() and "176.0" not in v._card.text()
        v.set_unit("F")
        assert "176.0" in v._card.text() and "+9.0" in v._card.text()
        v.show_probe(None)
        v.set_unit("K")                                              # nothing open: must not crash or reopen
        assert v._card.isHidden()

    def test_marker_labels_follow_markers_and_clear(self, qapp):
        v = self._viewer(qapp)
        if v._view is None:
            pytest.skip("no GL")
        v.set_world(np.array([[0.0, 0.0, 3.0]], np.float32), np.ones((1, 3), np.float32))
        marks = [Marker("H1", (0.0, 0.0, 3.0), 80.0, "hot", 0), Marker("C1", (0.5, 0.0, 3.0), -5.0, "cool", 1)]
        v.set_markers(marks)
        assert [l.text() for l in v._marker_labels] == ["H1", "C1"] and v._label_timer.isActive()
        v.set_markers([])
        assert v._marker_labels == [] and not v._label_timer.isActive()

