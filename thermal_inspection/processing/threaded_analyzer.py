"""
Threaded wrapper around ThermalAnalyzer.analyze().

analyze() (stats + hot/cold spot detection + anomaly detection, and the
8-bit estimator's adaptive-range scan when estimation is enabled) previously
ran inline on the Qt main thread once per _process_frame_loop tick. Its cost
(measured 10-40ms/frame depending on mode) capped video rendering at that
same rate regardless of CPU core count, since it's a single Python call -
extra cores don't parallelize a single-threaded call, and every tick spent
computing it is a tick the video widget doesn't get repainted.

This mirrors ThreadedCameraCapture's existing producer/consumer pattern:
a background thread continuously analyzes whatever the latest submitted
frame is, and the render loop reads the latest available result
non-blocking. Video now renders at full capture-limited speed; hot/cold
spot overlays update at whatever rate analysis can sustain, independently.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)


class ThreadedAnalyzer:
    """Runs ThermalAnalyzer.analyze() on a dedicated background thread."""

    def __init__(self, thermal_analyzer, name: str = "Analyzer"):
        self.thermal_analyzer = thermal_analyzer
        self.name = name

        self._input_lock = threading.Lock()
        self._input_frame: Optional[np.ndarray] = None

        self._results_lock = threading.Lock()
        self._results: Optional[Dict[str, Any]] = None

        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.analysis_count = 0
        self.error_count = 0

    def start(self):
        if self.running:
            logger.warning(f"{self.name}: Already running")
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self.thread.start()
        logger.info(f"{self.name}: Started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info(f"{self.name}: Stopped ({self.analysis_count} analyses, {self.error_count} errors)")

    def submit_frame(self, frame: Optional[np.ndarray]):
        """
        Hand off the latest frame to analyze (non-blocking). Only the most
        recent submission matters - if the background thread is still busy
        on an older frame, an in-between submission is simply overwritten
        rather than queued, so analysis never falls further and further
        behind under sustained load.
        """
        with self._input_lock:
            self._input_frame = frame

    def get_latest_results(self) -> Optional[Dict[str, Any]]:
        """Non-blocking read of the most recently completed analysis."""
        with self._results_lock:
            return self._results

    def _run(self):
        while self.running:
            with self._input_lock:
                frame = self._input_frame
                self._input_frame = None  # consume - don't reanalyze the same frame twice

            if frame is None:
                time.sleep(0.005)
                continue

            try:
                results = self.thermal_analyzer.analyze(frame)
                with self._results_lock:
                    self._results = results
                self.analysis_count += 1
            except Exception as e:
                self.error_count += 1
                logger.error(f"{self.name}: analyze() error: {e}", exc_info=True)
