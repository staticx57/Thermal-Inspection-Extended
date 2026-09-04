"""
Regression test for a rendering-jitter finding (2026-09-03):
ThermalInspectionApp._gui_invoke() always marshaled its call through
QTimer.singleShot(0, ...), even though its by-far-most-frequent caller
(_process_frame_loop, which fires many _gui_invoke calls per rendered
frame) already runs on the GUI thread - self.timer, the QTimer driving
it, is never moved off that thread. Marshaling an already-on-thread
call adds a pure, unnecessary event-loop round trip on every tick that
fires one of these. Fixed to call directly when already on the GUI
thread, keeping the marshal only for genuinely cross-thread callers
(ThreadedCapture, ThreadedAnalyzer).
"""
from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import QCoreApplication

from thermal_inspection.app import AppConfig, ThermalInspectionApp


@pytest.mark.unit
def test_gui_invoke_calls_directly_when_already_on_gui_thread(qapp):
    app = ThermalInspectionApp(AppConfig(headless=True))
    mock_method = MagicMock()
    app.gui = type("FakeGui", (), {"some_update": mock_method})()

    app._gui_invoke("some_update", 1, 2)

    # Must have run synchronously - no event-loop processing needed.
    mock_method.assert_called_once_with(1, 2)


@pytest.mark.unit
def test_gui_invoke_still_marshals_when_gui_is_none(qapp):
    """gui_ref is None (headless, no window) - must not raise, must not
    call anything."""
    app = ThermalInspectionApp(AppConfig(headless=True))
    app.gui = None

    app._gui_invoke("anything", 1, 2)  # must not raise
