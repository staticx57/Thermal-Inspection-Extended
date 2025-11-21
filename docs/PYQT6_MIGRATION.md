# PyQt6 Migration Plan

## Current Status
- **Current**: PyQt5
- **Target**: PyQt6
- **File**: `inspection_gui_qt.py` (40KB)

## Why PyQt6?
- **Active development** (PyQt5 in maintenance mode)
- **Better Python 3.10+ support**
- **Modern Qt 6 features**
- **Long-term stability**

---

## Breaking Changes (PyQt5 → PyQt6)

### 1. Namespace Reorganization
**PyQt5**:
```python
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPainter
```

**PyQt6**:
```python
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPainter
```

**Change**: Replace `PyQt5` → `PyQt6` in all imports

---

### 2. Enum Value Access
**PyQt5**:
```python
Qt.AlignCenter
Qt.KeepAspectRatio
QImage.Format_RGB888
```

**PyQt6**:
```python
Qt.AlignmentFlag.AlignCenter
Qt.AspectRatioMode.KeepAspectRatio
QImage.Format.Format_RGB888
```

**Change**: Enums now use proper enum syntax

---

### 3. exec() Method Renamed
**PyQt5**:
```python
app = QApplication(sys.argv)
sys.exit(app.exec_())
```

**PyQt6**:
```python
app = QApplication(sys.argv)
sys.exit(app.exec())
```

**Change**: `exec_()` → `exec()`

---

### 4. Signal/Slot Syntax
**PyQt5**:
```python
button.clicked.connect(self.on_click)
# Overloaded signals:
spinbox.valueChanged[int].connect(handler)
```

**PyQt6**:
```python
button.clicked.connect(self.on_click)
# Overloaded signals use explicit typing:
spinbox.valueChanged.connect(handler)
```

**Change**: Simplified signal syntax

---

## Migration Steps

### Step 1: Update requirements_qt.txt
```diff
-PyQt5
+PyQt6
```

### Step 2: Update imports in inspection_gui_qt.py
```bash
# Find all PyQt5 imports
grep -n "from PyQt5" inspection_gui_qt.py

# Replace globally
sed -i 's/from PyQt5/from PyQt6/g' inspection_gui_qt.py
```

### Step 3: Fix Enum Access
**Common changes needed**:
```python
# Alignment
Qt.AlignCenter → Qt.AlignmentFlag.AlignCenter
Qt.AlignLeft → Qt.AlignmentFlag.AlignLeft
Qt.AlignRight → Qt.AlignmentFlag.AlignRight

# Aspect ratio
Qt.KeepAspectRatio → Qt.AspectRatioMode.KeepAspectRatio
Qt.IgnoreAspectRatio → Qt.AspectRatioMode.IgnoreAspectRatio

# Image format
QImage.Format_RGB888 → QImage.Format.Format_RGB888
QImage.Format_ARGB32 → QImage.Format.Format_ARGB32

# Window flags
Qt.WindowStaysOnTopHint → Qt.WindowType.WindowStaysOnTopHint

# Pen/Brush
Qt.SolidLine → Qt.PenStyle.SolidLine
Qt.NoPen → Qt.PenStyle.NoPen
```

### Step 4: Fix exec_() calls
```python
# In main block (if exists)
app.exec_() → app.exec()
```

### Step 5: Test All Features
See testing checklist below.

---

## Estimated Effort

| Task | Time | Difficulty |
|------|------|-----------|
| Update imports | 10 min | Easy |
| Fix enum access | 1 hour | Medium |
| Fix exec() calls | 5 min | Easy |
| Testing | 1 hour | Medium |
| Bug fixes | 30 min | Medium |
| **Total** | **~2-3 hours** | **Medium** |

---

## Testing Checklist

### Basic GUI Tests
- [ ] Application starts without errors
- [ ] Main window displays correctly
- [ ] Video widget renders frames
- [ ] Overlay widget draws ROIs

### Controls Tests
- [ ] All buttons clickable
- [ ] Dropdown menus work
- [ ] Sliders respond correctly
- [ ] Checkboxes toggle

### Theme Tests
- [ ] Dark theme renders correctly
- [ ] Light theme renders correctly
- [ ] Theme switching works

### ROI Tools Tests
- [ ] ROI drawing works
- [ ] ROI selection works
- [ ] ROI list updates

### Recording Tests
- [ ] Recording button works
- [ ] Snapshot button works
- [ ] Progress indicators display

---

## Implementation Plan

### Option A: In-Place Migration (Recommended)
1. Create backup: `cp inspection_gui_qt.py inspection_gui_qt_pyqt5_backup.py`
2. Update requirements: `pip install PyQt6`
3. Modify `inspection_gui_qt.py` in place
4. Test thoroughly
5. If issues: `cp inspection_gui_qt_pyqt5_backup.py inspection_gui_qt.py`

### Option B: Parallel Implementation
1. Keep `inspection_gui_qt.py` (PyQt5)
2. Create `inspection_gui_qt6.py` (PyQt6)
3. Test PyQt6 version
4. When stable, replace PyQt5 version
5. Delete old file

**Recommendation**: Option A (simpler, less code duplication)

---

## Potential Issues & Solutions

### Issue 1: Missing PyQt6 Modules
**Problem**: Some PyQt5 modules might not exist in PyQt6
**Solution**: Check [PyQt6 docs](https://www.riverbankcomputing.com/static/Docs/PyQt6/) for equivalents

### Issue 2: Third-Party Dependencies
**Problem**: Some libraries might require PyQt5
**Solution**: Check compatibility or find PyQt6 alternatives

### Issue 3: Performance Differences
**Problem**: PyQt6 might have different performance characteristics
**Solution**: Profile and optimize if needed

---

## Rollback Plan

If migration fails:
```bash
# Restore backup
cp inspection_gui_qt_pyqt5_backup.py inspection_gui_qt.py

# Reinstall PyQt5
pip uninstall PyQt6
pip install PyQt5

# Test application
python inspection_main.py
```

---

## References

- [PyQt6 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- [PyQt5 to PyQt6 Migration Guide](https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html)
- [Qt 6 Changes](https://doc.qt.io/qt-6/portingguide.html)

---

## Task Tracking

Add to `task.md`:
```markdown
## GUI Migration to PyQt6
- [ ] Backup inspection_gui_qt.py
- [ ] Update requirements_qt.txt (PyQt5 → PyQt6)
- [ ] Install PyQt6: `pip install PyQt6`
- [ ] Update imports (PyQt5 → PyQt6)
- [ ] Fix enum access (Qt.X → Qt.EnumType.X)
- [ ] Fix exec_() → exec()
- [ ] Test basic GUI functionality
- [ ] Test all controls
- [ ] Test themes
- [ ] Test ROI tools
- [ ] Fix any bugs found
- [ ] Delete backup if successful
```

---

**Status**: Planning complete, ready to execute
**Priority**: Medium (current PyQt5 works, but PyQt6 is better long-term)
**Risk**: Low (easy rollback, well-documented migration)
