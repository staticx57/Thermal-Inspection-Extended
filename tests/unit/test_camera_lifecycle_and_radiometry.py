"""
Camera acquire/lock/release and radiometric/non-radiometric pipeline fixes
(2026-09-23 review). Each test pins one concrete defect found in that review
- see the comment at each fix site for the full story.
"""
import threading
import time

import cv2
import numpy as np
import pytest

import thermal_inspection.cameras.device_scanner as device_scanner
from thermal_inspection.cameras.device_scanner import VideoDevice
from thermal_inspection.cameras.plugin.camera_plugin_host import _open_with_timeout
from thermal_inspection.cameras.threaded_camera_capture import (
    DualThreadedCameraCapture, ThreadedCameraCapture,
)
from thermal_inspection.processing.thermal_analyzer import ThermalAnalyzer
from thermal_inspection.utils.thermal_estimator import ThermalTemperatureEstimator


# ---------------------------------------------------------------- open/release

class _SlowBackend:
    def __init__(self, open_delay, open_result=True):
        self.open_delay = open_delay
        self.open_result = open_result
        self.released = threading.Event()
        self.release_during_open = False
        self._opening = False

    def open(self):
        self._opening = True
        time.sleep(self.open_delay)
        self._opening = False
        return self.open_result

    def release(self):
        if self._opening:
            self.release_during_open = True
        self.released.set()


@pytest.mark.unit
class TestOpenWithTimeout:

    def test_open_finishing_after_timeout_releases_its_handle(self):
        backend = _SlowBackend(open_delay=0.3)
        assert _open_with_timeout(backend, 0.05, "slow") is False
        assert not backend.released.is_set(), "must not release while open() is still running"
        assert backend.released.wait(2.0), "late-succeeding open must release its orphaned handle"
        assert not backend.release_during_open

    def test_fast_failed_open_is_released(self):
        backend = _SlowBackend(open_delay=0.0, open_result=False)
        assert _open_with_timeout(backend, 1.0, "fails") is False
        assert backend.released.is_set()

    def test_successful_open_is_not_released(self):
        backend = _SlowBackend(open_delay=0.0)
        assert _open_with_timeout(backend, 1.0, "ok") is True
        assert not backend.released.is_set()


# ---------------------------------------------------------------- capture

class _FrameSource:
    def __init__(self, frame):
        self.frame = frame
        self.block = threading.Event()

    def read(self):
        if self.block.is_set():
            time.sleep(0.5)
        time.sleep(0.005)
        return True, self.frame.copy()


def _wait_for(pred, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.005)
    return False


@pytest.mark.unit
class TestThreadedCapture:

    def test_16bit_display_is_built_on_demand_and_matches_old_conversion(self):
        raw = (np.arange(64 * 80, dtype=np.uint32).reshape(64, 80) * 7 % 65535).astype(np.uint16)
        cap = ThreadedCameraCapture(_FrameSource(raw), "T")
        cap.start()
        try:
            assert _wait_for(lambda: cap.latest_raw_frame is not None)
            with cap.frame_lock:
                assert cap.latest_frame is None, "capture thread must not pre-build the unused display frame"
            ok, display, _ = cap.get_frame()
            expected = cv2.cvtColor(cv2.normalize(raw, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U),
                                    cv2.COLOR_GRAY2BGR)
            assert ok and np.array_equal(display, expected)
        finally:
            cap.stop()

    def test_raw_frames_counter_advances_only_on_new_frames(self):
        dual = DualThreadedCameraCapture(_FrameSource(np.zeros((8, 8), np.uint16)),
                                         _FrameSource(np.zeros((8, 8, 3), np.uint8)))
        dual.start()
        try:
            assert _wait_for(lambda: dual.get_raw_frames()[2][0] > 0 and dual.get_raw_frames()[2][1] > 0)
            _, _, counts_a = dual.get_raw_frames()
            assert _wait_for(lambda: dual.get_raw_frames()[2] != counts_a)
        finally:
            dual.stop()
        _, _, frozen = dual.get_raw_frames()
        assert dual.get_raw_frames()[2] == frozen

    def test_stop_reports_a_thread_stuck_in_read(self):
        source = _FrameSource(np.zeros((8, 8, 3), np.uint8))
        cap = ThreadedCameraCapture(source, "Stuck")
        cap.start()
        assert _wait_for(lambda: cap.frame_count > 0)
        source.block.set()
        time.sleep(0.05)
        assert cap.stop(timeout=0.01) is False
        assert cap.stop(timeout=2.0) is True, "a second stop() must keep waiting, not report success blindly"


# ---------------------------------------------------------------- scanner

@pytest.mark.unit
class TestScannerSkipsInUseDevices:

    @pytest.fixture(autouse=True)
    def _isolate(self, monkeypatch):
        monkeypatch.setattr(device_scanner, "_cached_devices", None)
        monkeypatch.setattr(device_scanner, "_last_known", {})
        monkeypatch.setattr(device_scanner, "_active_indices", frozenset())
        saved = []
        monkeypatch.setattr(device_scanner, "_save_fast_path", lambda names, devs: saved.append(list(devs)))
        monkeypatch.setattr(device_scanner, "_load_fast_path", lambda names: None)
        self.saved = saved
        self.probed = []

        def fake_probe(index, names):
            self.probed.append(index)
            return VideoDevice(index=index, name=names[index], width=640, height=512)
        monkeypatch.setattr(device_scanner, "_probe_device", fake_probe)

    def test_in_use_device_is_carried_forward_not_reopened(self, monkeypatch):
        monkeypatch.setattr(device_scanner, "_list_device_names", lambda: ["Boson", "Webcam"])
        device_scanner.scan_video_devices(force=True)
        self.probed.clear()

        device_scanner.set_active_indices([0, -1, None])
        devices = device_scanner.scan_video_devices(force=True)

        assert self.probed == [1], "the in-use device 0 must not be opened"
        assert [d.index for d in devices] == [0, 1]
        assert self.saved[-1] == devices

    def test_unknown_in_use_device_is_skipped_and_scan_not_persisted(self, monkeypatch):
        monkeypatch.setattr(device_scanner, "_list_device_names", lambda: ["Boson", "Webcam"])
        device_scanner.set_active_indices([0])
        devices = device_scanner.scan_video_devices(force=True)

        assert self.probed == [1]
        assert [d.index for d in devices] == [1]
        assert self.saved == [], "an incomplete scan must not become the next launch's fast path"

    def test_renumbered_index_is_not_described_by_the_old_entry(self, monkeypatch):
        names = ["Boson", "Webcam"]
        monkeypatch.setattr(device_scanner, "_list_device_names", lambda: names)
        device_scanner.scan_video_devices(force=True)
        names[:] = ["Webcam"]  # device 0 unplugged, webcam renumbered to 0
        device_scanner.set_active_indices([0])
        self.probed.clear()
        devices = device_scanner.scan_video_devices(force=True)
        assert devices == [] and self.probed == []


# ---------------------------------------------------------------- radiometry

@pytest.mark.unit
class TestRawStatsHaveNoTemperatureUnit:

    def test_raw_agc_stats_are_not_unit_converted(self):
        analyzer = ThermalAnalyzer()
        analyzer.set_radiometric_mode(False)
        analyzer.set_temperature_unit('F')
        frame = np.full((32, 32), 128, np.uint8)
        frame[0, 0] = 10
        stats = analyzer.compute_statistics(frame)
        assert stats.max_temp == 128.0 and stats.min_temp == 10.0
        assert stats.temp_range == 118.0
        assert stats.unit == " (raw)"

    def test_radiometric_stats_still_convert(self):
        analyzer = ThermalAnalyzer()
        analyzer.set_radiometric_mode(True)
        analyzer.set_temperature_unit('F')
        frame = np.full((8, 8), 29815, np.uint16)  # 25.0 C
        assert analyzer.compute_statistics(frame).max_temp == pytest.approx(77.0)


def _narrow_scene():
    rng = np.random.default_rng(0)
    gray = np.clip(rng.normal(120, 15, (64, 80)), 0, 255).astype(np.uint8)
    gray[10, 20] = 200
    return gray


@pytest.mark.unit
class TestEstimatorConsistency:

    def test_spot_reading_matches_the_map_stats_use(self):
        est = ThermalTemperatureEstimator()
        gray = _narrow_scene()
        assert est.get_pixel_temperature(gray, 20, 10, 25.0) == pytest.approx(
            float(est.estimate_temperature_map(gray, 25.0)[10, 20]))

    def test_three_channel_frame_gives_a_number(self):
        est = ThermalTemperatureEstimator()
        gray = _narrow_scene()
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        value = est.get_pixel_temperature(bgr, 20, 10, 25.0)
        assert isinstance(value, float)
        assert value == pytest.approx(est.get_pixel_temperature(gray, 20, 10, 25.0))

    def test_two_point_calibration_hits_both_references(self):
        est = ThermalTemperatureEstimator()
        est.calibrate_two_point(agc_low=40, temp_low_c=0.0, agc_high=200, temp_high_c=100.0, fpa_temp_c=25.0)
        frame = np.array([[40, 200]], dtype=np.uint8)
        temps = est.estimate_temperature_map(frame, 25.0)
        assert temps[0, 0] == pytest.approx(0.0, abs=1e-4)
        assert temps[0, 1] == pytest.approx(100.0, abs=1e-4)

    def test_single_point_calibration_applies_to_the_map(self):
        est = ThermalTemperatureEstimator()
        gray = _narrow_scene()
        est.calibrate_single_point(int(gray[10, 20]), 37.0, 25.0)
        assert float(est.estimate_temperature_map(gray, 25.0)[10, 20]) == pytest.approx(37.0, abs=1e-4)
