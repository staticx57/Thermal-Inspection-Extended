"""Per-point temperature layer: pure-numpy behaviour plus end-to-end ground truth on the synthetic scene."""
import numpy as np
import pytest

from thermal_inspection.processing.world_thermal import WorldThermalLayer, project_visible

FXFYCXCY = (100.0, 100.0, 50.0, 50.0)


def _pts():
    return np.array([[0.0, 0.0, 2.0], [1.0, 0.0, 2.0], [0.0, 1.0, 2.0], [0.0, 0.0, -1.0]])


class TestProjection:
    def test_visible_points_and_pixels(self):
        idx, u, v = project_visible(_pts(), np.eye(4), FXFYCXCY, (100, 100))
        # (1,0,2) -> u=100 and (0,1,2) -> v=100 fall off a 100x100 frame; z<0 is behind the camera
        assert list(idx) == [0]
        assert (u[0], v[0]) == (50, 50)

    def test_occlusion_rejects_hidden_points(self):
        depth = np.full((100, 100), 1.0, np.float32)    # a wall at 1 m in front of the 2 m points
        idx, _, _ = project_visible(_pts(), np.eye(4), FXFYCXCY, (100, 100), depth_m=depth)
        assert idx.size == 0
        depth[:] = 2.0
        idx, _, _ = project_visible(_pts(), np.eye(4), FXFYCXCY, (100, 100), depth_m=depth)
        assert 0 in idx


class TestLayer:
    def test_update_peak_and_latest(self):
        L = WorldThermalLayer()
        pts = _pts()[:1]
        t = np.full((100, 100), 30.0, np.float32)
        assert L.update(pts, np.eye(4), t, FXFYCXCY) == 1
        t[:] = 20.0
        L.update(pts, np.eye(4), t, FXFYCXCY)
        assert L.latest[0] == 20.0 and L.peak[0] == 30.0

    def test_nonfinite_pixels_skipped(self):
        L = WorldThermalLayer()
        t = np.full((100, 100), np.nan, np.float32)
        assert L.update(_pts()[:1], np.eye(4), t, FXFYCXCY) == 0
        assert not L.has_data

    def test_hotspots_are_distinct_places(self):
        L = WorldThermalLayer()
        pts = np.array([[0, 0, 0], [0.01, 0, 0], [2, 0, 0], [4, 0, 0]], float)
        L.latest = L.peak = np.array([90, 89, 70, 50], np.float32)
        hs = L.hotspots(pts, count=3, min_separation_m=0.25)
        assert [round(h[0]) for h in hs] == [90, 70, 50]      # the 89 C neighbour is folded into the 90 C hotspot

    def test_changes_vs_baseline(self):
        L = WorldThermalLayer()
        pts = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], float)
        L.baseline = np.array([20, 20, 20], np.float32)
        L.latest = np.array([30, 20, 12], np.float32)
        warm, cool = L.changes(pts)
        assert warm[0][0] == 10 and cool[0][0] == -8
        assert len(warm) == 1 and len(cool) == 1             # the unchanged point is neither

    def test_colorize_modes(self):
        L = WorldThermalLayer()
        L.latest = L.peak = np.array([20, 40, np.nan], np.float32)
        c = L.colorize("temperature")
        assert c.shape == (3, 3) and np.allclose(c[2], 0.25)  # unmeasured: dark grey
        assert not np.allclose(c[0], c[1])
        assert L.colorize("change") is None                   # no baseline -> nothing to show

    def test_sidecar_round_trip_becomes_baseline(self, tmp_path):
        L = WorldThermalLayer()
        L.latest = np.array([20, 30, np.nan], np.float32)
        L.peak = np.array([25, 35, np.nan], np.float32)
        path = str(tmp_path / "w.ply.thermal.npz")
        L.save(path)
        M = WorldThermalLayer()
        assert M.load(path, 3)
        assert np.allclose(M.baseline[:2], [20, 30]) and np.isnan(M.latest).all()
        assert np.allclose(M.peak[:2], [25, 35])
        assert not WorldThermalLayer().load(path, 5)          # wrong point count: refuse, don't mis-assign

    def test_missing_or_corrupt_sidecar_is_ignored(self, tmp_path):
        bad = tmp_path / "x.npz"
        bad.write_bytes(b"not an npz")
        assert not WorldThermalLayer().load(str(bad), 3)
        assert not WorldThermalLayer().load(str(tmp_path / "nope.npz"), 3)

    def test_csv_export(self, tmp_path):
        L = WorldThermalLayer()
        L.latest = np.array([20, np.nan], np.float32)
        L.peak = np.array([25, np.nan], np.float32)
        path = tmp_path / "w.csv"
        L.export_csv(str(path), np.array([[0, 0, 1], [1, 1, 1]], float))
        lines = path.read_text().splitlines()
        assert lines[0].startswith("x_m") and lines[1].startswith("0.0000,0.0000,1.0000,20.0000,25.0000,")
        assert lines[2].endswith(",,,")                       # unmeasured point: blanks, not NaN text


pytest.importorskip("open3d")
from tests.unit import mapping_synth as ms  # noqa: E402


class TestEndToEnd:
    def _live_temps(self, wm, true_pose, seed=70, delta=None):
        color, depth, pts = ms.render(true_pose, noise=0.002, seed=seed, with_points=True)
        temp = ms.hot_temperature(pts)
        if delta is not None:
            temp = delta(temp)
        wm.track_and_texture(color, depth, texture_frame=color, temp_c=temp)

    def test_temperatures_land_on_the_right_surfaces(self):
        wm, _ = ms.mapped_world()
        wm._pose = ms.TRAJECTORY[0].copy()      # live tracking starts from where the camera really is
        for _ in range(3):
            self._live_temps(wm, ms.TRAJECTORY[0])
        L = wm.world.thermal
        assert L.coverage() > 0.2
        P = wm.world.points
        truth = ms.hot_temperature(P)
        # points within 5 cm of the patch boundary can legitimately fall either side (pose/depth noise)
        away = np.minimum(np.abs(P[:, 0] - 0.35), np.abs(P[:, 1] - 0.2)) >= 0.05
        m = np.isfinite(L.latest) & (away | (np.abs(P[:, 2] - 2.5) >= 0.05))
        agree = np.mean(np.abs(L.latest[m] - truth[m]) < 1.0)
        assert agree > 0.95, f"only {agree:.0%} of measured points carry the right temperature"
        hot = L.hotspots(wm.world.points, count=1)[0]
        assert hot[0] == pytest.approx(80.0, abs=1.0)
        assert hot[1][0] > 0.3 and hot[1][2] > 2.0           # located on the hot patch, in world coordinates

    def test_save_load_baseline_and_change_detection(self, tmp_path):
        wm, _ = ms.mapped_world()
        wm._pose = ms.TRAJECTORY[0].copy()      # live tracking starts from where the camera really is
        for _ in range(3):
            self._live_temps(wm, ms.TRAJECTORY[0])
        path = str(tmp_path / "w.ply")
        wm.world.save(path)
        wm2 = type(wm)(voxel_size=0.02, relocalize_async=False)
        wm2.load_from_path(path, ms.W, ms.H, ms.FX, ms.FY, ms.CX, ms.CY)
        L = wm2.world.thermal
        assert L.has_baseline and not L.has_data
        # re-visit from the same view, but the hot patch has cooled by 30 C
        wm2._pose = ms.TRAJECTORY[0].copy()
        for i in range(3):
            self._live_temps(wm2, ms.TRAJECTORY[0], seed=71 + i, delta=lambda t: t - 30.0 * (t > 50))
        warm, cool = L.changes(wm2.world.points)
        assert cool and cool[0][0] == pytest.approx(-30.0, abs=1.5)
        assert cool[0][1][0] > 0.3                            # the cooling is located on the (former) hot patch
        # away from the patch boundary nothing else changed
        P = wm2.world.points
        delta = L.values("change")
        away = np.minimum(np.abs(P[:, 0] - 0.35), np.abs(P[:, 1] - 0.2)) >= 0.05
        stable = np.isfinite(delta) & (away | (np.abs(P[:, 2] - 2.5) >= 0.05))
        assert np.mean(np.abs(delta[stable] + 30 * (ms.hot_temperature(P)[stable] > 50)) < 1.5) > 0.95

    def test_other_resolution_temperature_frame_is_resized(self):
        wm, _ = ms.mapped_world()
        wm._pose = ms.TRAJECTORY[0].copy()
        color, depth, pts = ms.render(ms.TRAJECTORY[0], noise=0.002, seed=72, with_points=True)
        small = ms.hot_temperature(pts)[::2, ::2]
        wm.track_and_texture(color, depth, texture_frame=color, temp_c=small)
        assert wm.world.thermal.has_data

    def test_summary_and_viewport_colours(self):
        wm, _ = ms.mapped_world()
        assert wm.thermal_summary() == ""                      # nothing recorded yet
        assert np.allclose(wm.viewport_colors("temperature"), wm.world.colors)   # falls back to texture colours
        wm._pose = ms.TRAJECTORY[0].copy()
        for _ in range(3):
            self._live_temps(wm, ms.TRAJECTORY[0])
        text = wm.thermal_summary()
        assert "Hottest places" in text and "80.0 °C" in text and "Warmer" not in text
        wm.temp_unit = "F"
        assert "176.0 °F" in wm.thermal_summary()      # follows the app's unit setting
        colours = wm.viewport_colors("peak")
        assert colours.shape == (wm.world.point_count, 3)
        assert not np.allclose(colours, wm.world.colors)
        assert np.allclose(wm.viewport_colors("colour"), wm.world.colors)

    # ---- viewer-facing queries ------------------------------------------------------------------------------

    def _mapped_with_temps(self):
        wm, _ = ms.mapped_world()
        wm._pose = ms.TRAJECTORY[0].copy()
        for _ in range(3):
            self._live_temps(wm, ms.TRAJECTORY[0])
        return wm

    def test_preview_cloud_indices_round_trip(self):
        wm = self._mapped_with_temps()
        pts, cols, idx = wm.preview_cloud(1000, "temperature")
        assert len(pts) == len(cols) == len(idx) <= 1000
        assert idx.max() < wm.world.point_count and np.all(np.diff(idx) > 0)
        assert np.allclose(pts, wm.world.points[idx].astype(np.float32))
        full_pts, _, full_idx = wm.preview_cloud(10 ** 9)
        assert len(full_pts) == wm.world.point_count and full_idx[0] == 0

    def test_probe_reports_known_temperature_position_and_distance(self):
        wm = self._mapped_with_temps()
        hot = wm.world.thermal.hotspots(wm.world.points, count=1)[0]
        r = wm.probe(hot[2])
        assert r.has_temp and r.peak == pytest.approx(80.0, abs=1.0)
        assert r.xyz == pytest.approx(tuple(hot[1]))
        cam = wm.camera_pose()[:3, 3]
        assert r.distance_from_camera == pytest.approx(float(np.linalg.norm(hot[1] - cam)))
        assert r.change is None                                   # no baseline loaded
        assert wm.probe(-1) is None and wm.probe(wm.world.point_count) is None

    def test_probe_of_unmeasured_point_says_so(self):
        wm, _ = ms.mapped_world()                                 # no temperatures recorded at all
        r = wm.probe(0)
        assert r is not None and not r.has_temp and r.temp is None and r.peak is None

    def test_measure_matches_geometry_and_temperature_difference(self):
        wm = self._mapped_with_temps()
        P = wm.world.points
        L = wm.world.thermal
        hot = int(np.nanargmax(L.latest))
        cold = int(np.nanargmin(L.latest))
        m = wm.measure(cold, hot)
        assert m.distance_m == pytest.approx(float(np.linalg.norm(P[hot] - P[cold])))
        assert m.delta_temp == pytest.approx(L.latest[hot] - L.latest[cold])
        assert wm.measure(0, 10 ** 9) is None
        unmeasured = int(np.where(~np.isfinite(L.latest))[0][0])
        assert wm.measure(unmeasured, hot).delta_temp is None

    def test_markers_and_legend(self):
        wm = self._mapped_with_temps()
        marks = wm.markers(3)
        assert marks and marks[0].label == "H1" and marks[0].kind == "hot"
        assert marks[0].value == pytest.approx(80.0, abs=1.0) and marks[0].index == wm.probe(marks[0].index).index
        assert wm.legend("colour") is None
        lo, hi = wm.legend("temperature")
        assert lo == pytest.approx(25.0, abs=0.5) and hi == pytest.approx(80.0, abs=0.5)
        assert wm.legend("change") is None                       # nothing to compare against yet
        wm2, _ = ms.mapped_world()
        assert wm2.markers() == [] and wm2.legend("peak") is None

    def test_markers_include_changes_against_a_loaded_world(self, tmp_path):
        wm = self._mapped_with_temps()
        path = str(tmp_path / "w.ply")
        wm.world.save(path)
        wm2 = type(wm)(voxel_size=0.02, relocalize_async=False)
        wm2.load_from_path(path, ms.W, ms.H, ms.FX, ms.FY, ms.CX, ms.CY)
        wm2._pose = ms.TRAJECTORY[0].copy()
        for i in range(3):
            self._live_temps(wm2, ms.TRAJECTORY[0], seed=80 + i, delta=lambda t: t - 30.0 * (t > 50))
        kinds = {m.kind for m in wm2.markers(3)}
        assert "cool" in kinds
        lo, hi = wm2.legend("change")
        assert lo == -hi and hi >= 1.0
