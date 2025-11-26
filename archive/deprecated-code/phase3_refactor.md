# Phase 3 Refactoring Plan

## Current Architecture (Phase 2)
```python
def run(self):
    while self.running:
        # Process frame
        loop_start = time.time()
        # ... 250 lines of processing ...
        self.qt_app.processEvents()  # BAD: processEvents in loop
        time.sleep(0.001)
```

## Phase 3 Architecture (QTimer)
```python
def process_frame(self):
    # All frame processing logic (extracted from while loop)
    loop_start = time.time()
    # ... processing ...

def run(self):
    if self.gui_type == 'qt':
        # Setup QTimer
        self.frame_timer = QTimer()
        self.frame_timer.timeout.connect(self.process_frame)
        self.frame_timer.start(16)  # 60 FPS
        # Run Qt event loop
        self.qt_app.exec_()
    else:
        # OpenCV: keep while loop
        while self.running:
            self.process_frame()
```

## Changes Needed

1. Extract lines 667-920 from while loop → new `process_frame()` method
2. Remove `loop_start = time.time()` line (move to process_frame)
3. In `run()`:
   - For Qt: Setup QTimer + call exec_()
   - For OpenCV: Call process_frame() in while loop
4. Remove processEvents() and time.sleep() from process_frame() for Qt path

## Benefits
- Proper Qt architecture (no processEvents)
- Event loop runs naturally
- Better performance
- More responsive GUI
- Follows Qt best practices
