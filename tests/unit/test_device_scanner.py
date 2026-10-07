"""
Unit tests for the shared video device scanner.

The scanner is what keeps camera autodiscovery from re-probing the same USB
devices once per plugin, so its caching and filtering behaviour is
performance-critical as well as correctness-critical. Every test here stubs out
hardware access — nothing opens a real capture device.
"""
from dataclasses import FrozenInstanceError

import pytest

from thermal_inspection.cameras import device_scanner
from thermal_inspection.cameras.device_scanner import (
    VideoDevice,
    find_devices_by_resolution,
    get_device_map,
    invalidate_cache,
    scan_video_devices,
)


@pytest.fixture(autouse=True)
def clean_scanner_state(monkeypatch):
    """Isolate each test from the module cache and from persisted config."""
    invalidate_cache()
    # Never read or write the real config.json during tests.
    monkeypatch.setattr(device_scanner, "_load_fast_path", lambda names: None)
    monkeypatch.setattr(device_scanner, "_save_fast_path", lambda names, devices: None)
    yield
    invalidate_cache()


def _fake_hardware(monkeypatch, devices):
    """
    Install a fake device layer.

    Args:
        devices: mapping of index -> (name, width, height), or None to mean
            "index exists but delivers no frame" (a phantom filter).

    Returns:
        A list that records every index actually probed.
    """
    probed = []
    names = [spec[0] if spec else f"Phantom {i}" for i, spec in enumerate(devices)]

    def fake_list_names():
        return names

    def fake_probe(index, name_list):
        probed.append(index)
        # With no OS device list the scanner sweeps a fixed default range, so
        # it may probe past the end of our fake hardware.
        if index >= len(devices):
            return None
        spec = devices[index]
        if spec is None:
            return None
        name, width, height = spec
        return VideoDevice(index=index, name=name, width=width, height=height)

    monkeypatch.setattr(device_scanner, "_list_device_names", fake_list_names)
    monkeypatch.setattr(device_scanner, "_probe_device", fake_probe)
    return probed


class TestVendorVirtualSources:

    def test_basler_and_ebus_virtual_filters_are_never_opened(self, monkeypatch):
        probed = _fake_hardware(monkeypatch, [
            ("Logitech BRIO", 640, 480),
            ("THERMAL VISION CAMERA TAU-2", 640, 512),
            ("Basler GenICam Source", 640, 480),
            ("eBUS DirectShow Source", 640, 480),
            ("OBS Virtual Camera", 1920, 1080),
        ])

        devices = scan_video_devices()

        assert probed == [0, 1, 4]                      # opening a vendor filter can crash the process natively
        assert [d.index for d in devices] == [0, 1, 4]


class TestScanCaching:

    def test_probes_each_index_once(self, monkeypatch):
        probed = _fake_hardware(monkeypatch, [
            ("Logitech BRIO", 640, 480),
            ("FLIR Boson", 640, 512),
        ])

        devices = scan_video_devices()

        assert probed == [0, 1]
        assert len(devices) == 2

    def test_repeated_scans_do_not_reprobe(self, monkeypatch):
        probed = _fake_hardware(monkeypatch, [("Cam", 640, 480)])

        scan_video_devices()
        scan_video_devices()
        scan_video_devices()

        # This is the whole point of the module: six plugins calling detect()
        # must cost one hardware sweep, not six.
        assert probed == [0]

    def test_force_reprobes(self, monkeypatch):
        probed = _fake_hardware(monkeypatch, [("Cam", 640, 480)])

        scan_video_devices()
        scan_video_devices(force=True)

        assert probed == [0, 0]

    def test_invalidate_cache_forces_next_scan(self, monkeypatch):
        probed = _fake_hardware(monkeypatch, [("Cam", 640, 480)])

        scan_video_devices()
        invalidate_cache()
        scan_video_devices()

        assert probed == [0, 0]

    def test_callers_cannot_mutate_the_cache(self, monkeypatch):
        _fake_hardware(monkeypatch, [("Cam", 640, 480)])

        first = scan_video_devices()
        first.clear()

        assert len(scan_video_devices()) == 1


class TestPhantomFiltering:

    def test_devices_without_frames_are_excluded(self, monkeypatch):
        # Vendor SDKs register DirectShow filters that open but never deliver
        # frames; they must not be reported as cameras.
        _fake_hardware(monkeypatch, [
            ("Real Camera", 640, 480),
            None,   # Basler GenICam Source - registered, no hardware
            None,   # eBUS DirectShow Source - registered, no hardware
        ])

        devices = scan_video_devices()

        assert [d.name for d in devices] == ["Real Camera"]

    def test_indices_are_preserved_across_gaps(self, monkeypatch):
        _fake_hardware(monkeypatch, [
            None,
            ("Second Slot Camera", 640, 480),
        ])

        devices = scan_video_devices()

        # The surviving device must keep its true OS index, or plugins will
        # open the wrong device later.
        assert len(devices) == 1
        assert devices[0].index == 1


class TestResolutionFiltering:

    def test_exact_resolution_match(self, monkeypatch):
        _fake_hardware(monkeypatch, [
            ("Webcam", 640, 480),
            ("Boson", 640, 512),
            ("Lepton", 160, 120),
        ])

        matches = find_devices_by_resolution([(640, 512)])

        assert [d.name for d in matches] == ["Boson"]

    def test_tolerance_widens_the_match(self, monkeypatch):
        _fake_hardware(monkeypatch, [("Almost Boson", 636, 508)])

        assert find_devices_by_resolution([(640, 512)]) == []
        assert len(find_devices_by_resolution([(640, 512)], tolerance=10)) == 1

    def test_multiple_accepted_resolutions(self, monkeypatch):
        _fake_hardware(monkeypatch, [
            ("Lepton 3", 160, 120),
            ("Lepton 2", 80, 60),
            ("Webcam", 640, 480),
        ])

        matches = find_devices_by_resolution([(160, 120), (80, 60)])

        assert {d.name for d in matches} == {"Lepton 3", "Lepton 2"}

    def test_device_matching_two_entries_is_not_duplicated(self, monkeypatch):
        _fake_hardware(monkeypatch, [("Boson", 640, 512)])

        # Overlapping tolerance windows must still yield one result.
        matches = find_devices_by_resolution([(640, 512), (641, 513)], tolerance=5)

        assert len(matches) == 1

    def test_no_devices_yields_empty_list(self, monkeypatch):
        _fake_hardware(monkeypatch, [])

        assert find_devices_by_resolution([(640, 512)]) == []


class TestVideoDevice:

    def test_resolution_property(self):
        device = VideoDevice(index=0, name="Cam", width=640, height=512)
        assert device.resolution == (640, 512)

    def test_is_hashable_and_immutable(self):
        device = VideoDevice(index=0, name="Cam", width=640, height=512)
        assert {device}  # frozen dataclass must be hashable
        with pytest.raises(FrozenInstanceError):
            device.width = 1

    def test_device_map_is_keyed_by_index(self, monkeypatch):
        _fake_hardware(monkeypatch, [
            None,
            ("Cam A", 640, 480),
            ("Cam B", 1920, 1080),
        ])

        mapping = get_device_map()

        assert set(mapping) == {1, 2}
        assert mapping[2].name == "Cam B"


def test_camera_detector_also_skips_vendor_virtual_sources(monkeypatch):
    """The background monitor has its own probe loop; it must not open Basler/eBUS filters either."""
    from thermal_inspection.cameras.camera_detector import CameraDetector
    probed = []
    monkeypatch.setattr(CameraDetector, "_probe_single_windows_camera_safe",
                        staticmethod(lambda dev_id, name: probed.append(dev_id)))
    monkeypatch.setattr(device_scanner, "_list_device_names",
                        lambda: ["Logitech BRIO", "Basler GenICam Source", "eBUS DirectShow Source"])
    CameraDetector._probe_windows_cameras(skip_device_ids=[])
    assert probed == [0]                               # never the Basler (1) or eBUS (2) filters
