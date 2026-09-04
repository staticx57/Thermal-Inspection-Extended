"""
Regression test for a perf finding (2026-09-04): SpotMeterPanel.
update_spot_temperatures() is called unconditionally every render tick
from the main frame loop (app.py), once per active spot meter. Its
old implementation called update_temperature() per spot, and THAT
method unconditionally rebuilt the aggregate statistics labels and
redrew the history graph on every single call - so N active spot
meters meant the same aggregate stats/graph got rebuilt N times on a
single frame tick instead of once.

Fixed by splitting per-spot data application (_apply_temperature) from
the aggregate refresh (_update_statistics/_update_graph), and having
update_spot_temperatures call the aggregate refresh exactly once after
every spot in the batch has been applied. update_temperature() (the
single-spot API used elsewhere) keeps its old always-refresh-once
behavior.
"""
import sys
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication

from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPanel

qapp = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def panel():
    p = SpotMeterPanel()
    p.add_spot("spot_1", 10, 10, label="Spot #1")
    p.add_spot("spot_2", 20, 20, label="Spot #2")
    p.add_spot("spot_3", 30, 30, label="Spot #3")
    return p


class TestBatchUpdateRefreshesAggregatesOnce:
    def test_batch_update_calls_aggregate_refresh_exactly_once(self, panel):
        values = [
            {"label": "Spot #1", "temperature": 25.0, "unit": "°C"},
            {"label": "Spot #2", "temperature": 30.0, "unit": "°C"},
            {"label": "Spot #3", "temperature": 35.0, "unit": "°C"},
        ]
        with patch.object(panel, "_update_statistics") as mock_stats, \
             patch.object(panel, "_update_graph") as mock_graph:
            panel.update_spot_temperatures(values)

        assert mock_stats.call_count == 1, (
            "aggregate statistics must be refreshed once per batch, "
            "not once per spot in the batch"
        )
        assert mock_graph.call_count == 1, (
            "the history graph must be redrawn once per batch, not "
            "once per spot in the batch"
        )

    def test_batch_update_still_applies_every_spots_reading(self, panel):
        values = [
            {"label": "Spot #1", "temperature": 25.0, "unit": "°C"},
            {"label": "Spot #2", "temperature": 30.0, "unit": "°C"},
            {"label": "Spot #3", "temperature": 35.0, "unit": "°C"},
        ]
        panel.update_spot_temperatures(values)

        assert panel.spots["spot_1"].temperature == 25.0
        assert panel.spots["spot_2"].temperature == 30.0
        assert panel.spots["spot_3"].temperature == 35.0

    def test_empty_batch_skips_aggregate_refresh_entirely(self, panel):
        """No spots matched (e.g. all labels stale/unknown) - nothing
        to refresh, must not call the aggregate methods at all."""
        with patch.object(panel, "_update_statistics") as mock_stats, \
             patch.object(panel, "_update_graph") as mock_graph:
            panel.update_spot_temperatures([{"label": "Nonexistent", "temperature": 1.0}])

        mock_stats.assert_not_called()
        mock_graph.assert_not_called()

    def test_single_spot_update_temperature_still_refreshes_aggregates(self, panel):
        """The single-spot public API used elsewhere must keep its old
        always-refresh-immediately behavior."""
        with patch.object(panel, "_update_statistics") as mock_stats, \
             patch.object(panel, "_update_graph") as mock_graph:
            panel.update_temperature("spot_1", 42.0)

        mock_stats.assert_called_once()
        mock_graph.assert_called_once()
        assert panel.spots["spot_1"].temperature == 42.0
