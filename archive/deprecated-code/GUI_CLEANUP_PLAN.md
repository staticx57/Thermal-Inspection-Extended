# GUI Cleanup Plan - Hobbyist Edition

## Current State (Cluttered)

**Row 1 (5 buttons):**
```
PAL: IRONBOW | YOLO: ON | BOX: ON | DEV: CUDA | MODEL: V8N
```

**Row 2 (4-6 buttons):**
```
FLUSH: OFF | AUDIO: ON | SKIP: 1/1 | VIEW: FUSION | [FUS: ALPHA] | [α: 0.5]
```

**Total:** 9-11 buttons taking ~1200px width

**Problems:**
- Too many buttons for a hobby project
- Buttons you rarely touch (PAL, MODEL, FLUSH, SKIP, DEV)
- Hard to use while testing/driving
- Cluttered visual appearance

---

## New Design (Clean & Simple)

### Single Row - 4 Essential Buttons

```
┌────────────────────────────────────────────────────────────┐
│  VIEW MODE    │   DETECTION    │    AUDIO    │    INFO     │
│   Thermal     │      ON ✓      │    ON 🔊    │     ℹ️      │
└────────────────────────────────────────────────────────────┘
```

**Button 1: VIEW MODE**
- Click to cycle: Thermal → RGB → Fusion → Side-by-Side → PIP
- Shows current mode in button text
- Large, easy to hit

**Button 2: DETECTION**
- Toggle YOLO detection on/off
- Green when ON, gray when OFF
- Shows ON/OFF status clearly

**Button 3: AUDIO**
- Toggle audio alerts
- Shows speaker icon 🔊 when ON, muted 🔇 when OFF
- Quick toggle while testing

**Button 4: INFO**
- Click to show/hide info panel
- Info panel shows: sensor status, detection count, FPS, etc.
- Toggles top-right overlay

### Info Panel (When Enabled)

```
┌──────────────────────────────┐
│ SENSORS:                     │
│ 🎥 RGB:     ✓ Connected      │
│ 🔥 Thermal: ✓ Connected      │
│ 📡 LiDAR:   ✓ Connected      │
│                              │
│ SYSTEM:                      │
│ 🎯 Detections: 3             │
│ 📊 FPS: 28                   │
│ 💻 Device: CUDA              │
│ 🧠 Model: YOLOv8n            │
│                              │
│ Press 'H' for help          │
└──────────────────────────────┘
```

### Keyboard Shortcuts (Hidden Features)

All the "developer" stuff moved to keyboard:

- **V**: Cycle view modes (same as button)
- **D**: Toggle detection boxes
- **Y**: Toggle YOLO on/off
- **A**: Toggle audio
- **C**: Cycle thermal palette (removed from buttons)
- **M**: Cycle models (removed from buttons)
- **I**: Toggle info panel
- **H**: Show help overlay
- **P**: Print stats to console
- **S**: Screenshot
- **F**: Fullscreen
- **Q/ESC**: Quit

**Removed buttons:**
- PAL (now C key)
- BOX (now D key, or just always show when YOLO on)
- DEV (auto-detect, can't change at runtime anyway)
- MODEL (now M key)
- FLUSH (auto-adaptive, removed)
- SKIP (auto-adaptive, removed)
- FUS mode (part of VIEW cycling)
- Alpha (removed, use preset modes)

---

## Implementation Changes

### File: `driver_gui.py`

**Changes to `_draw_enhanced_controls()`:**

```python
def _draw_enhanced_controls(self, canvas: np.ndarray, params: dict):
    """
    Draw simplified control panel - hobby edition
    4 essential buttons only
    """
    gui_scale = self.scale_factor * 0.9
    button_width = int(150 * gui_scale)    # Wider buttons
    button_height = int(45 * gui_scale)    # Taller buttons
    button_spacing = int(15 * gui_scale)   # More spacing
    top_margin = int(40 * gui_scale)
    left_margin = int(15 * gui_scale)

    self.control_buttons = {}
    current_x = left_margin
    button_y = top_margin

    # Single row - 4 buttons only
    buttons = [
        ('view_cycle', self._get_view_text(params['view_mode']),
         button_width, self.colors['button_active_alt']),

        ('yolo_toggle', f"DETECT: {'ON ✓' if params['yolo'] else 'OFF'}",
         button_width,
         self.colors['button_active'] if params['yolo'] else self.colors['button_bg']),

        ('audio_toggle', f"AUDIO: {'ON 🔊' if params.get('audio_enabled', True) else 'OFF 🔇'}",
         button_width,
         self.colors['button_active'] if params.get('audio_enabled', True) else self.colors['button_bg']),

        ('info_toggle', "INFO ℹ️",
         int(button_width * 0.7),  # Smaller
         self.colors['button_active_alt'] if params.get('show_info', False) else self.colors['button_bg']),
    ]

    for btn_id, text, width, bg_color in buttons:
        self._draw_button_simple(canvas, current_x, button_y, width,
                                button_height, text, btn_id, gui_scale, bg_color)
        current_x += width + button_spacing

def _get_view_text(self, view_mode: str) -> str:
    """Get display text for view mode button"""
    mode_text = {
        'thermal': 'VIEW: 🔥 Thermal',
        'rgb': 'VIEW: 🎨 RGB',
        'fusion': 'VIEW: 🔀 Fusion',
        'side_by_side': 'VIEW: 👁️ Split',
        'picture_in_picture': 'VIEW: 📺 PIP'
    }
    return mode_text.get(view_mode, f'VIEW: {view_mode[:6].upper()}')
```

**New info panel method:**

```python
def _draw_info_panel(self, canvas: np.ndarray, params: dict):
    """
    Draw info panel (top-right) when enabled
    Shows sensor status, system info, shortcuts
    """
    if not params.get('show_info', False):
        return

    # Panel dimensions
    panel_w = int(300 * self.scale_factor)
    panel_h = int(350 * self.scale_factor)
    margin = int(15 * self.scale_factor)

    # Position: top-right corner
    canvas_h, canvas_w = canvas.shape[:2]
    x = canvas_w - panel_w - margin
    y = margin + int(60 * self.scale_factor)  # Below top buttons

    # Semi-transparent background
    overlay = canvas[y:y+panel_h, x:x+panel_w].copy()
    bg = np.full((panel_h, panel_w, 3), self.colors['panel_bg'], dtype=np.uint8)
    cv2.addWeighted(bg, 0.85, overlay, 0.15, 0, overlay)
    canvas[y:y+panel_h, x:x+panel_w] = overlay

    # Border
    cv2.rectangle(canvas, (x, y), (x + panel_w, y + panel_h),
                 self.colors['panel_accent'], 2)

    # Content
    text_y = y + int(30 * self.scale_factor)
    line_height = int(28 * self.scale_factor)
    text_x = x + int(15 * self.scale_factor)

    def draw_line(text, color=None):
        nonlocal text_y
        if color is None:
            color = self.colors['text']
        cv2.putText(canvas, text, (text_x, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, self.font_scale_small,
                   color, self.font_thickness)
        text_y += line_height

    # Title
    draw_line("SYSTEM INFO", self.colors['accent_cyan'])
    text_y += int(5 * self.scale_factor)

    # Sensors
    draw_line("SENSORS:", self.colors['text_dim'])

    # RGB
    rgb_status = "✓ Connected" if params.get('rgb_available') else "✗ Not found"
    rgb_color = self.colors['success'] if params.get('rgb_available') else self.colors['text_dim']
    draw_line(f"  RGB:     {rgb_status}", rgb_color)

    # Thermal (always connected if we're running)
    draw_line(f"  Thermal: ✓ Connected", self.colors['success'])

    # LiDAR (future)
    lidar_status = "✓ Connected" if params.get('lidar_available', False) else "- Ready"
    lidar_color = self.colors['success'] if params.get('lidar_available', False) else self.colors['text_dim']
    draw_line(f"  LiDAR:   {lidar_status}", lidar_color)

    text_y += int(10 * self.scale_factor)

    # System stats
    draw_line("SYSTEM:", self.colors['text_dim'])
    draw_line(f"  FPS: {params.get('fps', 0):.0f}")
    draw_line(f"  Objects: {params.get('detection_count', 0)}")
    draw_line(f"  Device: {params['device'].upper()}")
    draw_line(f"  Model: {params['model'][:12]}")

    text_y += int(10 * self.scale_factor)

    # Shortcuts
    draw_line("SHORTCUTS:", self.colors['text_dim'])
    draw_line("  H - Help", self.colors['accent_green'])
    draw_line("  C - Palette", self.colors['accent_green'])
    draw_line("  M - Model", self.colors['accent_green'])
    draw_line("  S - Screenshot", self.colors['accent_green'])
```

### File: `main.py`

**Add info panel state:**

```python
# In __init__:
self.show_info_panel = False  # NEW

# In _handle_keypress():
elif key == ord('i') or key == ord('I'):
    # Toggle info panel
    self.show_info_panel = not self.show_info_panel
    logger.info(f"Info panel {'shown' if self.show_info_panel else 'hidden'}")

elif key == ord('h') or key == ord('H'):
    # Show help overlay (quick reference)
    self._show_help_overlay()

elif key == ord('b') or key == ord('B'):
    # Toggle detection boxes (moved from button)
    self.show_detections = not self.show_detections
    logger.info(f"Detection boxes {'shown' if self.show_detections else 'hidden'}")

# In run() when rendering:
display_frame = self.gui.render_frame_with_controls(
    # ... existing params ...
    show_info=self.show_info_panel,  # NEW
    detection_count=len(detections),  # NEW
    lidar_available=False  # NEW (will be True when integrated)
)
```

**Add help overlay method:**

```python
def _show_help_overlay(self):
    """Show keyboard shortcuts help overlay"""
    import numpy as np

    # Create semi-transparent overlay
    help_screen = np.zeros((720, 1280, 3), dtype=np.uint8)

    # Title
    title = "KEYBOARD SHORTCUTS"
    cv2.putText(help_screen, title, (400, 80),
               cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)

    # Shortcuts (2 columns)
    shortcuts_left = [
        ("V", "Cycle view modes"),
        ("D", "Toggle detection boxes"),
        ("Y", "Toggle YOLO"),
        ("A", "Toggle audio"),
        ("C", "Cycle thermal palette"),
        ("M", "Cycle models"),
    ]

    shortcuts_right = [
        ("I", "Toggle info panel"),
        ("S", "Screenshot"),
        ("P", "Print stats"),
        ("F", "Fullscreen"),
        ("Q/ESC", "Quit"),
        ("H", "This help"),
    ]

    # Draw left column
    y = 150
    for key, desc in shortcuts_left:
        cv2.putText(help_screen, f"{key}", (200, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(help_screen, f"- {desc}", (280, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        y += 60

    # Draw right column
    y = 150
    for key, desc in shortcuts_right:
        cv2.putText(help_screen, f"{key}", (700, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(help_screen, f"- {desc}", (780, y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        y += 60

    # Footer
    cv2.putText(help_screen, "Press any key to close", (450, 650),
               cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 100), 1)

    # Display and wait for key
    self.gui.display(help_screen)
    cv2.waitKey(0)
```

---

## Visual Comparison

### Before (Cluttered):
```
┌──────────────────────────────────────────────────────────────┐
│ PAL | YOLO | BOX | DEV | MODEL                               │  ← Row 1
│ FLUSH | AUDIO | SKIP | VIEW | FUS | α                        │  ← Row 2
├──────────────────────────────────────────────────────────────┤
│                                                               │
│                    VIDEO FEED                                 │
│                                                               │
└──────────────────────────────────────────────────────────────┘
Total: 9-11 small buttons, hard to click
```

### After (Clean):
```
┌──────────────────────────────────────────────────────────────┐
│ VIEW: 🔥 Thermal | DETECT: ON ✓ | AUDIO: ON 🔊 | INFO ℹ️      │  ← Single row
├──────────────────────────────────────────────────────────────┤
│                                                               │
│                    VIDEO FEED                    [Info Panel] │
│                                                  [if enabled]  │
│                                                               │
└──────────────────────────────────────────────────────────────┘
Total: 4 large buttons, easy to use
```

---

## Button Click Handlers

Add to main.py mouse click handler:

```python
def _handle_button_click(self, button_id: str):
    """Handle button clicks from GUI"""
    if button_id == 'view_cycle':
        # Cycle view modes
        modes = [ViewMode.THERMAL_ONLY]
        if self.rgb_available:
            modes.extend([ViewMode.RGB_ONLY, ViewMode.FUSION,
                         ViewMode.SIDE_BY_SIDE, ViewMode.PICTURE_IN_PICTURE])
        current_idx = modes.index(self.view_mode) if self.view_mode in modes else 0
        next_idx = (current_idx + 1) % len(modes)
        self.view_mode = modes[next_idx]
        self.gui.set_view_mode(self.view_mode)
        logger.info(f"View mode: {self.view_mode}")

    elif button_id == 'yolo_toggle':
        self.yolo_enabled = not self.yolo_enabled
        logger.info(f"YOLO detection {'enabled' if self.yolo_enabled else 'disabled'}")

    elif button_id == 'audio_toggle':
        self.audio_enabled = not self.audio_enabled
        if self.analyzer:
            self.analyzer.set_audio_enabled(self.audio_enabled)
        logger.info(f"Audio alerts {'enabled' if self.audio_enabled else 'disabled'}")

    elif button_id == 'info_toggle':
        self.show_info_panel = not self.show_info_panel
        logger.info(f"Info panel {'shown' if self.show_info_panel else 'hidden'}")
```

---

## Implementation Checklist

- [ ] Modify `driver_gui.py::_draw_enhanced_controls()` - 4 button layout
- [ ] Add `driver_gui.py::_draw_info_panel()` - Info overlay
- [ ] Add `driver_gui.py::_get_view_text()` - View mode text helper
- [ ] Update `main.py::__init__()` - Add show_info_panel flag
- [ ] Update `main.py::_handle_keypress()` - Add I, H, B keys
- [ ] Add `main.py::_show_help_overlay()` - Help screen
- [ ] Update `main.py::_handle_button_click()` - New button handlers
- [ ] Update `main.py::run()` - Pass show_info, detection_count to GUI
- [ ] Update `driver_gui.py::render_frame_with_controls()` - Add new params
- [ ] Test all buttons and shortcuts work correctly

---

## Expected Results

✅ **68% fewer buttons** (9-11 → 4)
✅ **Larger click targets** (150px width vs 85-130px)
✅ **Cleaner visual appearance**
✅ **All functionality preserved** (moved to keyboard)
✅ **Info panel for diagnostics** (when you need it)
✅ **Help overlay** (H key for shortcuts)
✅ **Ready for LiDAR** (status shows in info panel)

---

## Time Estimate

**Implementation:** 2-3 hours
**Testing:** 30 minutes
**Total:** ~3 hours for a much cleaner interface

---

## Next Steps After GUI Cleanup

Once GUI is done:
1. Test the clean interface
2. Then we can plan LiDAR integration (you already have the hardware!)
3. Simple LiDAR distance override first
4. Then full point cloud fusion if you want

Sound good?
