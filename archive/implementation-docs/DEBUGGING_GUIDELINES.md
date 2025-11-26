# Debugging Guidelines for ThermalFusionDrivingAssist

## Core Principle
**If a feature is requested but doesn't work, it's BROKEN - not a "future state"**

When a user asks for help with a feature, assume:
1. The feature exists in the codebase
2. It's expected to work
3. If it doesn't work, something is broken and needs fixing

## Debugging Process

### 1. User Reports Issue
**ALWAYS assume the feature should work unless explicitly stated otherwise**

Example:
- User: "The 3x3 developer panel buttons aren't working"
- ❌ WRONG: "This feature isn't implemented yet"
- ✅ CORRECT: "Let me investigate why the buttons aren't functioning"

### 2. Investigate the Code
**Follow the complete signal/slot chain**

For GUI issues:
1. Check if UI elements exist
2. Check if signals are connected (`button.clicked.connect(...)`)
3. Check if signal handlers exist
4. Check if handlers are properly registered
5. Test the actual functionality

For detection/processing issues:
1. Check if feature is initialized
2. Check if feature is enabled
3. Check if data is flowing through
4. Check if there are errors in logs
5. Verify output is actually being produced

### 3. Verify Before Claiming Success
**NEVER claim something works without actual verification**

Required verifications:
- [ ] Code compiles/imports without errors
- [ ] Feature initializes correctly
- [ ] User-facing functionality actually responds
- [ ] Output/results are produced as expected
- [ ] No error messages in logs related to feature
- [ ] Test with actual user workflow (not just imports)

### 4. Testing Checklist

#### GUI Features
- [ ] Element is visible when it should be
- [ ] Element responds to clicks/interactions
- [ ] Signals are emitted
- [ ] Handlers are called
- [ ] State changes occur
- [ ] Visual feedback is provided
- [ ] No exceptions in logs

#### Processing Features
- [ ] Feature initializes successfully
- [ ] Input data is received
- [ ] Processing occurs
- [ ] Output is generated
- [ ] Results are displayed/stored
- [ ] Performance is acceptable
- [ ] No errors in processing pipeline

#### Cross-Platform Features
- [ ] Platform detection works
- [ ] Appropriate backend selected
- [ ] Fallbacks work if primary fails
- [ ] No platform-specific crashes
- [ ] Feature parity maintained
- [ ] Performance acceptable on target platform

### 5. Common Failure Patterns

#### Signal Not Connected
```python
# BROKEN: Button exists but does nothing
self.my_button = QPushButton("Click Me")

# FIXED: Signal connected
self.my_button = QPushButton("Click Me")
self.my_button.clicked.connect(self.handle_click)
```

#### Signal Connected But No Handler
```python
# BROKEN: Signal connected but no implementation
self.my_button.clicked.connect(self.handle_click)
# Missing: def handle_click(self): ...

# FIXED: Handler implemented
def handle_click(self):
    print("Button clicked")
    self.do_something()
```

#### Feature Initialized But Not Enabled
```python
# BROKEN: Feature exists but never activated
self.detector = Detector()
# Missing: self.detector.enable()

# FIXED: Feature properly activated
self.detector = Detector()
self.detector.enable()
self.detector.start()
```

#### Data Pipeline Broken
```python
# BROKEN: Data generated but not passed forward
result = self.process_data(input)
# Missing: self.send_to_display(result)

# FIXED: Complete pipeline
result = self.process_data(input)
self.send_to_display(result)
```

### 6. Debugging Workflow

```
1. Reproduce Issue
   ↓
2. Add Debug Logging
   ↓
3. Trace Execution Path
   ↓
4. Identify Break Point
   ↓
5. Fix Root Cause
   ↓
6. Verify Fix Works
   ↓
7. Test Edge Cases
   ↓
8. Clean Up Debug Code
   ↓
9. Document Fix
```

### 7. Log Analysis

**What to look for:**
- ✅ Feature initialized successfully
- ❌ Feature initialization failed
- ⚠️ Warnings about missing dependencies
- 🔧 Debug messages showing execution path
- ❌ Exception stack traces
- ⚠️ "Not implemented" or "TODO" messages

**Example Good Logging:**
```python
logger.info("Detector initialized successfully")
logger.debug(f"Processing frame {frame_id}")
logger.info(f"Found {len(detections)} objects")
```

**Example Problem Indicators:**
```python
logger.warning("Feature not available")
logger.error("Failed to initialize")
logger.debug("Handler not called")  # Should have been called
```

### 8. When to Ask for Clarification

Ask only when:
- Feature genuinely doesn't exist in codebase
- Multiple valid implementations possible
- Breaking change required
- Design decision needed

Don't ask when:
- Feature exists but broken
- Clear fix available
- Bug is obvious
- Standard implementation applies

### 9. Testing Standards

#### Before Claiming "Working"
1. ✅ Import test passes
2. ✅ Initialization succeeds
3. ✅ Feature activates
4. ✅ User interaction works
5. ✅ Output is generated
6. ✅ No errors in logs
7. ✅ Tested on target platform
8. ✅ Edge cases handled

#### Before Claiming "Fixed"
1. ✅ Original issue reproduced
2. ✅ Root cause identified
3. ✅ Fix implemented
4. ✅ Fix tested in isolation
5. ✅ Fix tested in full app
6. ✅ No regressions introduced
7. ✅ Edge cases work
8. ✅ Documentation updated

### 10. Common Mistakes to Avoid

❌ **Assuming Not Implemented**
- Just because you haven't seen the code doesn't mean it doesn't exist
- Search thoroughly before claiming missing functionality

❌ **Testing Imports Only**
- `import module` passing doesn't mean the feature works
- Must test actual user-facing functionality

❌ **Ignoring Error Messages**
- Every warning/error is a potential issue
- Don't dismiss errors as "minor" or "expected"

❌ **Not Following Complete Chain**
- GUI: Click → Signal → Handler → Action → Result
- Processing: Input → Process → Output → Display
- Must verify every step

❌ **Platform-Specific Testing**
- Don't test only on one platform if feature is cross-platform
- Check fallbacks actually work

### 11. Repair Workflow

```python
# 1. Understand what SHOULD happen
# User clicks button → Handler called → Action performed → UI updates

# 2. Find where it breaks
# Add logging at each step
logger.debug("Button clicked")  # ✅ This logs
logger.debug("Handler called")  # ❌ This doesn't log

# 3. Fix the break
# Found: Signal not connected
# Fix: self.button.clicked.connect(self.handler)

# 4. Verify complete chain
# Click button → Check logs → Verify all steps execute

# 5. Test edge cases
# Multiple clicks, rapid clicks, during other operations, etc.
```

### 12. Documentation Standards

When documenting a fix:
- State the original problem clearly
- Explain root cause
- Describe the fix
- List verification steps taken
- Note any side effects
- Update CHANGELOG

### 13. Quality Gates

**Before Committing a Fix:**
- [ ] Code compiles
- [ ] Feature works as intended
- [ ] No new errors introduced
- [ ] No regressions in existing features
- [ ] Cross-platform compatibility maintained
- [ ] Performance acceptable
- [ ] Code follows project style
- [ ] Tests pass (if applicable)
- [ ] Documentation updated
- [ ] CHANGELOG updated

### 14. Emergency Debugging

When under pressure or time-constrained:
1. **Reproduce** - Can you make it fail on demand?
2. **Isolate** - Narrow down to smallest failing component
3. **Fix** - Apply minimal change to resolve
4. **Verify** - Confirm fix works
5. **Document** - Note what was done (even if brief)

## Summary

**The Golden Rule:**
> If a user reports a feature isn't working, it's broken and needs fixing - not documentation, not "coming soon", not "not implemented yet". Fix it, test it, verify it works, then report success.

**Verification Standard:**
> "Working" means a user can successfully use the feature in the actual application, not just that imports succeed or code exists.

**Testing Standard:**
> Test the actual user workflow, not just individual functions. If user clicks a button, verify the complete action completes successfully.
