"""Guided hand-held test of 3D Mapping on a real RealSense (L515/D4xx).

Run:  python tools/mapping_motion_test.py        (close the normal app first - it needs the camera)

It opens the real app, switches to 3D Mapping, and prints cues you follow while holding the camera:
  1. SCAN (25 s):   pan slowly left, then right, then return to where you started and hold still.
                    -> reports how far the tracked pose is from the start when you come back (loop drift).
  2. LIVE (25 s):   after Finish, pan around the mapped area slowly, then cover the lens for ~3 s, then uncover it.
                    -> reports tracking quality over time, how long it was lost and whether it recovered.
Results are printed as one line per second plus a summary. Nothing is saved or changed.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
os.environ["OPENCV_VIDEOIO_PRIORITY_OBSENSOR"] = "0"
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
sys.coinit_flags = 0
try:
    import open3d  # noqa: F401  must load before Qt
except ImportError:
    sys.exit("open3d is not installed")
import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from thermal_inspection import app as appmod

SCAN_START, SCAN_END = 12, 37          # seconds after launch
LIVE_END = 65
log = []


def run(self):
    gui, wm, panel = self.gui, self.world_mapper, self.gui.mapping_fusion_panel
    t0 = time.time()

    def now():
        return time.time() - t0

    def say(msg):
        print(f"\n>>> [{now():4.0f}s] {msg}", flush=True)

    def sample():
        p = np.asarray(wm._pose)[:3, 3]
        log.append((now(), wm.state, wm.quality_state, wm.tracking_quality, wm.point_count, p.copy(),
                    wm._scan_lost_frames, wm.relocalizing))
        print(f"  {now():4.0f}s {wm.state:9s} q={wm.quality_state:8s}({wm.tracking_quality:6.2f}) "
              f"pts={wm.point_count:>7,} pose=({p[0]:+.2f},{p[1]:+.2f},{p[2]:+.2f}) "
              f"skipped={wm._scan_lost_frames} reloc={wm.relocalizing}", flush=True)

    start_pose = {}

    def start():
        panel._start_button.click()
        say("SCANNING. Pan slowly LEFT ... then RIGHT ... then come back to the START view and hold still.")
        start_pose["t"] = np.asarray(wm._pose)[:3, 3].copy()

    def finish():
        end = np.asarray(wm._pose)[:3, 3]
        drift = float(np.linalg.norm(end - start_pose["t"]))
        say(f"Back at start? Tracked pose is {drift * 100:.1f} cm from where it started (loop drift).")
        panel._finish_button.click()
        say("FINISHED. LIVE tracking: pan around the mapped area slowly. At ~15 s cover the lens for 3 s, then uncover.")

    def summary():
        live = [r for r in log if r[1] == "mapped"]
        scan = [r for r in log if r[1] == "scanning"]
        lost = [r for r in live if r[2] == "lost"]
        say("SUMMARY")
        if scan:
            print(f"  scan: {len(scan)} samples, final points {scan[-1][4]:,}, max skipped frames {max(r[6] for r in scan)}")
        if live:
            good = sum(r[2] == "good" for r in live)
            print(f"  live: {len(live)} samples, good {good}, degraded {sum(r[2] == 'degraded' for r in live)}, lost {len(lost)}")
            print(f"  live ended in state: {live[-1][2]} (recovered = good/degraded at the end)")
        QApplication.quit()

    for t in range(1, LIVE_END):
        QTimer.singleShot(t * 1000, sample)
    QTimer.singleShot(2000, lambda: say(f"Get ready, holding the camera. Scan starts at {SCAN_START}s."))
    QTimer.singleShot(SCAN_START * 1000, start)
    QTimer.singleShot(SCAN_END * 1000, finish)
    QTimer.singleShot(SCAN_END * 1000 + 15000, lambda: say("COVER the lens now (3 s)"))
    QTimer.singleShot(SCAN_END * 1000 + 18500, lambda: say("UNCOVER the lens; point back at the scene"))
    QTimer.singleShot(LIVE_END * 1000, summary)
    return orig_run(self)


orig_run = appmod.ThermalInspectionApp.run
appmod.ThermalInspectionApp.run = run
from thermal_inspection.cli import main  # noqa: E402

sys.argv = ["thermal_inspection"]
main()
