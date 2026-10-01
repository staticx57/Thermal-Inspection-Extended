"""PagedTabWidget: large arrow buttons on both ends, native continuous scrolling (no tabs popping in/out)."""

import pytest
from PyQt6.QtWidgets import QWidget

from thermal_inspection.gui.widgets.paged_tabwidget import PagedTabWidget


def _settle(qapp):
    for _ in range(4):
        qapp.processEvents()


def _make(qapp, count=14, width=420):
    tw = PagedTabWidget()
    for i in range(count):
        tw.addTab(QWidget(), f"Section {i + 1}")
    tw.resize(width, 200)
    tw.show()
    _settle(qapp)
    return tw


@pytest.mark.unit
class TestPagedTabWidget:
    def test_no_tab_is_hidden_and_buttons_appear(self, qapp):
        tw = _make(qapp)
        bar = tw.tabBar()
        assert all(bar.isTabVisible(i) for i in range(tw.count())), "tabs must scroll, never disappear"
        assert tw._left.isVisible() and tw._right.isVisible()
        assert not tw._left.isEnabled() and tw._right.isEnabled()      # at the start

    def test_next_tab_is_partly_visible_at_the_edge(self, qapp):
        """You can see what comes next: one tab straddles the right edge of the row."""
        tw = _make(qapp)
        bar = tw.tabBar()
        straddling = [i for i in range(tw.count()) if bar.tabRect(i).left() < bar.width() < bar.tabRect(i).right()]
        assert straddling, "expected a partly visible tab at the right edge"

    def test_native_arrows_take_no_space(self, qapp):
        tw = _make(qapp)
        assert tw._native_left is not None and tw._native_right is not None
        assert tw._native_left.width() == 0 and tw._native_right.width() == 0

    def test_buttons_are_large_and_on_opposite_sides(self, qapp):
        tw = _make(qapp)
        assert tw._left.width() >= 30 and tw._left.height() >= 28
        assert tw._left.geometry().center().x() < tw.width() / 2 < tw._right.geometry().center().x()

    def test_clicking_right_scrolls_the_row_and_left_scrolls_back(self, qapp):
        tw = _make(qapp)
        bar = tw.tabBar()
        start_x = bar.tabRect(0).left()
        tw._right.click()
        _settle(qapp)
        assert bar.tabRect(0).left() < start_x, "row should have scrolled left"
        assert tw._left.isEnabled()
        for _ in range(3):
            tw._left.click()
            _settle(qapp)
        assert bar.tabRect(0).left() == start_x
        assert not tw._left.isEnabled()

    def test_can_scroll_to_the_end(self, qapp):
        tw = _make(qapp)
        bar = tw.tabBar()
        for _ in range(tw.count() * 2):
            tw._right.click()
            _settle(qapp)
        assert bar.tabRect(tw.count() - 1).right() <= bar.width() + 1
        assert not tw._right.isEnabled() and tw._left.isEnabled()

    def test_selecting_a_scrolled_out_tab_brings_it_into_view(self, qapp):
        tw = _make(qapp)
        bar = tw.tabBar()
        tw.setCurrentIndex(tw.count() - 1)
        _settle(qapp)
        rect = bar.tabRect(tw.count() - 1)
        assert rect.left() >= 0 and rect.right() <= bar.width() + 1

    def test_no_buttons_when_all_tabs_fit_and_they_return_when_narrowed(self, qapp):
        tw = _make(qapp, count=3, width=900)
        assert not tw._left.isVisible() and not tw._right.isVisible()
        tw.resize(120, 200)
        _settle(qapp)
        assert tw._left.isVisible() and tw._right.isVisible()

    def test_behaves_like_a_normal_tab_widget(self, qapp):
        tw = _make(qapp, count=5, width=900)
        assert tw.count() == 5 and tw.tabText(2) == "Section 3"
        seen = []
        tw.currentChanged.connect(seen.append)
        tw.setCurrentIndex(3)
        assert seen == [3] and tw.currentIndex() == 3
        tw.removeTab(0)
        _settle(qapp)
        assert tw.count() == 4
