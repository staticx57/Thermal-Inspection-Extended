"""
Regression test for a live-reported correctness bug (2026-09-04): "the
application is no longer finding anomalies when previously it did
under the same visual conditions."

Root cause: ThermalAnalyzer._estimated_map() (the 8-bit estimation
path used by non-radiometric cameras) cached its result keyed by
id(thermal_frame). That id is only guaranteed unique among
simultaneously-alive objects - the grayscale array analyze() converts
each frame goes out of scope the instant analyze() returns (nothing
else holds a reference once ThreadedAnalyzer's run loop moves on to
the next frame), and CPython/numpy very reliably hand the very next
same-size allocation that exact just-freed address straight back. So
the id()-based cache didn't just risk a rare collision - it reliably
matched on every subsequent call, permanently freezing the estimated
temperature map (and therefore hot/cold-spot and anomaly detection,
which threshold against it) on whichever frame happened to populate
the cache first.

Fixed by keying the cache on a monotonic counter bumped once per
analyze() call instead of object identity - see
ThermalAnalyzer._analyze_generation.
"""
import numpy as np

from thermal_inspection.processing.thermal_analyzer import ThermalAnalyzer


class _FakeEstimator:
    """Returns a map whose fill value changes every call, so a stale
    cache hit is trivially distinguishable from a fresh computation."""

    def __init__(self):
        self.call_count = 0

    def estimate_temperature_map(self, frame, fpa):
        self.call_count += 1
        return np.full(frame.shape, float(self.call_count) * 10.0, dtype=np.float32)


def _make_estimation_mode_analyzer():
    analyzer = ThermalAnalyzer()
    analyzer.is_radiometric = False
    analyzer.estimation_enabled = True
    analyzer.thermal_estimator = _FakeEstimator()
    return analyzer


class TestEstimatedMapCacheSurvivesIdReuse:
    def test_second_analyze_call_recomputes_even_with_a_poisoned_id_collision(self):
        """Deterministic reproduction of the real-world hazard - rather
        than hoping CPython's allocator happens to reuse an address
        during the test, directly poison the cache with the new
        frame's id() (exactly what a recycled memory address would
        produce) and confirm analyze() still recomputes."""
        analyzer = _make_estimation_mode_analyzer()

        frame1 = np.full((64, 64), 100, dtype=np.uint8)
        analyzer.analyze(frame1)
        assert analyzer.thermal_estimator.call_count == 1

        frame2 = np.full((64, 64), 200, dtype=np.uint8)
        # Simulate the exact collision the old id()-based cache was
        # vulnerable to: frame2 "happens" to occupy an address a stale
        # cache entry already matches.
        analyzer._est_map_cache_key = id(frame2)

        analyzer.analyze(frame2)
        assert analyzer.thermal_estimator.call_count == 2, (
            "analyze() must recompute the estimated map for a new "
            "frame even when that frame's id() collides with a stale "
            "cache entry from a previous call - a cache stuck at "
            "call_count==1 here reproduces 'no longer finding "
            "anomalies under the same visual conditions'"
        )

    def test_repeated_calls_on_genuinely_new_frames_keep_recomputing(self):
        """Straightforward sequential-call version of the same
        guarantee, no manual poisoning - 10 distinct frames must
        produce 10 distinct estimator calls, not a frozen count."""
        analyzer = _make_estimation_mode_analyzer()

        for i in range(10):
            frame = np.full((32, 32), i, dtype=np.uint8)
            analyzer.analyze(frame)

        assert analyzer.thermal_estimator.call_count == 10

    def test_calls_within_one_analyze_invocation_still_share_the_cache(self):
        """The cache's actual intended purpose must still work:
        compute_statistics/detect_hot_spots/detect_cold_spots/
        detect_anomalies all call _estimated_map() during a single
        analyze() pass and must hit the same cached result, not
        recompute 4-5x per frame."""
        analyzer = _make_estimation_mode_analyzer()
        frame = np.full((64, 64), 128, dtype=np.uint8)

        analyzer.analyze(frame)

        # detect_hot_spots + detect_cold_spots + compute_statistics
        # (called directly, plus once more internally by
        # detect_anomalies) all ran during that one analyze() call -
        # every one of them must have shared the single cached map.
        assert analyzer.thermal_estimator.call_count == 1
