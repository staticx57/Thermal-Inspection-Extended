"""Tau 2 video-only board: the UVC-level video mode works without a control line; CCI-only controls say they cannot."""
import numpy as np
import pytest

from thermal_inspection.utils import config as config_module
from thermal_inspection.cameras.plugins.tau2.plugin import (
    Tau2CameraSDK, Tau2Plugin, get_video_mode, set_video_mode)
from thermal_inspection.cameras.plugin.camera_plugin import CameraPluginMatch


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """A throwaway Config so tests never write the real config.json."""
    instance = config_module.Config(str(tmp_path / "config.json"))
    monkeypatch.setattr(config_module, "_config_instance", instance)
    return instance


def test_default_is_the_onboard_colour_picture(cfg):
    assert get_video_mode() == "color"


def test_set_video_mode_reports_whether_it_changed_and_persists(cfg, tmp_path):
    assert set_video_mode("raw") is True
    assert get_video_mode() == "raw"
    assert set_video_mode("raw") is False                       # no change, no reopen needed
    assert config_module.Config(str(tmp_path / "config.json")).get("tau2")["raw_mode"] is True


def test_set_video_mode_keeps_other_tau2_settings(cfg):
    cfg.set("tau2", {"byte_order": "native"})
    set_video_mode("raw")
    assert cfg.get("tau2") == {"byte_order": "native", "raw_mode": True}


def test_sdk_switches_video_mode_without_a_serial_connection(cfg):
    sdk = Tau2CameraSDK(com_port=None)
    assert not sdk.is_connected()
    result = sdk.execute("set_video_mode", {"mode": "raw"})
    assert result == {"success": True, "mode": "raw", "reopen_required": True}
    assert sdk.execute("get_video_mode") == {"success": True, "mode": "raw"}
    assert sdk.execute("set_video_mode", {"mode": "raw"})["reopen_required"] is False


def test_sdk_rejects_an_unknown_mode_and_still_refuses_cci_commands(cfg):
    sdk = Tau2CameraSDK(com_port=None)
    assert sdk.execute("set_video_mode", {"mode": "y8"})["success"] is False
    assert get_video_mode() == "color"
    assert sdk.execute("set_palette", {"palette": "ironbow"}) == {
        "success": False, "error": "Tau 2 serial port is not connected"}


def test_backend_opens_in_the_saved_mode_and_is_not_radiometric_without_cci(cfg):
    set_video_mode("raw")
    match = CameraPluginMatch(plugin_id="flir_tau2", device_index=0, com_port=None, resolution=(640, 512))
    backend = Tau2Plugin().create_backend(match)
    assert backend.raw_mode is True
    assert backend.is_radiometric() is False                    # raw counts are not temperature


def test_panel_greys_out_cci_controls_but_not_video_mode_and_emits_the_command(qapp, cfg):
    from thermal_inspection.gui.camera_control.tau2_control_panel import Tau2ControlPanel
    panel = Tau2ControlPanel()
    for grp in (panel.ffc_grp, panel.shutter_grp, panel.gain_grp, panel.lut_grp, panel.agc_grp, panel.rad_grp):
        assert not grp.isEnabled() and grp.toolTip()
    assert panel.mode_color_radio.isEnabled() and panel.mode_raw_radio.isEnabled()
    assert panel.mode_color_radio.isChecked()

    sent = []
    panel.command_requested.connect(lambda cmd, params: sent.append((cmd, params)))
    panel.mode_raw_radio.setChecked(True)
    assert sent == [("set_video_mode", {"mode": "raw"})]

    panel.update_connection_status(True)                         # a control line appeared
    assert panel.ffc_grp.isEnabled() and panel.rad_grp.isEnabled()


def test_panel_shows_the_saved_mode_without_emitting(qapp, cfg):
    set_video_mode("raw")
    from thermal_inspection.gui.camera_control.tau2_control_panel import Tau2ControlPanel
    panel = Tau2ControlPanel()
    sent = []
    panel.command_requested.connect(lambda *a: sent.append(a))
    panel._load_video_mode()
    assert panel.mode_raw_radio.isChecked() and sent == []


def test_every_panel_tab_scrolls_so_tall_tabs_cannot_overlap(qapp, cfg):
    from PyQt6.QtWidgets import QScrollArea
    from thermal_inspection.gui.camera_control.tau2_control_panel import Tau2ControlPanel
    panel = Tau2ControlPanel()
    assert panel.tabs.count() >= 6
    assert all(isinstance(panel.tabs.widget(i), QScrollArea) for i in range(panel.tabs.count()))


def _camera():
    from thermal_inspection.cameras.tau2_camera import Tau2Camera
    return Tau2Camera(raw_mode=True)


def _scene(levels, shape=(256, 256)):
    rng = np.random.default_rng(0)
    return levels[rng.integers(0, len(levels), shape)].astype(np.uint16)


def test_two_cluster_levels_become_contiguous_so_a_linear_stretch_is_not_a_threshold():
    cam = _camera()
    levels = np.concatenate([np.arange(8, 1024, 8), np.arange(4096, 5120, 8)])       # the gapped layout seen live
    out = cam._relabel_sparse_levels(_scene(levels))
    assert out.max() == 255 and len(np.unique(out)) == len(levels)
    ranks = np.unique(out)
    assert np.diff(ranks).max() <= 3                                                   # no big hole left


def test_relabelling_keeps_the_order_of_the_levels():
    cam = _camera()
    frame = _scene(np.array([5, 40, 900, 4100, 5000]))
    out = cam._relabel_sparse_levels(frame)
    order = np.argsort(frame.ravel(), kind="stable")
    assert np.all(np.diff(out.ravel()[order].astype(int)) >= 0)


def test_levels_stay_stable_when_a_level_is_missing_from_a_frame():
    cam = _camera()
    levels = np.arange(10, 2600, 10)
    first = cam._relabel_sparse_levels(_scene(levels))
    partial = cam._relabel_sparse_levels(_scene(levels[levels != 500]))
    probe = np.full((256, 256), 1000, np.uint16)
    assert np.array_equal(cam._relabel_sparse_levels(probe), cam._relabel_sparse_levels(probe.copy()))
    assert partial.max() <= 255 and first.max() == 255


def test_wide_14bit_data_is_left_alone():
    cam = _camera()
    wide = (np.arange(256 * 256, dtype=np.uint16) % 9000 + 7000).reshape(256, 256)
    assert cam._relabel_sparse_levels(wide) is wide
