"""
Per-ROI tracking for the ROI Manager: temperature history, peak hold, trend, threshold alerts, comparison and export.

Pure Python (no Qt, no camera): the app pushes each ROI's statistics (as ThermalAnalyzer.compute_statistics reports
them, in the current display unit) into an ROITracker; the panel reads rows back out. Values are kept in the unit they
arrived in and converted when the app's unit changes, so a history or a peak never mixes degC with degF.
"""
from __future__ import annotations

import csv
import json
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Optional, Tuple

from thermal_inspection.utils.temperature_units import convert, unit_code

HISTORY_LIMIT = 600                 # samples kept per ROI (about 10 minutes at the 1 Hz stats push)
TREND_THRESHOLD_C = 0.5            # recent-vs-previous average difference (in degC) that counts as rising/falling
METRICS = ("max", "avg", "min")
METRIC_LABELS = {"max": "Hottest pixel", "avg": "Average", "min": "Coldest pixel"}


def trend_from_values(values: List[float], threshold: float = TREND_THRESHOLD_C) -> str:
    """'rising' / 'falling' / 'stable' from the last 5 readings versus the 5 before them (same rule as spot meters)."""
    if len(values) < 5:
        return "stable"
    recent = values[-5:]
    previous = values[-10:-5] if len(values) >= 10 else recent
    diff = sum(recent) / len(recent) - sum(previous) / len(previous)
    if diff > threshold:
        return "rising"
    if diff < -threshold:
        return "falling"
    return "stable"


def _delta_scale(unit: str) -> float:
    """How many display-unit degrees one degC difference is (deltas convert by scale only)."""
    return 1.8 if unit_code(unit) == "F" else 1.0


@dataclass
class ROIAlert:
    """Threshold alert on one of an ROI's statistics (hottest pixel, average or coldest pixel)."""
    threshold: float
    metric: str = "max"                  # 'max' | 'avg' | 'min'
    type: str = "above"                  # 'above' | 'below'
    unit: str = "°C"                     # unit the threshold was entered in
    enabled: bool = True
    sound_enabled: bool = True
    triggered: bool = False
    trigger_count: int = 0
    last_trigger_time: float = 0.0

    def check(self, value: Optional[float], unit: Optional[str] = None) -> bool:
        """True while the alert condition holds. `value` is in `unit` (the reading's display unit); it is converted to
        the threshold's unit first so a 50 degC alert doesn't compare against 122 (degF)."""
        if not self.enabled or value is None:
            self.triggered = False
            return False
        if unit is not None:
            converted = convert(value, unit, self.unit)
            if converted is not None:
                value = converted
        hit = value > self.threshold if self.type == "above" else value < self.threshold
        if hit and not self.triggered:
            self.trigger_count += 1
            self.last_trigger_time = time.time()
        self.triggered = hit
        return hit

    def describe(self) -> str:
        word = ">" if self.type == "above" else "<"
        return f"{METRIC_LABELS.get(self.metric, self.metric)} {word} {self.threshold:g} {self.unit}"


@dataclass
class ROIRecord:
    unit: str = "°C"
    history: Deque[Tuple[float, float, float, float]] = field(default_factory=lambda: deque(maxlen=HISTORY_LIMIT))
    peak_max: Optional[float] = None     # hottest pixel ever seen in this ROI
    peak_min: Optional[float] = None     # coldest pixel ever seen in this ROI
    latest: Dict[str, float] = field(default_factory=dict)    # temp_avg / temp_min / temp_max / std / pixel_count ...
    alert: Optional[ROIAlert] = None


class ROITracker:
    def __init__(self):
        self.records: Dict[str, ROIRecord] = {}

    # ------------------------------------------------------------------ feeding

    def update(self, stats: Dict[str, dict], now: Optional[float] = None) -> List[str]:
        """Record a stats push ({roi_id: {'temp_avg', 'temp_min', 'temp_max', 'unit', ...}}). Returns the ids of ROIs
        whose alert JUST started firing (a transition, not every sample)."""
        now = time.time() if now is None else now
        newly = []
        for roi_id, s in stats.items():
            avg, lo, hi = s.get("temp_avg"), s.get("temp_min"), s.get("temp_max")
            rec = self.records.setdefault(roi_id, ROIRecord(unit=s.get("unit", "°C")))
            unit = s.get("unit", rec.unit)
            if unit != rec.unit:
                self._change_unit(rec, unit)
            rec.latest = dict(s)
            if avg is None or lo is None or hi is None:
                continue
            rec.history.append((now, float(avg), float(lo), float(hi)))
            rec.peak_max = float(hi) if rec.peak_max is None else max(rec.peak_max, float(hi))
            rec.peak_min = float(lo) if rec.peak_min is None else min(rec.peak_min, float(lo))
            if rec.alert is not None:
                was = rec.alert.triggered
                value = {"max": hi, "avg": avg, "min": lo}.get(rec.alert.metric, hi)
                if rec.alert.check(value, unit) and not was:
                    newly.append(roi_id)
        return newly

    @staticmethod
    def _change_unit(rec: ROIRecord, new_unit: str):
        """Re-express stored history/peaks in a new display unit; if the units can't be converted (a raw-count unit),
        start over rather than mix scales."""
        probe = convert(0.0, rec.unit, new_unit)
        if probe is None:
            rec.history.clear()
            rec.peak_max = rec.peak_min = None
        else:
            conv = lambda v: convert(v, rec.unit, new_unit)           # noqa: E731
            rec.history = deque(((t, conv(a), conv(l), conv(h)) for t, a, l, h in rec.history), maxlen=HISTORY_LIMIT)
            rec.peak_max = None if rec.peak_max is None else conv(rec.peak_max)
            rec.peak_min = None if rec.peak_min is None else conv(rec.peak_min)
        rec.unit = new_unit

    # ------------------------------------------------------------------ queries

    def prune(self, valid_ids: Iterable[str]):
        """Forget ROIs that no longer exist."""
        keep = set(valid_ids)
        for roi_id in [r for r in self.records if r not in keep]:
            del self.records[roi_id]

    def clear_history(self, roi_id: Optional[str] = None):
        """Clear history and peaks for one ROI (None = all). Alerts keep their configuration."""
        for rid, rec in self.records.items():
            if roi_id is None or rid == roi_id:
                rec.history.clear()
                rec.peak_max = rec.peak_min = None
                if rec.alert is not None:
                    rec.alert.triggered = False

    def set_alert(self, roi_id: str, alert: Optional[ROIAlert]):
        self.records.setdefault(roi_id, ROIRecord()).alert = alert

    def alert(self, roi_id: str) -> Optional[ROIAlert]:
        rec = self.records.get(roi_id)
        return rec.alert if rec else None

    def trend(self, roi_id: str, metric: str = "avg") -> str:
        rec = self.records.get(roi_id)
        if rec is None or len(rec.history) < 5:
            return "stable"
        idx = {"avg": 1, "min": 2, "max": 3}[metric]
        scale = 1.0 if unit_code(rec.unit) != "F" else 1.8
        return trend_from_values([h[idx] for h in rec.history], TREND_THRESHOLD_C * scale)

    def series(self, roi_id: str, metric: str = "avg") -> List[Tuple[float, float]]:
        """[(timestamp, value)] for plotting."""
        rec = self.records.get(roi_id)
        idx = {"avg": 1, "min": 2, "max": 3}[metric]
        return [] if rec is None else [(h[0], h[idx]) for h in rec.history]

    def compare(self, roi_a: str, roi_b: str) -> Optional[dict]:
        """Differences b - a between two ROIs' latest readings, in a's unit, or None when either has no reading."""
        a, b = self.records.get(roi_a), self.records.get(roi_b)
        if not a or not b or not a.history or not b.history:
            return None
        ua, ub = a.unit, b.unit
        out = {"unit": ua}
        for key, idx in (("avg", 1), ("min", 2), ("max", 3)):
            vb = convert(b.history[-1][idx], ub, ua) if ub != ua else b.history[-1][idx]
            if vb is None:
                return None
            out[key] = vb - a.history[-1][idx]
        return out

    def hottest(self, among: Optional[Iterable[str]] = None) -> Optional[str]:
        """Id of the ROI with the highest current hottest-pixel reading (in a common unit), or None. `among` limits the
        candidates (e.g. to ROIs measured in the latest push, so a stale reading can't win)."""
        allowed = None if among is None else set(among)
        best, best_val = None, None
        for rid, rec in self.records.items():
            if not rec.history or (allowed is not None and rid not in allowed):
                continue
            v = convert(rec.history[-1][3], rec.unit, "°C")
            v = rec.history[-1][3] if v is None else v
            if best_val is None or v > best_val:
                best, best_val = rid, v
        return best

    # ------------------------------------------------------------------ export

    def rows(self, rois: Iterable) -> List[dict]:
        """One export/display row per ROI object (processing.roi_manager.ROI), in the ROI's current display unit."""
        rows = []
        for roi in rois:
            rec = self.records.get(roi.roi_id)
            last = rec.history[-1] if rec and rec.history else None
            latest = rec.latest if rec else {}
            pixels = latest.get("pixel_count")
            frame_px = latest.get("frame_pixels")
            alert = rec.alert if rec else None
            rows.append({
                "id": roi.roi_id,
                "name": roi.label or roi.roi_id,
                "type": roi.roi_type.value,
                "locked": bool(roi.locked),
                "visible": bool(roi.active),
                "unit": rec.unit if rec else "",
                "avg": last[1] if last else None,
                "min": last[2] if last else None,
                "max": last[3] if last else None,
                "std": latest.get("temp_std"),
                "peak_max": rec.peak_max if rec else None,
                "peak_min": rec.peak_min if rec else None,
                "pixels": pixels,
                "percent_of_frame": (100.0 * pixels / frame_px) if pixels and frame_px else None,
                "trend": self.trend(roi.roi_id) if rec else "stable",
                "alert": alert.describe() if alert else "",
                "alert_triggered": bool(alert.triggered) if alert else False,
                "alert_count": alert.trigger_count if alert else 0,
            })
        return rows


def write_csv(path: str, rows: List[dict]):
    if not rows:
        raise ValueError("No ROIs to export")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


def write_json(path: str, rows: List[dict]):
    if not rows:
        raise ValueError("No ROIs to export")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"exported_at": time.strftime("%Y-%m-%d %H:%M:%S"), "rois": rows}, f, indent=2)


def export_rows(path: str, rows: List[dict]):
    """CSV or JSON by the file extension (anything else is CSV)."""
    (write_json if path.lower().endswith(".json") else write_csv)(path, rows)
