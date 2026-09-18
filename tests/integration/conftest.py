"""
Shared fixtures for headless, hardware-free scenario tests that drive
the real ThermalInspectionApp frame-processing loop end to end - built
so the exact "relaunch, click through every view mode / parallax
setting / 3D mode, check the log for a crash" verification this session
did by hand repeatedly can run automatically instead (a pytest failure
here means what used to take a live relaunch + several minutes of
manual clicking to notice).
"""
import numpy as np
import pytest

from thermal_inspection.app import AppConfig, ThermalInspectionApp


class FakeThermalBackend:
    """Minimal stand-in for a real thermal camera backend's read() contract."""

    def __init__(self, width=640, height=512, seed=1):
        self._rng = np.random.default_rng(seed)
        self.width = width
        self.height = height

    def read(self):
        gray = (self._rng.normal(128, 20, size=(self.height, self.width))
                 .clip(0, 255).astype(np.uint8))
        return True, gray


class FakeRealSenseRgbBackend:
    """
    Stand-in for RGBCameraRealSense - read() for the plain RGB frame,
    plus get_point_cloud()/get_depth_frame() so app.py's THREE_D dispatch
    (which specifically probes hasattr(backend, 'get_point_cloud') to
    decide _rs_backend) takes the real 3D Fusion code path instead of
    silently falling back to "no depth hardware".
    """

    def __init__(self, width=1280, height=800, seed=2):
        self._rng = np.random.default_rng(seed)
        self.width = width
        self.height = height

    def read(self):
        frame = self._rng.integers(0, 255, size=(self.height, self.width, 3), dtype=np.uint8)
        return True, frame

    def get_point_cloud(self):
        n = 4000
        vertices = np.zeros((n, 3), dtype=np.float32)
        vertices[:, 2] = self._rng.uniform(0.3, 4.0, size=n).astype(np.float32)
        vertices[:, 0] = self._rng.uniform(-1, 1, size=n).astype(np.float32)
        vertices[:, 1] = self._rng.uniform(-1, 1, size=n).astype(np.float32)
        uv = self._rng.uniform(0, 1, size=(n, 2)).astype(np.float32)
        return vertices, uv

    def get_depth_frame(self, resize_to=None):
        """resize_to is (width, height), matching cv2.resize's convention
        and RGBCameraRealSense.get_depth_frame's real signature - app.py's
        3D display path relies on this parameter to avoid converting at
        full native resolution only to immediately downscale the result."""
        depth = self._rng.uniform(0.3, 4.0, size=(self.height, self.width)).astype(np.float32)
        if resize_to is not None and resize_to != (self.width, self.height):
            import cv2
            depth = cv2.resize(depth, resize_to, interpolation=cv2.INTER_NEAREST)
        return depth


class _FakePluginRef:
    def __init__(self, plugin_id):
        self.plugin_id = plugin_id


class _FakeActiveCamera:
    def __init__(self, backend, plugin_id):
        self.backend = backend
        self.plugin = _FakePluginRef(plugin_id)


@pytest.fixture
def headless_app_with_fake_cameras(qapp, monkeypatch, tmp_path):
    """
    A fully-initialized, headless ThermalInspectionApp (real
    FusionProcessor/ThermalAnalyzer/ParallaxCompensator/PaletteManager,
    no GUI window, no real hardware) wired to fake thermal + RealSense-
    like RGB backends via the synchronous (non-threaded-capture)
    frame-read path _process_frame_loop already falls back to when
    self.threaded_capture is unset.

    app.plugin_host is get_host() - a process-wide singleton, not a
    fresh instance per app - so its methods MUST be patched via
    monkeypatch (auto-reverted at teardown), never by plain attribute
    assignment: a raw `app.plugin_host.get_active_camera = ...` broke
    an unrelated, later-running unit test in the same pytest session by
    permanently replacing the singleton's method underneath it.

    get_config() is patched to a tmp_path-backed Config BEFORE
    ThermalInspectionApp is even constructed - app.initialize() calls
    _load_parallax_alignment_from_config() (and any test driving
    set_parallax_shift/zoom/baseline or the Auto-Align/Auto-Crop bus
    handlers writes back via _save_parallax_alignment_to_config()), and
    without this, EVERY such test call would read/write this project's
    real config.json on disk - confirmed live: an early version of the
    Auto-Crop smoke test below genuinely overwrote the real file's
    parallax_shift_x/fov_zoom_factor with test values before this fixture
    patch existed.
    """
    from thermal_inspection.utils.config import Config
    test_config = Config(config_file=str(tmp_path / "test_config.json"))
    monkeypatch.setattr("thermal_inspection.utils.config.get_config", lambda: test_config)

    app = ThermalInspectionApp(AppConfig(headless=True, enable_boson_sdk=False))
    assert app.initialize() is True
    # run() (never called here - it also starts the real QTimer/GUI event
    # loop, which a fast headless test doesn't want) is what normally
    # flips this - _process_frame_loop's very first line is `if not
    # self.running: return`.
    app.running = True

    thermal_backend = FakeThermalBackend()
    rgb_backend = FakeRealSenseRgbBackend()

    app.threaded_capture = None
    monkeypatch.setattr(app.plugin_host, "read_thermal", lambda: thermal_backend.read())

    _active = {
        "thermal": _FakeActiveCamera(thermal_backend, "flir_boson"),
        "rgb": _FakeActiveCamera(rgb_backend, "intel_realsense"),
    }
    monkeypatch.setattr(app.plugin_host, "get_active_camera", lambda role: _active.get(role))

    yield app

    app.cleanup()
