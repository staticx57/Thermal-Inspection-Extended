# Remaining Features Implementation Plan

## Summary of Completed Work
✅ Phase 1 Performance Optimizations - **30+ FPS achieved**
✅ Manual Threshold Detection Feature - **Fully integrated**
✅ Parallel Processing - **Detection tasks, ROI analysis, motion/edge**
✅ Manual Threshold Crash Fix - **Handler methods corrected**

---

## Remaining Features to Implement

### 1. ROI Multi-Select Functionality
**Status**: Not implemented
**Priority**: High
**Complexity**: Medium

**Requirements**:
- Allow users to select multiple ROIs simultaneously (Ctrl+Click, Shift+Click)
- Show visual feedback for selected ROIs (different border color/style)
- Enable batch operations on selected ROIs:
  - Delete multiple ROIs at once
  - Set palette for multiple ROIs
  - Move/resize multiple ROIs together (stretch goal)

**Implementation Steps**:
1. Update `ROIOverlay` class in `inspection_gui_qt.py` to track multiple selections
2. Add `selected_rois: Set[str]` to track selected ROI IDs
3. Modify `mousePressEvent()` to handle Ctrl/Shift modifiers
4. Update `draw_rois()` to show different visual style for selected ROIs
5. Add context menu with batch operations
6. Update AnalysisPanel to show stats for all selected ROIs

**Files to Modify**:
- `inspection_gui_qt.py` - ROIOverlay class (~lines 546-950)
- `roi_manager.py` - Add multi-select support methods

---

### 2. Per-ROI Palette Setting
**Status**: Partially implemented (infrastructure exists, GUI missing)
**Priority**: High
**Complexity**: Low-Medium

**Current State**:
- `palette_manager.py` already supports per-ROI palettes
- Method `set_roi_palette(roi_id, palette_type)` exists
- Missing: GUI controls to set palette per ROI

**Implementation Steps**:
1. Add "Set Palette" option to ROI context menu
2. Create palette picker dialog/dropdown
3. Wire palette selection to `palette_manager.set_roi_palette()`
4. Add visual indicator showing ROI has custom palette
5. Show current palette in AnalysisPanel ROI list

**Files to Modify**:
- `inspection_gui_qt.py` - Add palette picker UI
- Connect to existing `palette_manager` infrastructure

**Code Location**:
- Palette manager already has `apply_composite_palette()` - inspection_main.py:631
- Need GUI hook in ROI context menu or AnalysisPanel

---

### 3. Finish Recording Option Implementation
**Status**: Partially implemented (backend exists, GUI incomplete)
**Priority**: Medium
**Complexity**: Low

**Current State**:
- `VideoRecorder` class exists and works (`video_recorder.py`)
- Recording start/stop logic in `inspection_main.py:950-973`
- Control panel has record button (`inspection_gui_qt.py:1187`)
- Issue: Recording state not properly synced with GUI

**Implementation Steps**:
1. Fix recording button toggle state synchronization
2. Add visual indicator when recording (red dot, status text)
3. Show recording duration/frame count
4. Add file path display/configuration
5. Test recording with various view modes

**Files to Modify**:
- `inspection_gui_qt.py` - Update ControlPanel record button visual feedback
- `inspection_main.py` - Ensure proper state updates

**Current Issues to Fix**:
```python
# In inspection_main.py:950-973
# Recording logic exists but GUI feedback incomplete

# Add to GUI:
- Recording indicator (blinking red dot)
- Recording duration timer
- File save path display
- Frame count display
```

---

## Implementation Priority

### Phase 1 (Today):
1. ✅ Fix manual threshold crash
2. Per-ROI palette setting (GUI only, backend exists)
3. Recording visual feedback improvements

### Phase 2 (Next session):
4. ROI multi-select functionality

---

## Detailed Implementation: Per-ROI Palette Setting

### Step 1: Add Context Menu to ROI Overlay

**Location**: `inspection_gui_qt.py` - ROIOverlay class

```python
class ROIOverlay(QWidget):
    # ... existing code ...

    def contextMenuEvent(self, event):
        """Show context menu on right-click."""
        if not self.selected_roi:
            return

        menu = QMenu(self)

        # Palette submenu
        palette_menu = menu.addMenu("Set Palette")

        # Add all available palettes
        palettes = [
            "white_hot", "black_hot", "ironbow", "rainbow",
            "lava", "arctic", "medical", "plasma", "amber"
        ]

        for palette in palettes:
            action = palette_menu.addAction(palette.replace("_", " ").title())
            action.triggered.connect(lambda checked, p=palette: self._set_roi_palette(p))

        # Clear palette option
        clear_action = menu.addAction("Clear Custom Palette")
        clear_action.triggered.connect(self._clear_roi_palette)

        menu.addSeparator()

        # Delete ROI option
        delete_action = menu.addAction("Delete ROI")
        delete_action.triggered.connect(self._delete_selected_roi)

        menu.exec(event.globalPos())

    def _set_roi_palette(self, palette_name: str):
        """Set palette for selected ROI."""
        if self.selected_roi and self.parent_window:
            roi_id = self.selected_roi.roi_id
            # Call main window handler
            self.parent_window._on_roi_palette_changed(roi_id, palette_name)

    def _clear_roi_palette(self):
        """Clear custom palette for selected ROI."""
        if self.selected_roi and self.parent_window:
            roi_id = self.selected_roi.roi_id
            self.parent_window._on_roi_palette_cleared(roi_id)

    def _delete_selected_roi(self):
        """Delete the currently selected ROI."""
        if self.selected_roi:
            self.roi_deleted.emit(self.selected_roi.roi_id)
```

### Step 2: Add Main Window Handlers

**Location**: `inspection_gui_qt.py` - InspectionAppWindow class

```python
def _on_roi_palette_changed(self, roi_id: str, palette_name: str):
    """Handle ROI palette change."""
    if self.app and hasattr(self.app, 'palette_manager'):
        from palette_manager import PaletteType
        # Convert string to PaletteType enum
        palette_type = PaletteType[palette_name.upper()]
        self.app.palette_manager.set_roi_palette(roi_id, palette_type)
        logger.info(f"ROI {roi_id} palette set to: {palette_name}")

def _on_roi_palette_cleared(self, roi_id: str):
    """Handle ROI palette clear."""
    if self.app and hasattr(self.app, 'palette_manager'):
        self.app.palette_manager.clear_roi_palette(roi_id)
        logger.info(f"ROI {roi_id} palette cleared (using global)")
```

---

## Detailed Implementation: Recording Visual Feedback

### Step 1: Add Recording Indicator to Info Panel

**Location**: `inspection_gui_qt.py` - InfoPanel class

```python
class InfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # ... existing code ...

        # Add recording indicator
        self.recording_label = QLabel()
        self.recording_label.setStyleSheet(
            "QLabel { color: red; font-weight: bold; font-size: 14px; }"
        )
        self.recording_label.setVisible(False)
        layout.addWidget(self.recording_label)

        # Recording timer
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self._update_recording_time)
        self.recording_start_time = None

    def set_recording(self, recording: bool, filename: str = ""):
        """Update recording indicator."""
        self.recording_label.setVisible(recording)
        if recording:
            self.recording_start_time = time.time()
            self.recording_timer.start(1000)  # Update every second
            self.recording_label.setText(f"⏺ RECORDING: {filename}")
        else:
            self.recording_timer.stop()
            self.recording_label.setText("")

    def _update_recording_time(self):
        """Update recording duration display."""
        if self.recording_start_time:
            duration = int(time.time() - self.recording_start_time)
            mins, secs = divmod(duration, 60)
            hours, mins = divmod(mins, 60)
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

            # Get current filename
            current_text = self.recording_label.text()
            filename = current_text.split(": ")[1] if ": " in current_text else ""
            self.recording_label.setText(f"⏺ RECORDING [{time_str}]: {filename}")
```

### Step 2: Wire Recording State to GUI

**Location**: `inspection_main.py` - Recording handlers

```python
def _on_record_toggle(self, enabled: bool):
    """Toggle recording."""
    self.recording_enabled = enabled

    # Update GUI state
    if self.gui_type == 'qt' and self.gui:
        if enabled:
            # Get next recording filename
            filename = self.video_recorder.get_next_filename()
            self.gui.info_panel.set_recording(True, filename)
        else:
            self.gui.info_panel.set_recording(False)

    logger.info(f"Recording: {'ON' if enabled else 'OFF'}")
```

---

## Testing Checklist

### Per-ROI Palette:
- [ ] Right-click ROI shows context menu
- [ ] Selecting palette applies to that ROI only
- [ ] Clearing palette reverts to global
- [ ] Works with multiple ROIs with different palettes
- [ ] Palette persists when saving/loading ROIs

### Recording:
- [ ] Recording indicator appears when recording starts
- [ ] Duration timer updates every second
- [ ] Indicator disappears when recording stops
- [ ] Works across different view modes
- [ ] File is saved to correct location

### Multi-Select (Future):
- [ ] Ctrl+Click selects/deselects ROIs
- [ ] Shift+Click selects range
- [ ] Selected ROIs show different visual style
- [ ] Delete works on multiple selected ROIs
- [ ] Set palette works on multiple selected ROIs

---

## Notes
- All backend infrastructure for these features already exists
- Main work is GUI wiring and visual feedback
- Manual threshold crash is now fixed
- Performance optimizations are complete and working at 30+ FPS
