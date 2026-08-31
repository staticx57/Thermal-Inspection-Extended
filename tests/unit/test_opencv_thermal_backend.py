"""
Unit tests for OpenCVThermalBackend.

Regression coverage for a real bug found while debugging a physically
connected Boson camera: open() referenced self.camera.width/.height/.fps and
get_info()/get_resolution() referenced self.camera.width/.height/.is_radiometric
— none of which exist on FLIRBosonCamera (it exposes `resolution` as a tuple,
no `fps` attribute at all, and `is_radiometric_enabled()` as a method, not an
`is_radiometric` attribute). The underlying camera opened successfully every
time; the AttributeError in the success-path logging was caught by the
surrounding try/except and reported as a failed camera open, so the app
appeared to not start the camera at all.

No existing test touched this file, which is exactly how the bug went
uncaught: the backend's contract with FLIRBosonCamera was never exercised
without real hardware.
"""
from unittest.mock import MagicMock

from thermal_inspection.cameras.opencv_thermal_backend import OpenCVThermalBackend


def _fake_flir_camera(resolution=(640, 512)):
    """
    A stand-in matching FLIRBosonCamera's real attribute surface — no
    width/height/fps attributes, resolution as a tuple, is_radiometric_enabled
    as a method. Mirrors thermal_inspection/cameras/flir_camera.py exactly so
    a future rename on either side gets caught here instead of only on real
    hardware.
    """
    camera = MagicMock()
    camera.open.return_value = True
    camera.resolution = resolution
    camera.is_radiometric_enabled.return_value = False
    camera.cap = MagicMock()
    camera.cap.get.return_value = 30.0
    # Explicitly assert the attributes this backend used to reference don't
    # exist, so the mock can't accidentally paper over the bug by auto-
    # creating them (a plain MagicMock would happily return another
    # MagicMock for camera.width with no error).
    del camera.width
    del camera.height
    del camera.fps
    del camera.is_radiometric
    return camera


class TestOpenCVThermalBackendOpen:

    def test_open_succeeds_and_does_not_raise(self, monkeypatch):
        backend = OpenCVThermalBackend(device_id=2, com_port="COM6", enable_sdk=True)
        fake_camera = _fake_flir_camera()
        monkeypatch.setattr(
            "thermal_inspection.cameras.opencv_thermal_backend.FLIRBosonCamera",
            lambda **kwargs: fake_camera,
        )

        ok = backend.open()

        assert ok is True
        assert backend._is_opened is True

    def test_open_does_not_reference_nonexistent_camera_attributes(self, monkeypatch):
        # Regression guard: if open() is ever changed to read an attribute
        # FLIRBosonCamera doesn't have, this raises AttributeError from the
        # mock (which has no unexpected attributes, unlike a bare MagicMock)
        # instead of silently succeeding.
        backend = OpenCVThermalBackend(device_id=2, com_port="COM6", enable_sdk=True)
        fake_camera = _fake_flir_camera()
        monkeypatch.setattr(
            "thermal_inspection.cameras.opencv_thermal_backend.FLIRBosonCamera",
            lambda **kwargs: fake_camera,
        )

        backend.open()  # must not raise


class TestOpenCVThermalBackendIntrospection:

    def _opened_backend(self, monkeypatch, resolution=(640, 512)):
        backend = OpenCVThermalBackend(device_id=2, com_port="COM6", enable_sdk=True)
        fake_camera = _fake_flir_camera(resolution=resolution)
        monkeypatch.setattr(
            "thermal_inspection.cameras.opencv_thermal_backend.FLIRBosonCamera",
            lambda **kwargs: fake_camera,
        )
        backend.open()
        return backend, fake_camera

    def test_get_resolution_returns_camera_resolution_tuple(self, monkeypatch):
        backend, _ = self._opened_backend(monkeypatch, resolution=(336, 256))
        assert backend.get_resolution() == (336, 256)

    def test_get_resolution_returns_none_when_not_opened(self):
        backend = OpenCVThermalBackend(device_id=2, com_port="COM6")
        assert backend.get_resolution() is None

    def test_get_info_does_not_raise_and_reports_mode(self, monkeypatch):
        backend, fake_camera = self._opened_backend(monkeypatch)

        info = backend.get_info()

        assert info['resolution'] == (640, 512)
        assert info['mode'] == 'non-radiometric'
        fake_camera.is_radiometric_enabled.assert_called()

    def test_get_info_reports_radiometric_mode_when_enabled(self, monkeypatch):
        backend, fake_camera = self._opened_backend(monkeypatch)
        fake_camera.is_radiometric_enabled.return_value = True

        info = backend.get_info()

        assert info['mode'] == 'radiometric'
