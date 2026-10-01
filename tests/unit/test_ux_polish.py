"""UI/UX polish (2026-10-02): safe quitting, honest source/status text, panels that say why they are empty or unavailable, no
unreadable hard-coded colours, working settings controls, accessibility. Several of these only show up with hardware
attached (a populated camera-info panel, a depth camera that has not delivered its first frame yet), so they are tested
with simulated populated states, not just blank ones."""
import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QSpinBox, QWidget


@pytest.fixture(scope="module")
def win(qapp):
    from thermal_inspection.app import AppConfig, ThermalInspectionApp
    from thermal_inspection.gui.main_window import InspectionAppWindow
    app = ThermalInspectionApp(AppConfig(headless=True), qapp)
    w = InspectionAppWindow(app)
    yield w
    w.recording = False


def fake_active(name="FLIR Boson 640", plugin_id="flir_boson", res=(640, 512), radiometric=True, info=None):
    backend = MagicMock()
    backend.get_resolution.return_value = res
    backend.get_info.return_value = info or {}
    return SimpleNamespace(
        match=SimpleNamespace(name=name),
        plugin=SimpleNamespace(display_name="FLIR Boson", plugin_id=plugin_id),
        backend=backend, capabilities=SimpleNamespace(radiometric=radiometric))


class TestQuitting:
    def test_escape_and_q_no_longer_quit(self, win, qapp):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        win.close = MagicMock()
        for key in (Qt.Key.Key_Escape, Qt.Key.Key_Q):
            win.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))
        win.close.assert_not_called()
        del win.close

    def test_closing_while_recording_asks_first(self, win):
        from PyQt6.QtGui import QCloseEvent
        win.recording = True
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as q:
            ev = QCloseEvent()
            win.closeEvent(ev)
            assert q.called and not ev.isAccepted()
        win.recording = False
        with patch.object(QMessageBox, "question") as q:
            ev = QCloseEvent()
            win.closeEvent(ev)
            assert not q.called and ev.isAccepted()

    def test_menu_has_quit_and_a_complete_shortcut_list(self, win):
        titles = [a.text() for a in win.menuBar().actions()]
        assert "&File" in titles and "&Help" in titles
        src = inspect.getsource(type(win).keyPressEvent)
        for key, _ in win.SHORTCUTS:
            if len(key) == 1:                      # every documented single-letter key is really handled
                assert f"Key_{key}" in src, key
        assert "(R)" in win.control_panel.record_btn.toolTip() and "(Space)" in win.control_panel.freeze_btn.toolTip()


class TestSourceIndicator:
    @staticmethod
    def describe(win, active):
        host = SimpleNamespace(get_active_camera=lambda role: active)
        stub = SimpleNamespace(app=SimpleNamespace(plugin_host=host))
        return type(win)._describe_source(stub, "thermal")

    def test_text_for_a_live_camera_a_recording_and_nothing(self, win):
        live = self.describe(win, fake_active())
        text = win._source_text(live, "thermal")
        assert "FLIR Boson 640" in text and "640x512" in text and "radiometric (temperatures)" in text
        rec = self.describe(win, fake_active("demo.seq", "flir_file", (320, 256), True,
                                             {"backend": "FLIR file", "frames": 20, "fps": 9.0}))
        assert "recording, 20 frames at 9 fps" in win._source_text(rec, "thermal")
        assert "No thermal camera streaming" in win._source_text(None, "thermal")
        assert "not radiometric" in win._source_text(
            {"name": "UVC", "plugin": "", "resolution": None, "radiometric": False, "detail": ""}, "thermal")

    def test_banner_and_active_tab_marker_follow_the_host(self, win):
        host = SimpleNamespace(get_active_camera=lambda role: fake_active() if role == "thermal" else None)
        win.app.plugin_host = host
        win._refresh_source_banners()
        assert "FLIR Boson 640" in win.source_banners["thermal"].text()
        assert "No RGB camera streaming" in win.source_banners["rgb"].text()
        boson = win.camera_panels["flir_boson"]
        tabs = win.thermal_cameras_tabs
        assert tabs.tabText(tabs.indexOf(boson)).endswith("●")
        assert not any(tabs.tabText(i).endswith("●") for i in range(tabs.count()) if tabs.widget(i) is not boson)
        win.app.plugin_host = SimpleNamespace(get_active_camera=lambda role: None)
        win._refresh_source_banners()
        assert not tabs.tabText(tabs.indexOf(boson)).endswith("●")


class TestHud:
    def test_fps_dot_says_frames_are_arriving_not_that_the_rate_is_good(self, qapp):
        from thermal_inspection.gui.widgets.info_panel import InfoPanel
        p = InfoPanel()
        p.update_info(9.0, 0, True, False)
        assert "FPS: 9.0" in p.text() and "#6fdc8c" in p.text()         # a 9 Hz radiometric Boson is healthy
        p.update_info(0.0, 0, False, False)
        assert "#8a929a" in p.text()
        assert "background-color: rgba(10, 12, 16" in p.styleSheet()    # readable on any video, any theme


class TestSettings:
    def test_control_port_and_data_folder_are_wired(self, qapp, monkeypatch, tmp_path):
        from thermal_inspection.gui.panels.settings_panel import SettingsPanel
        monkeypatch.setenv("THERMAL_INSPECTION_HOME", str(tmp_path))
        p = SettingsPanel()
        got = []
        p.com_port_changed.connect(got.append)
        assert p.com_port_edit.itemText(0) == p.AUTO_PORT
        p.com_port_edit.setCurrentText("COM9")
        p._emit_port()
        p.com_port_edit.setCurrentText(p.AUTO_PORT)
        p._emit_port()
        assert got == ["COM9", ""]
        assert str(tmp_path) in p.paths_btn.toolTip()
        with patch("PyQt6.QtGui.QDesktopServices.openUrl") as opened:
            p.paths_btn.click()
            from pathlib import Path
            assert opened.called and Path(opened.call_args[0][0].toLocalFile()) == tmp_path

    def test_window_persists_the_override(self, win):
        from thermal_inspection.utils.config import get_config
        with patch.object(get_config().__class__, "set", return_value=True) as setter:
            win._on_com_port_changed("COM11")
            win._on_com_port_changed("")
        assert [c.args for c in setter.call_args_list] == [("sdk_com_port", "COM11"), ("sdk_com_port", None)]


class TestMappingAvailability:
    def test_panel_disables_start_with_a_reason_and_keeps_load(self, qapp):
        from thermal_inspection.gui.panels.mapping_fusion_panel import MappingFusionPanel
        p = MappingFusionPanel()
        assert p._start_button.isEnabled()
        p.set_available(False, "needs a RealSense")
        assert not p._start_button.isEnabled() and not p._availability_label.isHidden()
        assert "RealSense" in p._availability_label.text() and p._load_button.isEnabled()
        p.set_status("idle", "n/a", 0)                        # a later status update must not re-enable Start
        assert not p._start_button.isEnabled()
        p.set_available(True)
        assert p._start_button.isEnabled() and p._availability_label.isHidden()

    def test_real_depth_camera_before_its_first_frame_is_still_available(self, win):
        """get_depth_intrinsics() is None until a depth frame arrives: that must not read as 'no depth camera'."""
        backend = SimpleNamespace(get_depth_intrinsics=lambda: None)
        with patch.object(type(win.app), "rgb_camera", new_callable=lambda: property(lambda self: backend)):
            win._refresh_mapping_availability()
        assert win.mapping_fusion_panel._start_button.isEnabled()
        no_depth = SimpleNamespace()
        with patch.object(type(win.app), "rgb_camera", new_callable=lambda: property(lambda self: no_depth)):
            win._refresh_mapping_availability()
        assert not win.mapping_fusion_panel._start_button.isEnabled()
        with patch.object(type(win.app), "rgb_camera", new_callable=lambda: property(lambda self: None)):
            win._refresh_mapping_availability()
        assert "No RGB/depth camera" in win.mapping_fusion_panel._availability_label.text()


class TestThemeAwareColours:
    def test_roles_exist_in_the_qss_and_reject_typos(self, qapp):
        from thermal_inspection.gui.themes import ROLES, STATE_COLORS_QSS, set_role
        for role in ROLES:
            assert f'QLabel[role="{role}"]' in STATE_COLORS_QSS
        with pytest.raises(ValueError):
            set_role(QLabel(), "greeen")
        lab = QLabel()
        lab.setStyleSheet("color: red;")
        set_role(lab, "ok")
        assert lab.styleSheet() == "" and lab.property("role") == "ok"

    def test_boson_panel_populated_with_hardware_info_has_no_near_white_text(self, qapp):
        """The camera-info values were set to #e0e0e0, invisible on the light theme: only visible once a camera was
        connected, so a blank-state screenshot never showed it."""
        from thermal_inspection.gui.camera_control.boson_control_panel import BosonControlPanel
        p = BosonControlPanel()
        p.update_camera_info({"serial": "123456", "part_number": "4640-0000", "firmware": "4.2.1", "lens_number": 4,
                              "table_number": 2, "gain_mode": "HIGH", "external_sync": "disabled"})
        offenders = [w for w in p.findChildren(QLabel)
                     if any(c in w.styleSheet().lower() for c in ("#e0e0e0", "#aaf", "color: white"))]
        assert not offenders
        assert all(p.info_labels[k].styleSheet() == "" for k in ("serial", "part_number", "software", "lens", "table"))

    def test_mode_pill_sets_text_and_background_together_in_every_state(self, qapp):
        from thermal_inspection.gui.camera_control.boson_control_panel import BosonControlPanel
        p = BosonControlPanel()
        for radiometric, success in ((True, True), (False, True), (False, False)):
            p.update_radiometric_mode_status(radiometric, success)
            css = p.radiometric_mode_status.styleSheet()
            assert "background-color" in css and "color:" in css.replace("background-color", "")
        p.update_radiometric_mode_status(False, True)
        assert "#5c4410" in p.radiometric_mode_status.styleSheet()        # 8-bit is amber, not a green "success"


class TestEmptyStates:
    def test_hint_shows_only_while_empty(self, qapp):
        from PyQt6.QtGui import QImage
        from thermal_inspection.gui.widgets.empty_hint import HintListWidget, HintTableWidget

        def rendered(widget):
            widget.resize(300, 120)
            img = widget.grab().toImage()
            return img.convertToFormat(QImage.Format.Format_RGB32).bits().asstring(img.sizeInBytes())

        plain, hinted = HintListWidget(""), HintListWidget("Nothing here yet")
        assert rendered(plain) != rendered(hinted)
        hinted.addItem("row")
        assert hinted.count() == 1
        t = HintTableWidget(0, 2, hint="No ROIs yet")
        assert t.empty_hint == "No ROIs yet" and t.rowCount() == 0

    def test_panels_ship_with_hints(self, qapp):
        from thermal_inspection.gui.panels.calibration_panel import CalibrationPanel
        from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPanel
        assert "Add Spot Meter" in SpotMeterPanel().spot_list.empty_hint
        assert "reference points" in CalibrationPanel().points_table.empty_hint


class TestHonestRadiometricText:
    def test_no_unconditional_accuracy_number(self, qapp):
        from thermal_inspection.gui.panels.radiometric_panel import RadiometricPanel
        p = RadiometricPanel()
        p.update_active_mode_status("16bit", "verify against a reference", "16-bit T-Linear radiometric")
        assert "±2" not in p.status_banner.text() and "verify against a reference" in p.status_banner.text()
        assert "calibration" in p.status_banner.toolTip().lower()
        groups = [g.title() for g in p.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QGroupBox"]).QGroupBox)]
        assert "Scene / Display Range" in groups and "Temperature Range" not in groups


class TestAccessibility:
    def test_names_come_from_text_label_or_tooltip(self, qapp):
        from PyQt6.QtWidgets import QHBoxLayout
        from thermal_inspection.gui.accessibility import apply_accessible_names
        root = QWidget()
        lay = QHBoxLayout(root)
        btn = QPushButton("\U0001F50D Auto ROI")
        lab, spin = QLabel("Horizontal:"), QSpinBox()
        tip_only = QPushButton("")
        tip_only.setToolTip("Reset zoom\nsecond line")
        for w in (btn, lab, spin, tip_only):
            lay.addWidget(w)
        apply_accessible_names(root)
        assert btn.accessibleName() == "Auto ROI"
        assert spin.accessibleName() == "Horizontal"
        assert tip_only.accessibleName() == "Reset zoom"

    def test_tooltips_fill_gaps_without_overwriting(self, qapp):
        from thermal_inspection.gui.accessibility import apply_tooltips
        from thermal_inspection.gui.panels.isotherm_panel import IsothermPanel
        p = IsothermPanel()
        p.add_band_btn.setToolTip("mine")
        assert apply_tooltips(p) > 5
        assert p.add_band_btn.toolTip() == "mine" and p.hotspot_btn.toolTip()

    def test_whole_window_has_no_unnamed_interactive_control(self, win, qapp):
        from thermal_inspection.gui.accessibility import INTERACTIVE, apply_accessible_names
        win._polish_accessibility()
        apply_accessible_names(win)
        missing = [type(w).__name__ + ":" + (w.objectName() or w.toolTip() or "?")
                   for w in win.findChildren(QWidget)
                   if isinstance(w, INTERACTIVE) and not w.accessibleName()
                   and not (type(w).__name__ == "QLineEdit" and type(w.parentWidget()).__name__ in ("QComboBox", "QSpinBox", "QDoubleSpinBox"))]
        assert len(missing) <= 3, missing                     # only a few internal widgets may stay unnamed


class TestControlPanelLayout:
    def test_even_grid_with_a_full_width_theme_row(self, qapp):
        from thermal_inspection.gui.widgets.control_panel import ControlPanel
        cp = ControlPanel()
        lay = cp.controls_layout
        assert lay.getItemPosition(lay.indexOf(cp.view_mode_btn))[:2] == (1, 3)
        r, c, rs, cs = lay.getItemPosition(lay.indexOf(cp.theme_btn))
        assert (r, c, cs) == (2, 0, 4)
        assert "View:" in cp.view_mode_btn.text()


class TestNoDeveloperMode:
    """The 'developer mode' toggle was an artifact of the ADAS product this was forked from: it only hid the right-hand
    panel (and resized the window by a fixed 350 px). It is now a plain View > Side panel toggle."""

    def test_side_panel_toggle_replaces_it(self, win, qapp):
        assert not hasattr(win, "developer_mode") and not hasattr(win, "_toggle_developer_mode")
        assert not hasattr(win.control_panel, "show_developer_controls")
        assert "&View" in [a.text() for a in win.menuBar().actions()]
        before = win.width()
        win._side_panel_action.setChecked(False)
        assert win.right_panel_tabs.isHidden() and win.width() == before          # no size hack
        win._side_panel_action.setChecked(True)
        assert not win.right_panel_tabs.isHidden()
        win._set_side_panel_visible(False)
        assert not win._side_panel_action.isChecked()                             # menu stays in sync
        win._set_side_panel_visible(True)

    def test_no_developer_text_left(self, win):
        assert "Developer" not in win.statusBar().currentMessage()
        assert all("Ctrl+D" not in d and "eveloper" not in d for _, d in win.SHORTCUTS)
        from thermal_inspection import __version__
        assert win.windowTitle().endswith(__version__)
