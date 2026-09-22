# Spot-Meter Distance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Spot Meter shows estimated distance-to-point whenever a RealSense camera (D400 or L515) is the active RGB source, in any view mode.

**Architecture:** `app.py`'s existing spot-meter update loop gains a per-point depth lookup (RealSense depth frame resized to thermal resolution, sampled at the point's thermal-frame coordinates) that flows through the same dict-based pipeline temperature already uses, down to `MeasurementPoint` and `SpotMeterData`, ending in a small text-display change in the spot list.

**Tech Stack:** Python, existing `RGBCameraRealSense.get_depth_frame()` (thermal_inspection/cameras/realsense_camera.py), no new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-22-3d-mapping-fusion-design.md` (Spot-Meter Distance section)

## Global Constraints

- Distance is `None` whenever the active RGB camera isn't RealSense (no `get_depth_frame` attribute), or the depth reading at that point is outside the valid range (`MIN_VALID_DEPTH_M`/`MAX_VALID_DEPTH_M` from `thermal_inspection/processing/parallax_compensator.py`).
- This is a resize-only depth lookup (RealSense depth resized to thermal's resolution, no parallax shift/zoom correction applied) — full alignment-corrected distance would require running `parallax_compensator.apply_correction()` unconditionally regardless of view mode, an added per-frame cost this feature doesn't need to pay for a rough reading. Document this as a known approximation in the code, the same honesty standard this codebase already applies to its other estimation paths.
- Never break existing temperature-only spot metering when no RealSense camera is connected — `distance_m` must default to `None` everywhere it's threaded through.

---

### Task 1: `MeasurementPoint` gains a `distance_m` field

**Files:**
- Modify: `thermal_inspection/gui/widgets/measurement_point.py`
- Test: `tests/unit/test_measurement_point.py` (new file)

**Interfaces:**
- Produces: `MeasurementPoint.distance_m: Optional[float]` (default `None`), used by Task 4.

- [ ] **Step 1: Write the failing test**

```python
from thermal_inspection.gui.widgets.measurement_point import MeasurementPoint


def test_measurement_point_defaults_distance_to_none():
    point = MeasurementPoint(x=10, y=20, label="Test")
    assert point.distance_m is None


def test_measurement_point_accepts_distance():
    point = MeasurementPoint(x=10, y=20, label="Test", distance_m=1.42)
    assert point.distance_m == 1.42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_measurement_point.py -v`
Expected: FAIL with `TypeError: MeasurementPoint.__init__() got an unexpected keyword argument 'distance_m'`

- [ ] **Step 3: Add the field**

In `thermal_inspection/gui/widgets/measurement_point.py`, add to the dataclass:

```python
@dataclass
class MeasurementPoint:
    """Spot measurement point."""
    x: int
    y: int
    label: str
    color: tuple = (255, 255, 0)  # RGB
    temperature: Optional[float] = None
    unit: str = "°C"
    distance_m: Optional[float] = None  # Real depth-camera distance to this point, meters; None if no RealSense
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_measurement_point.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add thermal_inspection/gui/widgets/measurement_point.py tests/unit/test_measurement_point.py
git commit -m "feat: add distance_m field to MeasurementPoint"
```

---

### Task 2: `SpotMeterData` gains `distance_m`, `_apply_temperature` stores it, list display shows it

**Files:**
- Modify: `thermal_inspection/gui/panels/spot_meter_panel.py`
- Test: `tests/unit/test_spot_meter_distance.py` (new file)

**Interfaces:**
- Consumes: nothing new.
- Produces: `SpotMeterData.distance_m: Optional[float]`; `SpotMeterPanel._apply_temperature(spot_id, temperature, unit="°C", distance_m=None) -> bool` (new optional param); `SpotMeterListItem.update_display()` renders `" @ X.XXm"` when `distance_m is not None`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from PyQt6.QtWidgets import QApplication
from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterPanel, SpotMeterData


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_apply_temperature_stores_distance(qapp):
    panel = SpotMeterPanel()
    panel.add_spot("s1", 10, 20, label="Spot 1")
    panel._apply_temperature("s1", 42.0, "°C", distance_m=1.75)
    assert panel.spots["s1"].distance_m == 1.75


def test_apply_temperature_without_distance_defaults_none(qapp):
    panel = SpotMeterPanel()
    panel.add_spot("s1", 10, 20, label="Spot 1")
    panel._apply_temperature("s1", 42.0, "°C")
    assert panel.spots["s1"].distance_m is None


def test_list_item_display_includes_distance(qapp):
    data = SpotMeterData(id="s1", label="Spot 1", x=10, y=20, temperature=42.0, distance_m=1.75)
    from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterListItem
    item = SpotMeterListItem(data)
    assert "1.75m" in item.text()


def test_list_item_display_omits_distance_when_none(qapp):
    data = SpotMeterData(id="s1", label="Spot 1", x=10, y=20, temperature=42.0, distance_m=None)
    from thermal_inspection.gui.panels.spot_meter_panel import SpotMeterListItem
    item = SpotMeterListItem(data)
    assert "m)" not in item.text().replace("(10, 20)", "")  # no stray "Xm)" from a distance suffix
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_spot_meter_distance.py -v`
Expected: FAIL — `SpotMeterData` has no `distance_m` field (`TypeError`), `_apply_temperature` has no `distance_m` param.

- [ ] **Step 3: Implement**

In `thermal_inspection/gui/panels/spot_meter_panel.py`, add the field to `SpotMeterData` (after `unit`):

```python
    unit: str = "°C"                     # Temperature unit
    distance_m: Optional[float] = None   # Real depth-camera distance to this point, meters; None if no RealSense
```

Extend `_apply_temperature`:

```python
    def _apply_temperature(self, spot_id: str, temperature: float, unit: str = "°C",
                            distance_m: Optional[float] = None) -> bool:
        """Store a new reading and refresh just this spot's own list item -
        the aggregate stats/graph refresh is the caller's job (a single
        call after every spot in a batch is done, not once per spot)."""
        if spot_id not in self.spots:
            return False

        data = self.spots[spot_id]
        data.temperature = temperature
        data.unit = unit
        data.distance_m = distance_m
        data.updated_at = time.time()
        data.add_history(temperature)

        # Check alerts (Phase 6)
        self.check_alerts(spot_id, temperature)

        # Update list item display
        self._refresh_list_item(spot_id)
        return True
```

Update `update_spot_temperatures` to pass it through:

```python
                    if self._apply_temperature(
                        spot_id,
                        val.get('temperature'),
                        val.get('unit', '°C'),
                        distance_m=val.get('distance_m')
                    ):
                        any_updated = True
```

Update `SpotMeterListItem.update_display()` to append distance:

```python
        # Distance (real depth-camera reading, RealSense only - resize-only
        # approximation, not parallax-shift-corrected, see app.py's
        # spot-meter loop for why)
        dist_str = f" @ {data.distance_m:.2f}m" if data.distance_m is not None else ""

        # Build display text
        display_text = f"{indicators}{data.label}: {temp_str}{trend_icon}{dist_str}  ({data.x}, {data.y})"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_spot_meter_distance.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add thermal_inspection/gui/panels/spot_meter_panel.py tests/unit/test_spot_meter_distance.py
git commit -m "feat: SpotMeterPanel stores and displays distance-to-point"
```

---

### Task 3: `main_window.py` forwards `distance_m` from spot values to `MeasurementPoint`

**Files:**
- Modify: `thermal_inspection/gui/main_window.py:2266-2281` (`update_spot_meter_values`)
- Test: `tests/unit/test_main_window_panel_lifecycle.py` (add a test — this file already exercises `main_window` GUI wiring, follow its existing fixture pattern)

**Interfaces:**
- Consumes: `MeasurementPoint.distance_m` (Task 1), spot-value dicts with an optional `'distance_m'` key (Task 4 produces these).
- Produces: nothing new downstream — this is the middle of an existing pipe.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_main_window_panel_lifecycle.py` (match its existing imports/fixtures for constructing a `main_window` instance — check the top of that file for the exact fixture name before writing this, it varies file to file in this suite):

```python
def test_update_spot_meter_values_forwards_distance(main_window):
    from thermal_inspection.gui.widgets.measurement_point import MeasurementPoint
    point = MeasurementPoint(x=10, y=20, label="Spot 1")
    main_window.measurement_points = [point]

    main_window.update_spot_meter_values([
        {'label': 'Spot 1', 'temperature': 42.0, 'unit': '°C', 'distance_m': 1.42}
    ])

    assert point.distance_m == 1.42


def test_update_spot_meter_values_defaults_distance_none_when_absent(main_window):
    from thermal_inspection.gui.widgets.measurement_point import MeasurementPoint
    point = MeasurementPoint(x=10, y=20, label="Spot 1")
    main_window.measurement_points = [point]

    main_window.update_spot_meter_values([
        {'label': 'Spot 1', 'temperature': 42.0, 'unit': '°C'}
    ])

    assert point.distance_m is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_main_window_panel_lifecycle.py -v -k distance`
Expected: FAIL — `point.distance_m` stays at its pre-call value (never set), assertion error.

- [ ] **Step 3: Implement**

In `thermal_inspection/gui/main_window.py`, `update_spot_meter_values` (~line 2266):

```python
    def update_spot_meter_values(self, values: List[Dict]):
        updated = False
        val_map = {v['label']: v for v in values}

        for point in self.measurement_points:
            if point.label in val_map:
                data = val_map[point.label]
                point.temperature = data['temperature']
                point.unit = data['unit']
                point.distance_m = data.get('distance_m')
                updated = True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_main_window_panel_lifecycle.py -v -k distance`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add thermal_inspection/gui/main_window.py tests/unit/test_main_window_panel_lifecycle.py
git commit -m "feat: main_window forwards spot-meter distance to MeasurementPoint"
```

---

### Task 4: `app.py`'s spot-meter loop computes and emits `distance_m`

**Files:**
- Modify: `thermal_inspection/app.py:2372-2419` (the spot-meter update block)
- Test: `tests/unit/test_core_managers.py` or a new `tests/unit/test_spot_meter_app_distance.py` — use whichever existing test file already constructs a minimal `ThermalInspectionApp`-like harness with a fake camera (check `tests/unit/test_core_managers.py` first for a reusable fixture; if none fits cleanly, create the new file using the same duck-typed-fake style as `tests/unit/test_realsense_camera.py`)

**Interfaces:**
- Consumes: `MIN_VALID_DEPTH_M`, `MAX_VALID_DEPTH_M` from `thermal_inspection/processing/parallax_compensator.py`; `self.rgb_camera.backend.get_depth_frame(resize_to=(w, h))` (only present on `RGBCameraRealSense`).
- Produces: `spot_values` dicts gain an optional `'distance_m'` key, consumed by Task 3.

- [ ] **Step 1: Write the failing test**

This test exercises the logic in isolation rather than the full app loop (which needs a running Qt event loop and real camera plumbing) — extract the distance computation into a small standalone function first so it's directly testable:

```python
def test_spot_distance_reads_depth_at_point():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            import numpy as np
            w, h = resize_to
            depth = np.full((h, w), 1.5, dtype=np.float32)
            return depth

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result == pytest.approx(1.5)


def test_spot_distance_none_when_out_of_range():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            import numpy as np
            w, h = resize_to
            return np.full((h, w), 50.0, dtype=np.float32)  # beyond MAX_VALID_DEPTH_M

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result is None


def test_spot_distance_none_when_no_depth_frame():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            return None

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=5, point_y=5, thermal_w=10, thermal_h=10)
    assert result is None


def test_spot_distance_none_when_point_out_of_bounds():
    from thermal_inspection.app import _compute_spot_distance_m

    class FakeRealSenseBackend:
        def get_depth_frame(self, resize_to=None):
            import numpy as np
            w, h = resize_to
            return np.full((h, w), 1.5, dtype=np.float32)

    result = _compute_spot_distance_m(FakeRealSenseBackend(), point_x=99, point_y=99, thermal_w=10, thermal_h=10)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_spot_meter_app_distance.py -v`
Expected: FAIL — `ImportError: cannot import name '_compute_spot_distance_m'`

- [ ] **Step 3: Implement**

Add a module-level helper near the top of `thermal_inspection/app.py` (alongside other module-level helpers — check the imports section for where `MIN_VALID_DEPTH_M`/`MAX_VALID_DEPTH_M` would need importing from `thermal_inspection.processing.parallax_compensator`):

```python
def _compute_spot_distance_m(rs_backend, point_x: int, point_y: int,
                              thermal_w: int, thermal_h: int) -> Optional[float]:
    """
    Real depth-camera distance (meters) at a thermal-frame point, or None if
    unavailable/out of range.

    This is a resize-only lookup - RealSense depth is resized to thermal's
    resolution (RGBCameraRealSense.get_depth_frame's own resize_to param, on
    the small raw array before the float32 conversion, same as every other
    call site) with no parallax shift/zoom correction applied. Full
    alignment-corrected distance would need parallax_compensator.apply_correction()
    to run unconditionally regardless of view mode - an added per-frame cost
    this rough reading doesn't need to pay. Known limitation, not a bug: at
    typical mounting offsets this can be off by a handful of pixels.
    """
    if not (0 <= point_x < thermal_w and 0 <= point_y < thermal_h):
        return None
    depth_map = rs_backend.get_depth_frame(resize_to=(thermal_w, thermal_h))
    if depth_map is None:
        return None
    d = float(depth_map[point_y, point_x])
    if not (MIN_VALID_DEPTH_M <= d <= MAX_VALID_DEPTH_M):
        return None
    return d
```

Add the import at the top of `app.py`:

```python
from thermal_inspection.processing.parallax_compensator import MIN_VALID_DEPTH_M
from thermal_inspection.processing.fusion_3d_panel import MAX_VALID_DEPTH_M
```

(Check actual current import locations for these two constants before adding — `MIN_VALID_DEPTH_M` is defined in `parallax_compensator.py`, `MAX_VALID_DEPTH_M` in `fusion_3d_panel.py`, per the earlier grep in this session; import both from wherever they're actually defined, not re-declared.)

In the spot-meter loop (~line 2372-2419), inside the `for point in self.gui.measurement_points:` loop, after `temp` is resolved and before appending to `spot_values`:

```python
                        distance_m = None
                        if (cam and hasattr(cam, 'get_depth_frame')
                                and self._last_thermal_frame is not None):
                            th, tw = self._last_thermal_frame.shape[:2]
                            distance_m = _compute_spot_distance_m(cam, point.x, point.y, tw, th)

                        if temp is not None:
                            # Use radiometric unit symbol if available
                            if self.radiometric_controller and cam and hasattr(cam, 'is_radiometric_capable') and cam.is_radiometric_capable():
                                unit = self.radiometric_controller.get_unit_symbol()
                            spot_values.append({
                                'label': point.label,
                                'temperature': temp,
                                'unit': unit,
                                'distance_m': distance_m
                            })
```

Note: `cam` here is `self.thermal_camera` per the existing loop (line ~2378) — check whether the RealSense backend is actually reachable as `self.thermal_camera` or needs to come from `self.rgb_camera`/`plugin_host.get_active_camera('rgb')` instead (RealSense is wired as the **rgb**-role camera per this session's own earlier live testing, e.g. "Activating camera plugin 'intel_realsense' for role 'rgb'"). Use the same `active_rgb = self.plugin_host.get_active_camera('rgb') if self.plugin_host else None` pattern already used at `app.py:1681-1684` for `_rs_backend`, not `self.thermal_camera` — RealSense is never the thermal-role camera in this app.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_spot_meter_app_distance.py -v`
Expected: PASS

- [ ] **Step 5: Run the full existing spot-meter test suite to confirm no regression**

Run: `pytest tests/unit -k spot_meter -v`
Expected: all PASS (temperature-only behavior unchanged when no RealSense camera is present)

- [ ] **Step 6: Commit**

```bash
git add thermal_inspection/app.py tests/unit/test_spot_meter_app_distance.py
git commit -m "feat: spot meter reports distance-to-point when RealSense is active"
```

---

### Task 5: Manual live-hardware verification (required before calling this done)

Not a code task — a verification gate, per this session's own established practice (see the L515 pyrealsense2 integration itself, done live-hardware-verified before being called working).

- [ ] Launch the app with an L515 or D455 connected as the active RGB camera.
- [ ] Place a spot meter, confirm the list shows `@ X.XXm` alongside temperature.
- [ ] Move the camera/target closer and farther, confirm the distance updates sensibly.
- [ ] Switch to a view mode other than Fusion/3D Fusion (e.g. RGB Only or Thermal Only), confirm distance still shows (per the "always-on, any view mode" requirement).
- [ ] Disconnect RealSense (or test with only a webcam/Firefly as RGB), confirm distance silently omits (no crash, no stale value) and temperature-only behavior is unaffected.
- [ ] Report results back before this plan is considered complete — do not mark it done from unit tests alone.
