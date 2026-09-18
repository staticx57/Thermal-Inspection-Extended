"""
Unit tests for utils/gpu_device.py's shared torch GPU-device resolver
(2026-09-09) - added when wiring a "directml" device option (Intel/AMD,
via the torch-directml package) alongside the existing CUDA path across
all four GPU resolvers (fusion_processor.py's feature_weighted/
laplacian_pyramid, fusion_3d_panel.py's relief/normals,
parallax_compensator.py's remap).

torch-directml is not installed in this project's dev/test environment
(a real version-pin conflict with this project's torch build - see
requirements.txt), so these tests exercise the DirectML branch by
inserting a fake `torch_directml` module into sys.modules rather than
requiring the real package - the resolver only ever calls
`torch_directml.is_available()`/`.device()`/`.device_name()`/
`.default_device()`, so a minimal fake covering those four names is a
faithful stand-in for "torch-directml is installed and a DirectML
device is present", without needing real Intel/AMD hardware.
"""
import sys
import types

import pytest

torch = pytest.importorskip("torch")

from thermal_inspection.utils.gpu_device import resolve_torch_gpu_device


@pytest.fixture
def fake_torch_directml(monkeypatch):
    """Installs a fake torch_directml module reporting one available device."""
    fake = types.ModuleType("torch_directml")
    fake.is_available = lambda: True
    fake.device = lambda: "directml_fake_device"
    fake.default_device = lambda: 0
    fake.device_name = lambda idx: "Fake Intel Iris Xe"
    monkeypatch.setitem(sys.modules, "torch_directml", fake)
    return fake


@pytest.fixture
def no_torch_directml(monkeypatch):
    """Ensures torch_directml raises ImportError (simulates not installed)."""
    monkeypatch.setitem(sys.modules, "torch_directml", None)


class TestCpuRequested:
    def test_cpu_returns_none_without_touching_torch(self):
        device, name = resolve_torch_gpu_device("cpu", "test")
        assert device is None
        assert name is None


class TestCudaRequested:
    def test_cuda_available_returns_cuda_device(self, monkeypatch):
        monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
        monkeypatch.setattr(torch.cuda, "get_device_name", lambda i=0: "Fake RTX")
        device, name = resolve_torch_gpu_device("cuda", "test")
        assert device == "cuda"
        assert name == "Fake RTX"

    def test_cuda_unavailable_and_not_requested_falls_through_to_directml(
        self, monkeypatch, fake_torch_directml
    ):
        """'auto' with no CUDA must still try DirectML, not just give up."""
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        device, name = resolve_torch_gpu_device("auto", "test")
        assert device == "directml_fake_device"
        assert "Fake Intel Iris Xe" in name

    def test_cuda_explicitly_requested_but_unavailable_declines(
        self, monkeypatch, no_torch_directml
    ):
        """An explicit 'cuda' request must not silently fall back to a
        different accelerator - only 'auto' tries alternatives."""
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        device, name = resolve_torch_gpu_device("cuda", "test")
        assert device is None
        assert name is None


class TestDirectmlRequested:
    def test_directml_available_returns_directml_device(self, fake_torch_directml, monkeypatch):
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        device, name = resolve_torch_gpu_device("directml", "test")
        assert device == "directml_fake_device"
        assert "DirectML" in name
        assert "Fake Intel Iris Xe" in name

    def test_directml_requested_but_not_installed_declines_not_raises(self, no_torch_directml):
        """The real, current state of this project's own dev environment -
        must decline cleanly (ImportError caught), never raise."""
        device, name = resolve_torch_gpu_device("directml", "test")
        assert device is None
        assert name is None

    def test_directml_requested_but_no_device_present_declines(self, monkeypatch):
        fake = types.ModuleType("torch_directml")
        fake.is_available = lambda: False
        monkeypatch.setitem(sys.modules, "torch_directml", fake)
        device, name = resolve_torch_gpu_device("directml", "test")
        assert device is None
        assert name is None


class TestAutoPrefersCudaOverDirectml:
    def test_auto_prefers_cuda_when_both_available(self, monkeypatch, fake_torch_directml):
        """CUDA is the mature, verified path - 'auto' must prefer it over
        DirectML when both are present, not pick arbitrarily."""
        monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
        monkeypatch.setattr(torch.cuda, "get_device_name", lambda i=0: "Fake RTX")
        device, name = resolve_torch_gpu_device("auto", "test")
        assert device == "cuda"
        assert name == "Fake RTX"


class TestNoAcceleratorAvailable:
    def test_auto_with_nothing_available_declines(self, monkeypatch, no_torch_directml):
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        device, name = resolve_torch_gpu_device("auto", "test")
        assert device is None
        assert name is None
