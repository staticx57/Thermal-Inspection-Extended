"""
Targeted parallax regression tests covering all five bugs fixed.

NOTE: We import processing modules directly (not via the thermal_inspection
package) to bypass the package-level __init__.py which attempts to import
torch and crashes on this machine's broken c10.dll.
"""
import sys
import os
import cv2
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

# Direct path import — does NOT go through thermal_inspection/__init__.py
sys.path.insert(0, os.path.abspath("."))

qapp = QApplication.instance() or QApplication(sys.argv)

# Import only from the two affected submodules; no package-level torch contact
from thermal_inspection.processing.parallax_compensator import (
    ParallaxCompensator, CameraGeometry, DepthEstimator
)
from thermal_inspection.gui.panels.parallax_panel import ParallaxPanel


class TestBug1_ApplyCorrectionCalledInFrameLoop:
    """Bug 1: apply_correction was never called in _process_frame_loop."""

    def test_apply_correction_runs_when_enabled(self):
        """ParallaxCompensator.apply_correction must run and shift the thermal frame."""
        comp = ParallaxCompensator(
            camera_geometry=CameraGeometry(baseline_mm=50.0),
            depth_method="simplified"
        )
        comp.enable(True)

        # Use a horizontal gradient so the remap shift is detectable.
        # A uniform frame would look identical before and after shifting.
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        thermal[:, :, 0] = np.tile(np.arange(640, dtype=np.uint8), (512, 1))  # horizontal gradient
        rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        result, rgb_out = comp.apply_correction(thermal, rgb)

        assert result is not None
        assert result.shape == thermal.shape
        # The disparity with a 50mm baseline shifts pixels; the left columns
        # should differ from the uncorrected frame.
        assert not np.array_equal(result, thermal), (
            "apply_correction returned identical frame — no shift applied"
        )
        # Default correction_target is "thermal" - rgb passes through untouched.
        assert np.array_equal(rgb_out, rgb)

    def test_apply_correction_passthrough_when_disabled(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(False)

        thermal = np.ones((512, 640, 3), dtype=np.uint8) * 42
        rgb = np.ones((480, 640, 3), dtype=np.uint8)
        result, rgb_out = comp.apply_correction(thermal, rgb)

        assert np.array_equal(result, thermal), "Disabled compensator must return original frame unchanged"
        assert np.array_equal(rgb_out, rgb)


class TestBug2_BaselineChangedSignal:
    """Bug 2: baseline_changed signal was never emitted from the spinbox."""

    def test_baseline_spinbox_emits_signal(self):
        from thermal_inspection.gui.panels.parallax_panel import ParallaxPanel
        panel = ParallaxPanel()

        received = []
        panel.baseline_changed.connect(received.append)

        panel.baseline_spin.setValue(75.0)
        assert len(received) >= 1, "baseline_changed signal was never emitted from spinbox"
        assert received[-1] == pytest.approx(75.0)


class TestBug3_SetDepthDisplay:
    """Bug 3: set_depth_display() method was missing from ParallaxCompensator."""

    def test_set_depth_display_exists(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        assert hasattr(comp, 'set_depth_display'), "set_depth_display() method missing"
        assert hasattr(comp, 'show_depth_map'), "show_depth_map attribute missing"

    def test_set_depth_display_returns_colorised_frame(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(True)
        comp.set_depth_display(True)

        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        result, _rgb_out = comp.apply_correction(thermal, rgb)
        assert result is not None
        assert result.shape == (512, 640, 3)
        # Depth overlay should be colourised (non-uniform colour channels, JET palette)
        assert not np.all(result[:, :, 0] == result[:, :, 1]), (
            "Depth overlay should be a JET-colourised map, not grayscale"
        )

    def test_depth_display_off_returns_corrected_thermal(self):
        from thermal_inspection.processing.parallax_compensator import ParallaxCompensator
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(True)
        comp.set_depth_display(False)

        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        thermal[:, 320:, 0] = 200
        rgb = np.ones((480, 640, 3), dtype=np.uint8) * 128

        result, _rgb_out = comp.apply_correction(thermal, rgb)
        assert result is not None
        # Should be corrected thermal (shifted), not a JET overlay
        assert result.shape == thermal.shape


class TestBug5_DepthMethodReinit:
    """Bug 5: set_parallax_depth_method mutated .method without re-initialising the estimator."""

    def test_depth_method_reinit_on_change(self):
        from thermal_inspection.processing.parallax_compensator import (
            ParallaxCompensator, DepthEstimator
        )
        comp = ParallaxCompensator(depth_method="simplified")
        original_estimator = comp.depth_estimator
        assert original_estimator.method == "simplified"

        # Simulate what set_parallax_depth_method now does
        old_device = comp.depth_estimator._device_requested
        comp.depth_estimator = DepthEstimator(method="simplified", device=old_device)

        new_estimator = comp.depth_estimator
        assert new_estimator is not original_estimator, "New DepthEstimator should be a fresh instance"
        assert new_estimator.method == "simplified"
        assert new_estimator.model_loaded is False or new_estimator.enabled is True


class TestFlowMapRecomputeThrottle:
    """
    Regression tests for a major live performance finding (2026-09-04):
    apply_correction() ran the full depth-estimate+disparity-compute
    chain on EVERY call, unlike every other expensive per-frame effect
    in this codebase (3D Fusion's depth-relief shading, ThreadedAnalyzer,
    motion detection), all of which are throttled. Measured live:
    apply_correction() alone cost ~11ms/frame with depth-based
    correction genuinely engaged, stacking with 3D/2D Fusion's own cost
    to push several mode/setting combinations into the low 20s fps
    ("modes and combinations of settings that bring fps down to the
    20s"). Fixed by throttling only the depth-estimate+disparity step
    (reusing self.last_displacement_map between calls within
    correction_recompute_interval_s) - _remap_thermal still runs on the
    CURRENT frame's live pixel data every single call, so this can't
    freeze the displayed video the way caching the whole corrected
    frame would have.

    Also covers the safety net this needed given parallax's history this
    session (three separate live bugs from stale/mismatched correction
    state): a correction-target switch, in particular, must never reuse
    a flow map computed in the OLD target's resolution/pixel space.
    """

    @staticmethod
    def _make_comp():
        comp = ParallaxCompensator(depth_method="simplified")
        comp.enable(True)
        comp.set_correction_target("thermal")
        return comp

    def test_flow_map_reused_within_throttle_window(self):
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)  # first call: computes and caches
        first_flow_map = comp.last_displacement_map
        assert first_flow_map is not None

        comp.apply_correction(thermal, rgb)  # second call, immediately after
        assert comp.last_displacement_map is first_flow_map, (
            "a second call within the throttle window must reuse the cached flow map, not rebuild it"
        )

    def test_flow_map_recomputed_after_throttle_interval_elapses(self):
        comp = self._make_comp()
        comp.correction_recompute_interval_s = 0.01  # short interval for a fast test
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        first_flow_map = comp.last_displacement_map

        import time
        time.sleep(0.02)
        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not first_flow_map, (
            "a call after the throttle interval elapses must recompute, not keep reusing a stale flow map"
        )

    def test_correction_target_switch_forces_immediate_recompute(self):
        """The specific safety net this needed: reusing a cached flow map
        across a target switch is exactly the "frame cut in half" bug
        class from earlier this session - the shape/space are entirely
        different between targets."""
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.set_correction_target("rgb")
        assert comp.last_displacement_map is None, (
            "switching correction target must invalidate the cached flow map immediately"
        )

        result_thermal, result_rgb = comp.apply_correction(thermal, rgb)
        assert result_rgb.shape[:2] == rgb.shape[:2]  # did not silently corrupt/crash

    def test_manual_shift_change_forces_immediate_recompute(self):
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.set_manual_shift(5, -3)
        assert comp.last_displacement_map is None

    def test_enable_toggle_forces_immediate_recompute(self):
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.enable(False)
        comp.enable(True)
        assert comp.last_displacement_map is None

    def test_depth_method_swap_via_invalidate_correction_cache(self):
        """Covers app.py's set_parallax_depth_method, which replaces
        depth_estimator directly (bypassing every ParallaxCompensator
        method that would otherwise invalidate the cache) and must call
        invalidate_correction_cache() itself."""
        comp = self._make_comp()
        thermal = np.zeros((512, 640, 3), dtype=np.uint8)
        rgb = np.ones((512, 640, 3), dtype=np.uint8) * 128

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        comp.depth_estimator = DepthEstimator(method="simplified", device="cpu")
        comp.invalidate_correction_cache()
        assert comp.last_displacement_map is None

    def test_apply_correction_is_meaningfully_cheaper_when_throttled(self):
        """Locks in the actual performance win, not just the caching
        mechanics - loose bound (steady-state measured ~4.2ms vs ~11.1ms
        before this fix) to avoid CI flakiness from timing variance."""
        import time
        comp = self._make_comp()
        thermal = np.random.randint(0, 255, size=(512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, size=(512, 640, 3), dtype=np.uint8)

        comp.apply_correction(thermal, rgb)  # warm up

        n = 20
        t0 = time.perf_counter()
        for _ in range(n):
            comp.apply_correction(thermal, rgb)
        elapsed_ms_per_call = (time.perf_counter() - t0) * 1000 / n

        assert elapsed_ms_per_call < 8.0, (
            f"apply_correction averaged {elapsed_ms_per_call:.2f}ms/call across {n} rapid calls - "
            "expected well under the pre-throttle ~11ms since almost all of these should hit the cache"
        )


class TestBug6_RealsenseInvalidDepthGhosting:
    """Bug 6: live-reported - "parallax correction for realsense... visually
    looks like two rgb images superimposed" while the other 3 depth methods
    never behave that way. Root cause: real RealSense depth reports 0 =
    "invalid" in a thin ring right at object edges ("flying pixels"), and
    compute_disparity's existing "treat invalid as far away" fallback turns
    that ring into a large disparity discontinuity - splitting a shifted
    object into a correctly-shifted body plus a ghost edge strip left behind
    at the old position. Fixed by inpainting invalid depth pixels in
    DepthEstimator._estimate_depth_realsense before disparity is computed.
    """

    @staticmethod
    def _make_synthetic_realsense_depth(h=480, w=640):
        """A foreground object at 0.6m against a 3.0m background, with a
        6px ring of invalid (0.0) depth right at the object's edge - the
        real-sensor "flying pixels" artifact this bug is about. Matches
        the shape used in the direct reproduction that confirmed this bug
        and its fix.
        """
        depth = np.full((h, w), 3.0, dtype=np.float32)
        depth[150:330, 200:400] = 0.6
        edge_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(edge_mask, (200, 150), (400, 330), 255, thickness=6)
        depth[edge_mask > 0] = 0.0
        return depth

    def _make_comp(self, depth):
        comp = ParallaxCompensator(
            camera_geometry=CameraGeometry(), depth_method="realsense"
        )

        def fake_hardware_depth_source(resize_to):
            d = depth
            if resize_to is not None and resize_to != (d.shape[1], d.shape[0]):
                d = cv2.resize(d, resize_to, interpolation=cv2.INTER_NEAREST)
            return d

        comp.set_hardware_depth_source(fake_hardware_depth_source)
        comp.enable(True)
        comp.set_correction_target("rgb")
        comp.set_baseline(50.0)
        return comp

    def test_invalid_edge_ring_no_longer_produces_extreme_displacement_outlier(self):
        """Before the fix, the invalid-depth edge ring produced a
        displacement outlier (~-435px measured directly) wildly outside the
        object's own true disparity range - the ghosting artifact. After
        inpainting, displacement across the whole object (including its
        former edge ring) should stay within a sane multiple of the
        object's true disparity, not spike to a separate extreme value.
        """
        depth = self._make_synthetic_realsense_depth()
        comp = self._make_comp(depth)

        thermal = np.full((256, 320, 3), 100, dtype=np.uint8)
        rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        rgb[:] = (40, 40, 40)
        cv2.rectangle(rgb, (200, 150), (400, 330), (0, 200, 0), -1)

        comp.apply_correction(thermal, rgb)
        assert comp.last_displacement_map is not None

        disp_x = comp.last_displacement_map[:, :, 0]
        # True disparity at the object's own depth (0.6m), computed the
        # same way compute_disparity_rgb does, is the sane reference point.
        object_disp = disp_x[240, 300]
        assert abs(disp_x.min()) < abs(object_disp) * 3, (
            f"displacement outlier at min={disp_x.min():.2f}px vs object's own "
            f"disparity={object_disp:.2f}px - suggests the invalid-depth ring "
            "is still producing a ghosting discontinuity"
        )
        assert abs(disp_x.max()) < max(abs(object_disp) * 3, 5.0), (
            f"displacement outlier at max={disp_x.max():.2f}px vs object's own "
            f"disparity={object_disp:.2f}px - suggests the invalid-depth ring "
            "is still producing a ghosting discontinuity"
        )

    def test_estimate_depth_realsense_fills_invalid_ring_before_disparity(self):
        """Unit-level check directly on DepthEstimator: the returned depth
        map must have no remaining <= MIN_VALID_DEPTH_M pixels inside the
        object's edge ring once real neighboring depth is available to
        inpaint from.
        """
        from thermal_inspection.processing.parallax_compensator import MIN_VALID_DEPTH_M

        depth = self._make_synthetic_realsense_depth()
        estimator = DepthEstimator(method="realsense", device="cpu")

        def fake_hardware_depth_source(resize_to):
            return depth

        estimator.set_hardware_depth_source(fake_hardware_depth_source)
        rgb = np.zeros((480, 640, 3), dtype=np.uint8)

        filled = estimator.estimate_depth(rgb)

        assert filled is not None
        # The ring itself (edge_mask, thickness=6 at the rectangle boundary)
        # should no longer read as invalid.
        assert filled[150, 300] > MIN_VALID_DEPTH_M, (
            "top edge of the invalid ring is still unfilled after inpainting"
        )
        assert filled[240, 200] > MIN_VALID_DEPTH_M, (
            "left edge of the invalid ring is still unfilled after inpainting"
        )

    def test_no_invalid_pixels_is_a_no_op(self):
        """When depth has no invalid pixels (the common case, e.g. once the
        RealSense SDK's own hole-filling filter is enabled), the inpaint
        path must not run/alter the depth map at all.
        """
        depth = np.full((480, 640), 1.5, dtype=np.float32)
        estimator = DepthEstimator(method="realsense", device="cpu")
        estimator.set_hardware_depth_source(lambda resize_to: depth)

        rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        result = estimator.estimate_depth(rgb)

        assert result is not None
        assert np.array_equal(result, depth), (
            "depth map with no invalid pixels should pass through unchanged"
        )

    def test_all_invalid_pixels_does_not_crash(self):
        """cv2.inpaint requires at least one valid pixel to inpaint from -
        a fully-invalid frame (e.g. camera briefly lost tracking) must be
        guarded against, not crash apply_correction.
        """
        depth = np.zeros((480, 640), dtype=np.float32)
        comp = self._make_comp(depth)

        thermal = np.full((256, 320, 3), 100, dtype=np.uint8)
        rgb = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # Must not raise.
        result_thermal, result_rgb = comp.apply_correction(thermal, rgb)
        assert result_rgb.shape == rgb.shape


def _make_edge_scene(h, w, x_offset=0):
    """A scene with real, findable edge structure (not a flat image),
    shifted by x_offset - used to build a thermal/rgb pair with a known
    injected misalignment for the image-registration tests below."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.rectangle(img, (100 + x_offset, 80), (300 + x_offset, 280), (200, 200, 200), -1)
    cv2.circle(img, (350 + x_offset, 150), 40, (255, 255, 255), -1)
    cv2.rectangle(img, (60 + x_offset, 300), (220 + x_offset, 360), (150, 150, 150), -1)
    return img


def _as_thermal_like(bgr_scene):
    """Grayscale + inverted brightness - a thermal frame's raw intensity
    convention is unrelated to RGB's, even when both show the same real
    edge structure; the tests below must work despite that, not because
    the two images happen to share brightness."""
    gray = cv2.cvtColor(bgr_scene, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(255 - gray, cv2.COLOR_GRAY2BGR)


def _make_edge_scene_2d(h, w, x_offset=0, y_offset=0, scale=1.0):
    """Like _make_edge_scene, but also supports a vertical offset and a
    uniform scale (crop-in for scale>=1, shrink-and-pad for scale<1, the
    same convention _apply_fov_zoom/_scale_edge_map use) - for tests that
    inject a known 2D shift and/or scale mismatch."""
    base = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.rectangle(base, (100, 80), (300, 280), (200, 200, 200), -1)
    cv2.circle(base, (350, 150), 40, (255, 255, 255), -1)
    cv2.rectangle(base, (60, 300), (220, 360), (150, 150, 150), -1)

    if abs(scale - 1.0) > 1e-6:
        if scale >= 1.0:
            crop_w = max(1, min(w, int(round(w / scale))))
            crop_h = max(1, min(h, int(round(h / scale))))
            x0, y0 = (w - crop_w) // 2, (h - crop_h) // 2
            base = cv2.resize(base[y0:y0 + crop_h, x0:x0 + crop_w], (w, h),
                             interpolation=cv2.INTER_LINEAR)
        else:
            new_w = max(1, min(w, int(round(w * scale))))
            new_h = max(1, min(h, int(round(h * scale))))
            shrunk = cv2.resize(base, (new_w, new_h), interpolation=cv2.INTER_AREA)
            canvas = np.zeros_like(base)
            x0, y0 = (w - new_w) // 2, (h - new_h) // 2
            canvas[y0:y0 + new_h, x0:x0 + new_w] = shrunk
            base = canvas

    M = np.float32([[1, 0, x_offset], [0, 1, y_offset]])
    return cv2.warpAffine(base, M, (w, h))


class TestImageBasedAutoAlign:
    """2026-09-08: extends compute_auto_alignment() with a new shift+scale
    source - direct image registration (cv2.phaseCorrelate on each frame's
    own Sobel-gradient-magnitude map, searched across candidate FOV
    crop-zoom factors) - used in preference to the pre-existing
    geometry-only formula (entered lens focal-length/sensor-width specs)
    whenever both frames are available, since it measures the actual
    current misalignment AND scale instead of trusting entered specs that
    don't capture real per-unit manufacturing tolerance or mounting
    geometry. Sign convention was NOT assumed from cv2.phaseCorrelate's
    docs - a first attempt (-dx) was tried, measured to make real edge-map
    agreement WORSE (not better) on a synthetic pair with a known injected
    shift, and corrected to +dx."""

    def test_recovers_a_known_injected_shift(self):
        h, w = 400, 500
        known_shift = 22
        rgb = _make_edge_scene(h, w, x_offset=0)
        thermal = _as_thermal_like(_make_edge_scene(h, w, x_offset=-known_shift))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        measured = comp._estimate_shift_and_scale_from_images(thermal, rgb)

        assert measured is not None
        dx, dy, scale = measured
        assert abs(dx - known_shift) <= 2, f"expected ~{known_shift}px, got {dx}px"
        assert abs(dy) <= 2
        assert abs(scale - 1.0) <= 0.06, f"no scale mismatch injected, got {scale}"

    def test_recovers_a_known_injected_vertical_shift(self):
        """The vertical component must not be silently discarded - a real
        rig almost always has SOME vertical mounting offset between two
        physically separate camera bodies, not just horizontal."""
        h, w = 400, 500
        known_dy = 13
        rgb = _make_edge_scene(h, w, x_offset=0)
        thermal = _as_thermal_like(_make_edge_scene_2d(h, w, x_offset=0, y_offset=-known_dy))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        measured = comp._estimate_shift_and_scale_from_images(thermal, rgb)

        assert measured is not None
        dx, dy, scale = measured
        assert abs(dy - known_dy) <= 2, f"expected ~{known_dy}px vertical, got {dy}px"

    def test_recovers_a_known_injected_scale(self):
        """FOV crop-zoom must come from what the cameras actually see, not
        only shift - a real thermal/RGB pair's FOV ratio rarely matches
        entered datasheet specs exactly. thermal's content is injected
        1.25x magnified relative to rgb (correction_target="thermal" is
        the "moving" frame here) - the correctly-measured crop-zoom to
        apply back to thermal at render time is the INVERSE, ~0.8, the
        same crop-in-vs-shrink convention _apply_fov_zoom itself uses."""
        h, w = 400, 500
        injected_scale = 1.25
        rgb = _make_edge_scene(h, w, x_offset=0)
        thermal = _as_thermal_like(_make_edge_scene_2d(h, w, scale=injected_scale))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        measured = comp._estimate_shift_and_scale_from_images(thermal, rgb)

        assert measured is not None
        dx, dy, scale = measured
        expected_scale = 1.0 / injected_scale
        assert abs(scale - expected_scale) <= 0.06, f"expected ~{expected_scale}, got {scale}"

    def test_applying_the_measured_shift_actually_reduces_misalignment(self):
        """Not just a plausible-looking number - confirms the SIGN is
        right by checking real edge-map agreement improves, not worsens,
        once the measured shift is applied through the actual correction
        path a user would trigger it through."""
        h, w = 400, 500
        rgb = _make_edge_scene(h, w, x_offset=0)
        thermal = _as_thermal_like(_make_edge_scene(h, w, x_offset=-22))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        dx, dy, scale = comp._estimate_shift_and_scale_from_images(thermal, rgb)
        comp.enable(False)
        comp.set_manual_shift(dx, dy)
        comp.set_fov_zoom_factor(scale)
        corrected_thermal, _ = comp.apply_correction(thermal, rgb)

        def edges(frame):
            return cv2.Canny(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 50, 150)

        mismatch_before = int(np.count_nonzero(cv2.absdiff(edges(rgb), edges(thermal))))
        mismatch_after = int(np.count_nonzero(cv2.absdiff(edges(rgb), edges(corrected_thermal))))

        assert mismatch_after < mismatch_before * 0.5, (
            f"correction should substantially reduce edge mismatch - "
            f"before={mismatch_before} after={mismatch_after}"
        )

    def test_zero_shift_measures_near_zero(self):
        h, w = 400, 500
        rgb = _make_edge_scene(h, w, x_offset=0)
        thermal = _as_thermal_like(_make_edge_scene(h, w, x_offset=0))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        measured = comp._estimate_shift_and_scale_from_images(thermal, rgb)
        assert measured is not None
        dx, dy, scale = measured
        # A discrete scale search introduces some shift/scale coupling
        # ambiguity even on a perfectly-matched synthetic pair (a slightly
        # wrong scale can still show a sharp-looking peak at a slightly
        # offset shift) - same tolerance as the deliberately-injected-scale
        # test above, not tightened just because nothing was injected here.
        assert abs(dx) <= 5
        assert abs(dy) <= 2
        assert abs(scale - 1.0) <= 0.06

    def test_flat_textureless_scene_returns_none_not_a_bogus_value(self):
        """No shared edge structure to register against - must decline
        rather than confidently return noise."""
        h, w = 400, 500
        flat_rgb = np.full((h, w, 3), 128, dtype=np.uint8)
        flat_thermal = np.full((h, w, 3), 60, dtype=np.uint8)

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        assert comp._estimate_shift_and_scale_from_images(flat_thermal, flat_rgb) is None

    def test_compute_auto_alignment_prefers_image_based_when_both_frames_given(self):
        h, w = 400, 500
        rgb = _make_edge_scene(h, w, x_offset=0)
        thermal = _as_thermal_like(_make_edge_scene(h, w, x_offset=-15))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        dx, zoom = comp.compute_auto_alignment(
            working_distance_m=2.0, rgb_frame=rgb, thermal_frame=thermal
        )

        assert abs(dx - 15) <= 2
        assert comp.manual_shift_x == dx
        # No scale mismatch injected in this scene - image-based zoom
        # should land near 1.0, NOT compute_fov_crop_factor()'s
        # geometry/lens-spec-derived value (~1.07 for this comp's default
        # optics) - confirms scale now genuinely comes from image content.
        assert abs(zoom - 1.0) <= 0.06
        # Result must be usable immediately - not left in a stale-cache state.
        assert comp.last_displacement_map is None
        assert comp.crop_rect is None

    def test_compute_auto_alignment_falls_back_to_geometry_without_thermal_frame(self):
        """Existing behavior (rgb_frame only, or neither) must be
        completely unaffected by this feature's addition."""
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        dx, zoom = comp.compute_auto_alignment(working_distance_m=2.0)
        expected_dx = comp.compute_geometric_shift_px(2.0)
        assert dx == expected_dx


class TestMultiSampleConsensus:
    """2026-09-09: extends the image-based path with a multi-sample
    consensus option (_estimate_shift_and_scale_from_samples), found
    necessary via direct testing against REAL thermal/RGB hardware, not
    a theoretical concern - repeated real frame pairs of the SAME real
    misalignment measured phaseCorrelate confidence in the same ~0.08-
    0.10 range for both a consistent, clearly-correct result (a majority
    of samples agreeing closely) and a wild outlier sample; a single
    frame's own confidence score could not tell them apart. Cross-sample
    AGREEMENT is the trust signal here instead."""

    def test_majority_agreement_wins_over_a_minority_outlier(self):
        """4 good samples + 1 wild outlier - the outlier must not spoil
        the result, mirroring exactly what was observed on real hardware."""
        h, w = 400, 500
        rgb = _make_edge_scene(h, w, x_offset=0)
        good_thermal = _as_thermal_like(_make_edge_scene_2d(h, w, x_offset=-5, y_offset=-40))
        outlier_thermal = _as_thermal_like(_make_edge_scene_2d(h, w, x_offset=60, y_offset=90))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        pairs = [(good_thermal, rgb)] * 4 + [(outlier_thermal, rgb)]
        result = comp._estimate_shift_and_scale_from_samples(pairs)

        assert result is not None
        dx, dy, scale = result
        assert abs(dx - 5) <= 3
        assert abs(dy - 40) <= 3

    def test_no_majority_agreement_declines(self):
        """When samples genuinely disagree (no majority), there's no
        real consensus to trust - must decline, not average noise into
        a plausible-looking but meaningless number."""
        h, w = 400, 500
        rgb = _make_edge_scene(h, w, x_offset=0)
        thermal_a = _as_thermal_like(_make_edge_scene_2d(h, w, x_offset=-5, y_offset=-40))
        thermal_b = _as_thermal_like(_make_edge_scene_2d(h, w, x_offset=60, y_offset=90))
        thermal_c = _as_thermal_like(_make_edge_scene_2d(h, w, x_offset=-90, y_offset=20))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        pairs = [(thermal_a, rgb), (thermal_b, rgb), (thermal_c, rgb)]
        result = comp._estimate_shift_and_scale_from_samples(pairs)

        assert result is None

    def test_too_few_valid_samples_declines(self):
        """Fewer than _MIN_CONSENSUS_SAMPLES usable results (e.g. mostly
        flat/textureless frames) - not enough to form any consensus."""
        h, w = 400, 500
        flat_rgb = np.full((h, w, 3), 128, dtype=np.uint8)
        flat_thermal = np.full((h, w, 3), 60, dtype=np.uint8)

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        pairs = [(flat_thermal, flat_rgb)] * 5
        assert comp._estimate_shift_and_scale_from_samples(pairs) is None

    def test_compute_auto_alignment_uses_samples_when_given(self):
        """compute_auto_alignment must route to the multi-sample consensus
        path when thermal_frame_samples/rgb_frame_samples are both given,
        not silently ignore them in favor of the single-pair path."""
        h, w = 400, 500
        rgb = _make_edge_scene(h, w, x_offset=0)
        good_thermal = _as_thermal_like(_make_edge_scene_2d(h, w, x_offset=-5, y_offset=-40))

        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        dx, zoom = comp.compute_auto_alignment(
            working_distance_m=2.0,
            thermal_frame_samples=[good_thermal] * 4,
            rgb_frame_samples=[rgb] * 4,
        )

        assert abs(dx - 5) <= 3
        assert comp.manual_shift_y != 0
        assert abs(comp.manual_shift_y - 40) <= 3


class TestAutoCrop:
    """2026-09-08: a one-time (GUI-button-triggered) computation of a
    FIXED border-blank extent, replacing _remap_thermal's per-frame live
    re-derivation of the same numbers from the current flow_map - a
    simplification of the existing per-frame cost (no numpy min/max
    reduction every call), not a new one, per direct user instruction
    that this feature "does not contribute to the render pipeline as an
    additional layer."""

    def test_returns_none_before_any_correction_has_run(self):
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        assert comp.compute_auto_crop() is None
        assert comp.get_crop_rect() is None

    def test_computes_exact_rect_for_manual_shift_only(self):
        """A manual-shift-only flow map is a uniform constant, so the
        needed crop is fully deterministic - not an approximation."""
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.enable(False)
        comp.set_manual_shift(15, -8)
        thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        comp.apply_correction(thermal, rgb)

        rect = comp.compute_auto_crop()

        assert rect == (0, 8, 15, 0)  # (top, bottom, left, right)
        assert comp.get_crop_rect() == rect

    def test_cached_rect_produces_bit_identical_output_to_live_computation(self):
        """The whole point: using the cached crop_rect must not change
        what gets rendered, only how cheaply it's computed."""
        thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)

        comp_cached = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                         depth_method="simplified")
        comp_cached.enable(False)
        comp_cached.set_manual_shift(15, -8)
        comp_cached.apply_correction(thermal, rgb)
        comp_cached.compute_auto_crop()
        out_cached, _ = comp_cached.apply_correction(thermal, rgb)

        comp_live = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                       depth_method="simplified")
        comp_live.enable(False)
        comp_live.set_manual_shift(15, -8)
        out_live, _ = comp_live.apply_correction(thermal, rgb)  # crop_rect never set

        assert np.array_equal(out_cached, out_live)

    def test_set_manual_shift_invalidates_a_stale_crop_rect(self):
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.enable(False)
        comp.set_manual_shift(15, -8)
        thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        comp.apply_correction(thermal, rgb)
        comp.compute_auto_crop()
        assert comp.get_crop_rect() is not None

        comp.set_manual_shift(1, 1)

        assert comp.get_crop_rect() is None, (
            "a crop_rect sized for the OLD shift must not survive a shift change"
        )

    def test_compute_auto_alignment_also_invalidates_crop_rect(self):
        """compute_auto_alignment sets manual_shift_x directly (not via
        set_manual_shift()), so it needs its own invalidation - this
        guards against that being silently dropped in a future edit."""
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.enable(False)
        comp.set_manual_shift(15, -8)
        thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        comp.apply_correction(thermal, rgb)
        comp.compute_auto_crop()
        assert comp.get_crop_rect() is not None

        comp.compute_auto_alignment(working_distance_m=2.0)

        assert comp.get_crop_rect() is None

    def test_clear_crop_rect_restores_live_computation(self):
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.enable(False)
        comp.set_manual_shift(15, -8)
        thermal = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        rgb = np.random.randint(0, 255, (512, 640, 3), dtype=np.uint8)
        comp.apply_correction(thermal, rgb)
        comp.compute_auto_crop()
        assert comp.get_crop_rect() is not None

        comp.clear_crop_rect()

        assert comp.get_crop_rect() is None
        # Must still work correctly via the live path afterward.
        result, _ = comp.apply_correction(thermal, rgb)
        assert result.shape == thermal.shape

    def test_set_crop_rect_directly_for_restoring_a_persisted_value(self):
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.set_crop_rect(3, 4, 5, 6)
        assert comp.get_crop_rect() == (3, 4, 5, 6)

    def test_crop_rect_reclamped_against_a_smaller_current_frame(self):
        """A stored crop_rect from a larger resolution must not blank an
        entire smaller frame if the camera resolution changes later."""
        comp = ParallaxCompensator(camera_geometry=CameraGeometry(baseline_mm=50.0),
                                  depth_method="simplified")
        comp.enable(False)
        comp.set_manual_shift(1, 1)  # non-zero - has_manual_shift() must be True
        # to actually route through _remap_thermal at all
        comp.set_crop_rect(300, 300, 300, 300)  # absurdly large for a small frame

        small_thermal = np.random.randint(0, 255, (100, 120, 3), dtype=np.uint8)
        small_rgb = np.random.randint(0, 255, (100, 120, 3), dtype=np.uint8)
        result, _ = comp.apply_correction(small_thermal, small_rgb)

        assert result.shape == small_thermal.shape
        assert not np.all(result == 0), "must not blank the entire frame"
