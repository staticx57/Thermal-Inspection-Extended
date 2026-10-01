"""The Gradient controls belong with Detection (highlighting), not Analysis (measuring)."""

import logging

import pytest


@pytest.fixture(scope="module")
def window(qapp):
    logging.disable(logging.CRITICAL)
    from thermal_inspection.gui.main_window import InspectionAppWindow
    win = InspectionAppWindow(None)
    win.show()
    qapp.processEvents()
    yield win
    win.close()
    logging.disable(logging.NOTSET)


def _tab_titles(tabs):
    return [tabs.tabText(i) for i in range(tabs.count())]


@pytest.mark.unit
class TestGradientPlacement:
    def test_gradient_is_a_detection_subtab(self, window):
        assert "Gradient" in _tab_titles(window.combined_anomaly_widget.mode_tabs)
        assert _tab_titles(window.combined_anomaly_widget.mode_tabs)[:2] == ["Automatic", "Manual"]

    def test_gradient_is_no_longer_under_analysis(self, window):
        assert "Gradient" not in _tab_titles(window.analysis_tabs)

    def test_gradient_panel_is_inside_the_detection_tab(self, window):
        panel = window.gradient_panel
        detection = window.combined_anomaly_widget
        assert detection.isAncestorOf(panel)
        assert not window.analysis_tabs.isAncestorOf(panel)

    def test_panel_is_still_wired_to_the_window_handlers(self, window):
        """Moving the tab must not break the signal wiring (enable/mode/threshold/sensitivity/colormap)."""
        calls = []
        window._apply_gradient_setting = lambda **kw: calls.append(kw)
        window.gradient_panel.enable_cb.setChecked(True)
        window.gradient_panel.sensitivity_slider.setValue(70)
        window.gradient_panel.colormap_combo.setCurrentIndex(2)
        assert {"enabled": True} in calls
        assert {"sensitivity": 70} in calls
        assert any("colormap" in c for c in calls)
