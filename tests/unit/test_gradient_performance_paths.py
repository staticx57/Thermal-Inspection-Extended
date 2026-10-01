"""
The gradient overlay runs on every displayed frame, so its hot path is sparse and cached. These tests pin down that
the optimised path still produces *exactly* what the straightforward dense computation does, and that the caching,
throttling and batched arrow drawing behave as designed.
"""

import cv2
import numpy as np
import pytest

from thermal_inspection.processing import gradient_processor as gp_mod
from thermal_inspection.processing.gradient_processor import GradientProcessor


def _scene(h=96, w=128, seed=0):
    rng = np.random.default_rng(seed)
    base = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 6) * 1200
    obj = np.zeros((h, w), np.float32)
    cv2.ellipse(obj, (w // 2, h // 2), (w // 4, h // 3), 25, 0, 360, 1.0, -1)
    obj = cv2.GaussianBlur(obj, (0, 0), 1.2) * 900
    y16 = (29815 + base * 0.15 + obj + rng.normal(0, 4, (h, w))).astype(np.uint16)
    disp = cv2.applyColorMap(cv2.normalize(y16.astype(np.float32), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8),
                             cv2.COLORMAP_INFERNO)
    return disp, y16


def _dense_reference(gp, display, source):
    """The original, unoptimised formulation: whole-frame float maths, written independently of the fast path."""
    s = gp._settings
    values, per_count = gp._to_float(source)
    gx, gy = gp._derivatives(values, per_count, display.shape[:2], source.shape[:2])
    if s.mode == "horizontal":
        mag = np.abs(gx)
    elif s.mode == "vertical":
        mag = np.abs(gy)
    else:
        mag = np.sqrt(gx ** 2 + gy ** 2)
    eff = gp.effective_threshold()
    mask = (mag >= eff) & (mag > 0)
    hi = max(float(np.percentile(mag[mask], 99)) if mask.any() else 0.0, eff * 1.5, 1e-6)   # first frame: no smoothing yet
    norm = np.clip(mag / hi, 0.0, 1.0).astype(np.float32)
    gray = (norm * 255).astype(np.uint8)
    overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if s.colormap == "gray" else \
        cv2.applyColorMap(gray, gp_mod._COLORMAP_IDS[s.colormap])
    alpha = s.alpha * mask.astype(np.float32) * (0.4 + 0.6 * norm)
    a = alpha[..., None]
    out = display.astype(np.float32) * (1.0 - a) + overlay.astype(np.float32) * a
    return np.clip(out, 0, 255).astype(np.uint8)


@pytest.mark.unit
class TestExactlyMatchesTheDenseComputation:
    @pytest.mark.parametrize("mode", ["magnitude", "horizontal", "vertical"])
    @pytest.mark.parametrize("colormap", ["hot", "cool", "jet", "viridis", "gray"])
    @pytest.mark.parametrize("kind", ["y16", "u8", "u8_bgr"])
    def test_blend_is_bit_identical(self, mode, colormap, kind):
        disp, y16 = _scene()
        src = {"y16": y16, "u8": (y16 >> 6).astype(np.uint8),
               "u8_bgr": cv2.merge([(y16 >> 6).astype(np.uint8)] * 3)}[kind]
        threshold = 0.2 if kind == "y16" else 4.0
        gp = GradientProcessor()
        gp.update_settings(enabled=True, mode=mode, colormap=colormap, threshold=threshold, sensitivity=60)
        expected = _dense_reference(gp, disp, src)
        got = gp.blend(disp, src)
        assert np.array_equal(got, expected), f"max diff {np.abs(got.astype(int) - expected.astype(int)).max()}"
        assert not np.array_equal(got, disp), "test scene should actually trigger the overlay"

    def test_display_and_source_of_different_sizes(self):
        disp, y16 = _scene(96, 128)
        disp = cv2.resize(disp, (256, 192))
        gp = GradientProcessor()
        gp.update_settings(enabled=True, mode="magnitude", threshold=0.2)
        assert np.array_equal(gp.blend(disp, y16), _dense_reference(gp, disp, y16))

    def test_only_tinted_pixels_change(self):
        disp, y16 = _scene()
        gp = GradientProcessor()
        gp.update_settings(enabled=True, threshold=0.3)
        out = gp.blend(disp, y16)
        changed = (out != disp).any(axis=-1)
        assert 0 < changed.mean() < 0.5
        assert np.array_equal(out[~changed], disp[~changed])


def _count_recomputes(gp):
    calls = {"n": 0}
    original = gp._build_layers

    def counting(*a, **k):
        calls["n"] += 1
        return original(*a, **k)

    gp._build_layers = counting
    return calls


@pytest.mark.unit
class TestFrameReuse:
    def test_identical_frame_is_computed_once(self):
        disp, y16 = _scene()
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        calls = _count_recomputes(gp)
        first = gp.blend(disp, y16)
        for _ in range(5):
            assert np.array_equal(gp.blend(disp, y16.copy()), first)        # equal content, different object
        assert calls["n"] == 1

    def test_a_new_frame_recomputes(self):
        d, a = _scene(seed=1)
        _, b = _scene(seed=2)
        gp = GradientProcessor()
        gp.update_settings(enabled=True, min_interval_s=0.0)
        gp._last_cost_s = 0.0                                                # no cost-based throttle
        calls = _count_recomputes(gp)
        gp.blend(d, a)
        gp.blend(d, b)
        assert calls["n"] == 2

    def test_reused_capture_buffer_mutated_in_place_is_not_mistaken_for_the_same_frame(self):
        """Capture code reuses its frame buffers - identity alone can't prove 'same frame'."""
        d, a = _scene(seed=1)
        _, b = _scene(seed=2)
        buf = a.copy()
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        gp._last_cost_s = 0.0
        first = gp.blend(d, buf)
        buf[:] = b                                                           # same array object, new content
        second = gp.blend(d, buf)
        assert not np.array_equal(first, second)
        assert np.array_equal(second, gp.blend(d, b))

    def test_settings_change_invalidates_the_cache(self):
        disp, y16 = _scene()
        gp = GradientProcessor()
        gp.update_settings(enabled=True, threshold=0.2)
        low = gp.blend(disp, y16)
        gp.update_settings(threshold=50.0)
        assert np.array_equal(gp.blend(disp, y16), disp)                     # nothing passes now
        gp.update_settings(threshold=0.2)
        assert np.array_equal(gp.blend(disp, y16), low)

    def test_returned_frame_is_a_copy_so_downstream_drawing_cannot_corrupt_the_cache(self):
        disp, y16 = _scene()
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        out = gp.blend(disp, y16)
        reference = out.copy()
        out[:] = 0                                                           # downstream code scribbles on it
        assert np.array_equal(gp.blend(disp, y16), reference)
        assert not np.shares_memory(gp.blend(disp, y16), disp)


@pytest.mark.unit
class TestThrottling:
    def test_explicit_min_interval_reuses_the_overlay_for_different_frames(self):
        d, a = _scene(seed=1)
        _, b = _scene(seed=2)
        gp = GradientProcessor()
        gp.update_settings(enabled=True, min_interval_s=60.0)
        calls = _count_recomputes(gp)
        gp.blend(d, a)
        gp.blend(d, b)
        assert calls["n"] == 1

    def test_cheap_recomputes_are_never_throttled(self):
        d, a = _scene(seed=1)
        _, b = _scene(seed=2)
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        calls = _count_recomputes(gp)
        gp.blend(d, a)
        gp._last_cost_s = 0.0002                                             # a fraction of a millisecond
        gp.blend(d, b)
        assert calls["n"] == 2

    def test_expensive_recomputes_are_held_to_a_budget(self):
        d, a = _scene(seed=1)
        _, b = _scene(seed=2)
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        calls = _count_recomputes(gp)
        gp.blend(d, a)
        gp._last_cost_s = 0.007                                              # ~7 ms: a large sensor
        gp.blend(d, b)                                                       # immediately after: reuse
        assert calls["n"] == 1
        assert gp_mod.AUTO_MAX_INTERVAL_S <= 0.05                            # lag is bounded

    def _slow_build(self, gp, slow_calls):
        """Make _build_layers take ~8 ms on the given (1-based) call numbers; return the call counter."""
        import time as _time
        calls = {"n": 0}
        original = gp._build_layers

        def slow(*a, **k):
            calls["n"] += 1
            if calls["n"] in slow_calls:
                _time.sleep(0.008)
            return original(*a, **k)

        gp._build_layers = slow
        return calls

    def test_one_slow_outlier_does_not_throttle(self):
        """A cold-cache / busy-machine first call must not make a cheap frame size look expensive."""
        d, a = _scene(seed=1)
        _, b = _scene(seed=2)
        _, c = _scene(seed=3)
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        calls = self._slow_build(gp, slow_calls={1})
        gp.blend(d, a)
        gp.blend(d, b)
        gp.blend(d, c)
        assert calls["n"] == 3

    def test_consecutive_slow_recomputes_are_throttled(self):
        d, a = _scene(seed=1)
        _, b = _scene(seed=2)
        _, c = _scene(seed=3)
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        calls = self._slow_build(gp, slow_calls={1, 2, 3})
        gp.blend(d, a)           # slow, first measurement
        gp.blend(d, b)           # slow again: now it is clear this frame size is expensive
        gp.blend(d, c)           # immediately after: reuse instead of a third expensive recompute
        assert calls["n"] == 2

    def test_throttle_interval_is_capped(self):
        assert min(gp_mod.AUTO_MAX_INTERVAL_S, 10.0 / gp_mod.AUTO_BUDGET) == gp_mod.AUTO_MAX_INTERVAL_S


@pytest.mark.unit
class TestArrowBatching:
    def test_arrow_field_uses_a_few_batched_draw_calls(self, monkeypatch):
        disp = np.zeros((256, 320, 3), np.uint8)
        y16 = np.full((256, 320), 29815, np.uint16)
        yy, xx = np.mgrid[0:256, 0:320]
        y16 = (y16 + (xx * 3)).astype(np.uint16)                             # a steady ramp: arrows everywhere
        gp = GradientProcessor()
        gp.update_settings(enabled=True, mode="both", threshold=0.05, sensitivity=90, colormap="gray")
        calls = {"n": 0}
        real = cv2.polylines

        def counting(*a, **k):
            calls["n"] += 1
            return real(*a, **k)

        monkeypatch.setattr(gp_mod.cv2, "polylines", counting)
        out = gp.blend(disp, y16)
        assert out.any(), "arrows should be drawn"
        assert calls["n"] <= 20, f"{calls['n']} polylines calls - arrows must be batched, not drawn one by one"

    def test_arrows_are_drawn_only_near_the_gradient(self):
        disp = np.zeros((128, 128, 3), np.uint8)
        src = np.full((128, 128), 29815, np.uint16)
        src[:, 64:] += 1200                                                   # hot on the right
        gp = GradientProcessor()
        gp.update_settings(enabled=True, mode="both", threshold=0.3, sensitivity=70, colormap="gray")
        out = gp.blend(disp, src).astype(int).sum(axis=2)
        assert out.any()
        # arrows exist only where the gradient is (near the step), none in the flat regions
        assert out[:, :40].sum() == 0 and out[:, 90:].sum() == 0


@pytest.mark.unit
class TestSceneStats:
    def test_none_before_any_frame(self):
        assert GradientProcessor().scene_stats() is None

    def test_reports_typical_and_strong_gradient_in_processor_units(self):
        disp, y16 = _scene()
        gp = GradientProcessor()
        gp.update_settings(enabled=True)
        gp.blend(disp, y16)
        stats = gp.scene_stats()
        assert stats and set(stats) == {"p50", "p90", "p99"}
        assert 0 <= stats["p50"] <= stats["p90"] <= stats["p99"]
        # flat-ish sensor noise is ~0.04 C/px; the warm object's edge is far stronger
        assert stats["p50"] < 0.3 < stats["p99"]

    def test_does_not_depend_on_the_threshold(self):
        disp, y16 = _scene()
        a, b = GradientProcessor(), GradientProcessor()
        a.update_settings(enabled=True, threshold=0.05)
        b.update_settings(enabled=True, threshold=40.0)             # nothing passes: still reports the scene
        a.blend(disp, y16)
        b.blend(disp, y16)
        assert a.scene_stats() == b.scene_stats()

    def test_panel_shows_it_in_the_selected_unit(self, qapp):
        from thermal_inspection.gui.panels.gradient_overlay_panel import GradientOverlayPanel
        panel = GradientOverlayPanel()
        panel.set_scene_stats({"p50": 0.04, "p90": 0.12, "p99": 0.5})
        assert "0.04" in panel.scene_label.text() and "0.50" in panel.scene_label.text()
        assert "°C/px" in panel.scene_label.text()
        panel.set_temperature_unit("F")
        panel.set_scene_stats({"p50": 0.04, "p90": 0.12, "p99": 0.5})
        assert "0.07" in panel.scene_label.text() and "0.90" in panel.scene_label.text()
        assert "°F/px" in panel.scene_label.text()
        panel.set_radiometric(False)
        panel.set_scene_stats({"p50": 1.5, "p90": 3.0, "p99": 12.0})
        assert "counts/px" in panel.scene_label.text() and "12.00" in panel.scene_label.text()
        panel.set_scene_stats(None)
        assert panel.scene_label.text().endswith("--")
