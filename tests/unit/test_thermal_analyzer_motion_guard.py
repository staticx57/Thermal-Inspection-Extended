"""
Regression tests for the motion-guard saga in detect_anomalies()'s
statistical background model, resolved on 2026-09-04 by REMOVING the
guard rather than continuing to patch it.

History: a "Fix 4" motion guard (added 2026-08-31) skipped updating
the background model whenever a frame's global mean diff against it
exceeded a fixed threshold (15.0 raw units), intended to stop a real
camera pan from poisoning the model.

Two live bugs traced back to it:
1. "[Thermal] anomalies is still not working" / "stays empty
   indefinitely" - on a non-radiometric AGC camera, continuous
   auto-gain/contrast-stretching shifts a frame's global brightness by
   more than the threshold with NO actual motion at all (confirmed
   live: stuck at frame_count=686, global_diff~42-46 vs threshold=15.0,
   for minutes). background_model then froze on its old baseline
   forever - no anomaly was ever reported again.
2. A first fix attempt added a rebaseline-after-sustained-trip escape
   hatch, which then itself misfired on completely ordinary handheld
   motion ("if I move around in frame it will stop tracking and then
   spend a few seconds catching up... any motion will cause this wait
   period to repeat, previously this was never an issue").

git history showed the guard didn't exist before 2026-08-31:
accumulateWeighted ran unconditionally every frame, and a brief pan
only nudged the model by background_alpha's small learning rate (1%)
for the few frames it was actually moving - self-correcting smoothly
with nothing to ever get stuck on and nothing to "catch up" from.
That behavior is restored here exactly, rather than continuing to
tune a guard whose failure mode was worse than the problem it existed
to prevent.
"""
import numpy as np

from thermal_inspection.processing.thermal_analyzer import ThermalAnalyzer


def _make_analyzer():
    analyzer = ThermalAnalyzer()
    analyzer.is_radiometric = False
    return analyzer


class TestNoMotionGuardInterruption:
    def test_background_model_updates_every_frame_even_during_a_large_shift(self):
        """The old guard would have skipped this update entirely and
        returned early. It must now update unconditionally."""
        analyzer = _make_analyzer()
        shape = (64, 64)

        baseline = np.full(shape, 100, dtype=np.uint8)
        analyzer.detect_anomalies(baseline)
        model_before = analyzer.background_model.copy()

        # A large frame-to-frame shift (would have tripped the old
        # threshold=15.0 guard) - must still update the model.
        shifted = np.full(shape, 200, dtype=np.uint8)
        analyzer.detect_anomalies(shifted)

        assert not np.array_equal(analyzer.background_model, model_before), (
            "background_model must update every frame - no motion guard "
            "should ever skip this"
        )

    def test_frame_count_never_resets_or_pauses_across_sustained_motion(self):
        """The exact live complaint: any motion (even sustained, even
        far longer than the old escape hatch's window) must not pause
        frame_count or force a re-warm-up - it must keep climbing by
        exactly one per call, uninterrupted, matching pre-2026-08-31
        behavior."""
        analyzer = _make_analyzer()
        shape = (64, 64)

        baseline = np.full(shape, 100, dtype=np.uint8)
        for _ in range(analyzer.background_init_frames + 5):
            analyzer.detect_anomalies(baseline)
        frame_count_before = analyzer.frame_count

        # Sustained "motion" - a large, constant shift held for far
        # longer than the old escape hatch's window ever needed to be.
        shifted = np.full(shape, 200, dtype=np.uint8)
        for i in range(200):
            analyzer.detect_anomalies(shifted)
            assert analyzer.frame_count == frame_count_before + 1 + i, (
                "frame_count must climb by exactly one per call with no "
                "pause or reset, however long the shift is sustained"
            )

    def test_detection_resumes_instantly_with_no_catch_up_delay(self):
        """After any motion event, real or synthetic, the very next
        matching frame must be able to detect an anomaly immediately -
        no residual warm-up delay left over from the motion."""
        analyzer = _make_analyzer()
        shape = (64, 64)

        baseline = np.full(shape, 100, dtype=np.uint8)
        for _ in range(analyzer.background_init_frames + 5):
            analyzer.detect_anomalies(baseline)

        shifted = np.full(shape, 200, dtype=np.uint8)
        for _ in range(50):
            analyzer.detect_anomalies(shifted)

        # Back to the baseline scene, but with a real localized
        # anomaly - must be detected on this very first settled frame,
        # not several frames later.
        anomalous = baseline.copy()
        anomalous[10:30, 10:30] = 250
        anomalies = analyzer.detect_anomalies(anomalous)
        assert len(anomalies) > 0, (
            "detection must resume on the very next frame after motion "
            "settles, with no catch-up delay"
        )

    def test_no_motion_guard_attributes_remain(self):
        """The guard and its escape hatch were removed entirely, not
        just disabled - no dead state should linger on the instance."""
        analyzer = _make_analyzer()
        assert not hasattr(analyzer, "_motion_guard_threshold")
        assert not hasattr(analyzer, "_motion_guard_trip_start_time")
        assert not hasattr(analyzer, "_motion_guard_reset_after_seconds")
