"""
Tests for CameraMonitor's hot-plug scan gating.

A full detect_all_cameras() sweep costs ~10s because it renegotiates
resolutions and reads frames from every idle device. The monitor runs on a
loop, so it must skip that sweep while the OS device list is unchanged, and
must not discard the shared device scan that startup just built.
"""
import pytest

from thermal_inspection.cameras import camera_monitor as monitor_mod
from thermal_inspection.cameras.camera_monitor import CameraMonitor


@pytest.fixture
def harness(monkeypatch):
    """Replace hardware access with counters."""

    class Harness:
        def __init__(self):
            self.fingerprint = ["Cam A", "Cam B"]
            self.full_scans = 0
            self.invalidations = 0

    h = Harness()

    monkeypatch.setattr(
        CameraMonitor, "_device_fingerprint", staticmethod(lambda: h.fingerprint)
    )

    def fake_detect(skip_device_ids=None, register_cameras=True):
        h.full_scans += 1
        return []

    monkeypatch.setattr(
        monitor_mod.CameraDetector, "detect_all_cameras", staticmethod(fake_detect)
    )

    import thermal_inspection.cameras.device_scanner as scanner

    def fake_invalidate():
        h.invalidations += 1

    monkeypatch.setattr(scanner, "invalidate_cache", fake_invalidate)
    return h


def test_first_scan_runs_but_keeps_startup_cache(harness):
    mon = CameraMonitor()

    mon._perform_scan()

    assert harness.full_scans == 1
    # Startup discovery just populated the shared scan; dropping it here would
    # make every plugin re-probe for nothing.
    assert harness.invalidations == 0


def test_repeat_scans_skipped_while_device_list_unchanged(harness):
    mon = CameraMonitor()

    mon._perform_scan()
    mon._perform_scan()
    mon._perform_scan()

    assert harness.full_scans == 1
    assert harness.invalidations == 0


def test_device_added_triggers_full_scan_and_invalidation(harness):
    mon = CameraMonitor()
    mon._perform_scan()

    harness.fingerprint = ["Cam A", "Cam B", "New Thermal Cam"]
    mon._perform_scan()

    assert harness.full_scans == 2
    assert harness.invalidations == 1


def test_device_removed_triggers_full_scan(harness):
    mon = CameraMonitor()
    mon._perform_scan()

    harness.fingerprint = ["Cam A"]
    mon._perform_scan()

    assert harness.full_scans == 2
    assert harness.invalidations == 1


def test_settles_after_a_change(harness):
    mon = CameraMonitor()
    mon._perform_scan()

    harness.fingerprint = ["Cam A"]
    mon._perform_scan()
    mon._perform_scan()
    mon._perform_scan()

    # One scan for the change, then quiet again.
    assert harness.full_scans == 2


def test_force_always_scans_and_invalidates(harness):
    mon = CameraMonitor()
    mon._perform_scan()

    mon._perform_scan(force=True)

    assert harness.full_scans == 2
    assert harness.invalidations == 1


def test_unavailable_fingerprint_falls_back_to_scanning(harness, monkeypatch):
    # Without an OS device list we cannot detect changes cheaply, so the
    # monitor must not silently stop scanning.
    monkeypatch.setattr(
        CameraMonitor, "_device_fingerprint", staticmethod(lambda: None)
    )
    mon = CameraMonitor()

    mon._perform_scan()
    mon._perform_scan()

    assert harness.full_scans == 2
