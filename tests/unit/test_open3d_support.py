"""Test the open3d_support module for lazy-import support."""


def test_open3d_support_flag_matches_real_import():
    from thermal_inspection.processing.open3d_support import OPEN3D_AVAILABLE
    try:
        import open3d  # noqa: F401
        really_available = True
    except ImportError:
        really_available = False
    assert OPEN3D_AVAILABLE == really_available


def test_get_open3d_raises_clear_error_when_unavailable(monkeypatch):
    import thermal_inspection.processing.open3d_support as mod
    monkeypatch.setattr(mod, "OPEN3D_AVAILABLE", False)
    import pytest
    with pytest.raises(ImportError, match="pip install open3d"):
        mod.get_open3d()
