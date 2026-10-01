"""
Theme behaviour: consistent button sizing across themes, and "auto" following the OS.
"""

import pytest

from thermal_inspection.gui import themes


@pytest.mark.unit
class TestButtonSizeConsistency:
    def test_buttons_do_not_change_size_with_the_theme(self, qapp):
        """The control-panel buttons under the video must be the same size in every theme
        (they used to swing wildly: 10x20px bold 14px padding in some themes, 4x12px in others)."""
        from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget
        from thermal_inspection.gui.widgets.control_panel import ControlPanel

        sizes = {}
        for name, qss in themes.THEMES.items():
            host = QWidget()
            lay = QVBoxLayout(host)
            panel = ControlPanel()
            lay.addWidget(panel)
            host.setStyleSheet(qss + themes.STATE_COLORS_QSS)
            host.resize(1100, 200)
            host.show()
            qapp.processEvents()
            sizes[name] = [(b.sizeHint().width(), b.sizeHint().height())
                           for b in panel.findChildren(QPushButton)]
            host.close()

        reference = sizes["Dark Mode"]
        for name, per_button in sizes.items():
            for (w, h), (rw, rh) in zip(per_button, reference):
                assert w == rw, f"{name}: button width {w} != {rw}"
                assert abs(h - rh) <= 3, f"{name}: button height {h} vs {rh}"


@pytest.mark.unit
class TestAutoTheme:
    def test_auto_follows_the_os_setting(self, monkeypatch):
        monkeypatch.setattr(themes, "system_prefers_dark", lambda: True)
        assert themes.resolve_auto_theme(now_hour=12) == "Dark Mode"      # midday, but OS says dark
        monkeypatch.setattr(themes, "system_prefers_dark", lambda: False)
        assert themes.resolve_auto_theme(now_hour=23) == "Light Mode"     # midnight, but OS says light

    def test_auto_falls_back_to_time_of_day_when_os_setting_unknown(self, monkeypatch):
        monkeypatch.setattr(themes, "system_prefers_dark", lambda: None)
        assert themes.resolve_auto_theme(now_hour=12) == "Light Mode"
        assert themes.resolve_auto_theme(now_hour=22) == "Dark Mode"
        assert themes.resolve_auto_theme(now_hour=6) == "Dark Mode"

    def test_resolved_theme_always_exists(self, monkeypatch):
        for pref in (True, False, None):
            monkeypatch.setattr(themes, "system_prefers_dark", lambda p=pref: p)
            assert themes.resolve_auto_theme() in themes.THEMES

    def test_system_query_never_raises(self):
        assert themes.system_prefers_dark() in (True, False, None)


@pytest.mark.unit
class TestSoftenedDarkLight:
    def test_no_pure_white_or_black_extremes_in_base_backgrounds(self):
        import re
        for name in ("DARK_THEME", "LIGHT_THEME"):
            qss = getattr(themes, name)
            base_bg = re.search(r"QMainWindow \{\s*background-color: (#[0-9a-fA-F]{6})", qss).group(1).lower()
            assert base_bg not in ("#000000", "#ffffff")
        # the old neon info-panel green and harsh near-black/near-white are gone
        assert "#00ff00" not in themes.DARK_THEME.lower()
        assert "#1a1a1a" not in themes.DARK_THEME.lower()
        assert "#f5f5f5" not in themes.LIGHT_THEME.lower()


@pytest.mark.unit
class TestThemeButtonLabel:
    def test_label_fits_the_button_for_every_theme_and_auto(self, qapp):
        """The theme button's text (icon + short name, or 'Auto: X') must never overflow its column."""
        from PyQt6.QtWidgets import QVBoxLayout, QWidget
        from thermal_inspection.gui.widgets.control_panel import ControlPanel

        host = QWidget()
        lay = QVBoxLayout(host)
        panel = ControlPanel()
        lay.addWidget(panel)
        host.setStyleSheet(themes.THEMES["Dark Mode"] + themes.STATE_COLORS_QSS)
        host.resize(1100, 200)
        host.show()
        qapp.processEvents()
        width = panel.theme_btn.width()

        labels = list(themes.THEMES) + [f"auto ({name})" for name in themes.THEMES]
        for label in labels:
            panel.update_theme_button(label)
            qapp.processEvents()
            assert panel.theme_btn.sizeHint().width() <= width, (label, panel.theme_btn.text())
            assert panel.theme_btn.text().strip() not in ("🌓 Theme",), f"{label!r} has no button label entry"
        host.close()
