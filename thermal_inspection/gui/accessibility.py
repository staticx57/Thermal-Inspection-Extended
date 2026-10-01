"""
Accessibility and discoverability passes that run over finished widget trees:

  * apply_tooltips(root)          fills in tooltips for controls that had none (a table per panel class, so the panels'
                                  own construction code stays untouched); never overwrites an existing tooltip.
  * apply_accessible_names(root)  gives every interactive control an accessible name (what screen readers announce and
                                  UI-automation tools find): its own text, else the label sitting in front of it in the
                                  same row, else its tooltip.

Both are idempotent and cheap, and are re-run on a panel when it is swapped in at camera connect time.
"""
import re

from PyQt6.QtWidgets import (QAbstractButton, QAbstractItemView, QAbstractSpinBox, QComboBox, QFormLayout, QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QSlider, QTableWidget, QVBoxLayout,
                             QWidget)

# {panel class name: {attribute name: tooltip}}
TOOLTIPS = {
    "ROITemperaturePanel": {
        "rename_btn": "Rename the selected ROI",
        "lock_btn": "Lock the selected ROI so it cannot be moved or resized by accident",
        "visible_btn": "Hide or show the selected ROI on the video (it keeps measuring while hidden)",
        "duplicate_btn": "Make a copy of the selected ROI",
        "alert_btn": "Set a temperature alert on the selected ROI (above / below a threshold)",
        "roi_delete_btn": "Delete the selected ROI",
        "roi_delete_all_btn": "Delete every ROI",
        "graph_check": "Plot the selected ROI's temperature over time",
        "graph_metric": "Which statistic the history graph plots",
        "clear_btn": "Clear the recorded history of the selected ROI",
        "save_set_btn": "Save all ROIs to a file so the same layout can be reloaded",
        "load_set_btn": "Load a saved set of ROIs",
        "export_btn": "Export the ROI statistics to a file",
    },
    "ROIAlertDialog": {
        "metric": "Which ROI statistic the alert watches",
        "kind": "Trigger when the value rises above, or falls below, the threshold",
        "threshold": "The temperature that triggers the alert (in the app's temperature unit)",
        "sound": "Play a beep when the alert triggers",
        "enabled": "Switch this alert on or off without deleting it",
    },
    "IsothermPanel": {
        "enable_check": "Highlight pixels inside a temperature band in a solid colour",
        "mode_combo": "Which pixels are highlighted: above, below, inside or outside the thresholds",
        "low_spinbox": "Lower temperature threshold",
        "high_spinbox": "Upper temperature threshold",
        "color_combo": "Highlight colour",
        "hotspot_btn": "Preset: highlight everything above the hot threshold",
        "coldspot_btn": "Preset: highlight everything below the cold threshold",
        "normal_btn": "Preset: highlight the comfortable/normal band",
        "multiband_cb": "Use several highlight bands at once, each with its own colour",
        "add_band_btn": "Add a band using the current thresholds and colour",
        "remove_band_btn": "Remove the selected band",
    },
    "MappingFusionPanel": {
        "_start_button": "Start building a 3D map of the scene (needs a RealSense depth camera)",
        "_finish_button": "Stop scanning and freeze the map so it can be inspected and saved",
        "_reset_button": "Throw the current map away and start empty",
        "_save_button": "Save the map, including temperatures, to a file",
        "_load_button": "Load a previously saved map",
        "_texture_source_combo": "What colours the 3D points: thermal, RGB, or a blend of both",
        "_view_mode_combo": "What to display: texture colour, live temperature, peak temperature or change",
    },
    "GigEControlPanel": {
        "btn_scan": "Broadcast on the network (GVCP, UDP 3956) to find GigE Vision cameras",
        "cam_combo": "The cameras that answered the scan",
        "txt_ip": "IP address to give the selected camera",
        "txt_subnet": "Subnet mask to give the selected camera",
        "txt_gateway": "Gateway to give the selected camera",
        "btn_force_ip": "Send the address above to the camera (ForceIP): use when it is on another subnet",
        "spin_exposure": "Exposure time in microseconds",
        "spin_gain": "Sensor gain in dB",
        "combo_mtu": "Packet size: larger (jumbo) packets need a network adapter that supports them",
        "chk_trigger": "Capture a frame only when a software trigger is fired",
        "btn_fire_trigger": "Capture one frame now (software trigger mode)",
    },
    "CameraManagerDialog": {
        "_thermal_spin": "Device index of the thermal camera",
        "_rgb_spin": "Device index of the RGB camera",
        "_manual_apply_btn": "Use the device indices entered above",
        "_detect_btn": "Scan for cameras again",
        "_apply_btn": "Apply the thermal / RGB roles chosen in the list",
        "_swap_btn": "Swap which device is thermal and which is RGB",
    },
}


def apply_tooltips(root: QWidget) -> int:
    """Fill in missing tooltips for the panels in TOOLTIPS found at or below `root`. Returns how many were set."""
    done = 0
    candidates = [root] + root.findChildren(QWidget)
    for w in candidates:
        table = TOOLTIPS.get(type(w).__name__)
        if not table:
            continue
        for attr, tip in table.items():
            target = getattr(w, attr, None)
            if isinstance(target, QWidget) and not target.toolTip():
                target.setToolTip(tip)
                done += 1
    return done


_NON_WORD_EDGES = re.compile(r"^[^\w]+|[^\w\)\.]+$", re.UNICODE)


def _clean(text: str) -> str:
    """Button text without accelerator ampersands and leading emoji/symbols ('🔍 Auto ROI' -> 'Auto ROI')."""
    text = (text or "").replace("&&", "\0").replace("&", "").replace("\0", "&")
    return _NON_WORD_EDGES.sub("", text).strip()


def _group_title(widget: QWidget) -> str:
    p = widget.parentWidget()
    while p is not None:
        if isinstance(p, QGroupBox) and p.title():
            return _clean(p.title())
        p = p.parentWidget()
    return ""


_KIND = ((QComboBox, "selector"), (QSlider, "slider"), (QAbstractItemView, "list"), (QLineEdit, "field"),
         (QAbstractSpinBox, "value"), (QAbstractButton, "button"))


def _label_before(widget: QWidget):
    """The QLabel that precedes `widget` in its row (HBox / Grid), or None."""
    parent = widget.parentWidget()
    if parent is None or parent.layout() is None:
        return None

    def walk(layout):
        if isinstance(layout, QGridLayout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item.widget() is widget:
                    r, c, _, _ = layout.getItemPosition(i)
                    for j in range(layout.count()):
                        other = layout.itemAt(j)
                        r2, c2, _, _ = layout.getItemPosition(j)
                        if r2 == r and c2 < c and isinstance(other.widget(), QLabel) and other.widget().text():
                            return other.widget()
                    return None
        elif isinstance(layout, (QHBoxLayout, QVBoxLayout)):
            prev = None                      # the widget immediately before this one: a label only counts if adjacent
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item.widget() is widget:
                    return prev if isinstance(prev, QLabel) and prev.text() else None
                prev = item.widget() if item.widget() is not None else prev
        for i in range(layout.count()):
            sub = layout.itemAt(i).layout()
            if sub is not None:
                found = walk(sub)
                if found is not None:
                    return found
        return None

    return walk(parent.layout())


INTERACTIVE = (QAbstractButton, QComboBox, QAbstractSpinBox, QSlider, QLineEdit, QListWidget, QTableWidget)


def apply_accessible_names(root: QWidget) -> int:
    """Give every interactive control under `root` an accessible name when it has none. Returns how many were named."""
    named = 0
    for w in root.findChildren(QWidget):
        if not isinstance(w, INTERACTIVE) or w.accessibleName():
            continue
        if isinstance(w, QAbstractButton) and isinstance(w.parentWidget(), QAbstractItemView):
            continue                       # a table's select-all corner button: internal, not a control
        # skip the internal line edit of an editable combo / spin box: the owner carries the name
        if isinstance(w, QLineEdit) and isinstance(w.parentWidget(), (QComboBox, QAbstractSpinBox)):
            continue
        name = ""
        if isinstance(w, QAbstractButton):
            name = _clean(w.text())
        if not name:
            label = _label_before(w)
            if label is not None:
                name = _clean(label.text()).rstrip(":")
        if not name:
            name = (w.toolTip() or "").split("\n")[0].strip()
        if not name:
            name = _clean(w.objectName().replace("_", " "))
        if not name:
            title = _group_title(w)
            if title:
                kind = next((k for cls, k in _KIND if isinstance(w, cls)), "control")
                name = f"{title} {kind}"
        if name:
            w.setAccessibleName(name)
            named += 1
    return named
