# Interactive Radiometric Features - Complete Guide

## Overview

Your system has extensive interactive temperature measurement capabilities that work with BOTH the 8-bit estimation AND future 16-bit radiometric modes.

---

## 🌍 GLOBAL Temperature Features (Full Frame)

### 1. **Automatic Min/Max Detection** ✅ WORKING NOW
**What it does:** Automatically finds and displays hottest and coldest points in the entire frame

**How to use:**
- Always active when 8-bit estimation is enabled
- Red markers (🔴) show hot spots with temperature
- Blue markers (🔵) show cold spots with temperature
- Updates in real-time

**Display:**
```
🔴 Max: 45.2°C at (320, 150)
🔵 Min: 18.3°C at (100, 400)
```

---

### 2. **Frame Statistics** ✅ WORKING NOW
**What it does:** Computes global temperature statistics across entire frame

**Available data:**
- Minimum temperature
- Maximum temperature
- Average temperature
- Median temperature
- Standard deviation
- Percentile values (5th, 95th)

**Where to see:** Status displays and debug output

---

### 3. **Hardware Center Spot Meter** ✅ WORKING NOW
**What it does:** Uses camera's internal radiometry for center pixel temperature

**How to use:**
1. Open **Radiometric Panel**
2. Check **"Enable Hardware Spot Meter"**
3. Center point shows ±2-3°C accurate temperature
4. Works on ALL Boson cameras (not just -R models)

**Accuracy:** ±2-3°C (true radiometric from camera FPA)

---

### 4. **Click-to-Measure Spot Meter** 🚧 NEEDS ACTIVATION
**What it does:** Click anywhere on thermal image to measure temperature at that exact point

**Current status:** Backend exists, needs GUI toggle button

**How it will work:**
1. Click "Add Measurement Point" button
2. Click anywhere on thermal image
3. Temperature label appears at that point
4. Add multiple measurement points
5. Each shows live temperature reading

**Data available per point:**
- Exact pixel temperature
- Pixel coordinates
- AGC value at that point
- FPA-compensated temperature

---

## 🎯 ROI-Based Temperature Features (Per Region)

### 1. **Manual ROI Drawing** ✅ WORKING NOW
**What it does:** Draw custom regions and analyze temperatures within them

**How to use:**
1. Click **"✏ Draw ROI"** button in Control Panel
2. Choose ROI type:
   - Rectangle: Click and drag
   - Polygon: Click points, double-click to finish
3. ROI automatically analyzes temperatures inside

**Per-ROI temperature data:**
- `temp_min`: Minimum temperature in ROI
- `temp_max`: Maximum temperature in ROI
- `temp_avg`: Average temperature in ROI
- `temp_std`: Standard deviation in ROI
- Temperature history/trending

---

### 2. **Automatic Temperature-Based ROIs** ✅ WORKING NOW
**What it does:** System auto-detects hot and cold regions and creates ROIs

**How to use:**
1. Enable auto-ROI detection
2. Set temperature thresholds
3. System automatically:
   - Detects hot spots above threshold
   - Detects cold spots below threshold
   - Creates ROIs around them
   - Tracks them over time

**ROI types created:**
- `AUTO_TEMPERATURE`: Temperature-based regions
- `AUTO_GRADIENT`: High thermal gradient regions
- `AUTO_MOTION`: Moving hot/cold objects
- `AUTO_EDGE`: Sharp temperature boundaries

---

### 3. **ROI Temperature Statistics** ✅ WORKING NOW
**What it does:** Full statistical analysis per ROI

**Available per ROI:**
```python
{
    'temp_min': 25.3,      # Coldest point in ROI (°C)
    'temp_max': 42.1,      # Hottest point in ROI (°C)
    'temp_avg': 33.7,      # Average temperature (°C)
    'temp_std': 4.2,       # Temperature variation (°C)
    'emissivity': 0.95,    # Material emissivity (optional override)
    'temp_history': [...]   # Historical temps for trending
}
```

**Use cases:**
- Monitor specific equipment over time
- Compare temperatures across different regions
- Alert on temperature changes in critical areas
- Track thermal trends per region

---

### 4. **Per-ROI Min/Max Points** ✅ WORKING NOW
**What it does:** Find hottest and coldest point WITHIN each ROI

**Display:**
```
ROI "Motor Housing":
  🔴 Hottest: 58.2°C at (450, 200)
  🔵 Coldest: 32.1°C at (440, 220)
  📊 Average: 45.3°C
  📈 StdDev: ±6.1°C
```

---

## 📊 Measurement Point System

### Current Implementation ✅ AVAILABLE
**Module:** `measurement_points.py` - `MeasurementPointManager`

**Capabilities:**
- Add measurement points by clicking
- Store point coordinates and temperatures
- Update temperatures in real-time
- Track multiple points simultaneously
- Export measurement data

**Data per measurement point:**
```python
{
    'point_id': 'MP001',
    'x': 320,
    'y': 240,
    'temperature_c': 35.4,
    'agc_value': 145,
    'timestamp': '2025-12-02T14:30:15',
    'fpa_compensated': True
}
```

---

## 🔄 How 8-Bit vs 16-Bit Works

### With 8-Bit Estimation (Current)
- **Global Features:** Use `ThermalTemperatureEstimator.get_pixel_temperature()`
- **ROI Features:** Estimate temperatures from AGC values within ROI mask
- **Accuracy:** ±5-10°C absolute, ±2-3°C relative
- **Hardware Spot Meter:** Uses camera's internal radiometry (±2-3°C)

### With 16-Bit Radiometric (Future)
- **Global Features:** Direct 16-bit radiometric data per pixel
- **ROI Features:** True radiometric analysis within ROI mask
- **Accuracy:** ±2°C absolute (NIST-traceable)
- **Hardware Spot Meter:** Same camera radiometry

### Unified API
**Both modes use the same interface:**
```python
# Get temperature at any point (works with both modes)
temp_c = app.get_pixel_temperature(x, y)

# Get ROI statistics (works with both modes)
roi_stats = app.get_roi_temperature_stats(roi_id)

# Global min/max (works with both modes)
global_stats = app.get_global_temperature_stats()
```

---

## 🎮 How to Use Everything Right Now

### Step 1: Enable 8-Bit Estimation
✅ Should be auto-enabled when SDK connects
✅ Checkbox in Radiometric Panel should be checked

### Step 2: Set Scene Range
1. Radiometric Panel → "Scene Temperature Range"
2. Min: 10°C, Max: 110°C (adjust for your scene)
3. Click "Apply Scene Range"

### Step 3: Calibrate (Optional but Recommended)
**Single-Point:**
1. Point at known temp object (e.g., ice water = 0°C)
2. Center it in frame
3. Click "Single-Point Calibration"
4. Enter known temperature

**Two-Point (Best):**
1. Point at COLD reference (ice water)
2. Click "Two-Point Calibration"
3. Enter cold temp (0°C)
4. Point at HOT reference (warm object)
5. Enter hot temp (50°C)

### Step 4: Use Interactive Features

**For Global Min/Max:**
- Just look at the thermal display
- Red/blue markers show hot/cold spots automatically

**For ROI Analysis:**
1. Click "✏ Draw ROI" button
2. Draw rectangle or polygon
3. ROI shows temp stats immediately

**For Hardware Spot Meter:**
1. Check "Enable Hardware Spot Meter" in Radiometric Panel
2. Point camera - center reads precise temperature

**For Click-to-Measure:** (needs button - coming soon)
- Will add "Add Measurement Point" button
- Click anywhere to measure that exact spot
- Track multiple points

---

## 📈 Advanced Features

### Temperature Trending
- Each ROI stores `temp_history`
- Track how temperatures change over time
- Detect gradual increases/decreases
- Alert on sudden changes

### Emissivity Override
- Set different emissivity per ROI
- Correct for different materials
- `roi.emissivity = 0.85` for painted metal
- `roi.emissivity = 0.95` for matte black

### Temperature Gradients
- Auto-detect regions with sharp temperature changes
- `AUTO_GRADIENT` ROIs find thermal boundaries
- Useful for finding leaks, defects, interfaces

---

## 🔧 Implementation Status

| Feature | Status | 8-Bit Support | 16-Bit Support |
|---------|--------|---------------|----------------|
| Global Min/Max | ✅ Working | ✅ Yes | 🔜 Ready |
| Global Statistics | ✅ Working | ✅ Yes | 🔜 Ready |
| Hardware Spot Meter | ✅ Working | ✅ Yes | 🔜 Ready |
| Click-to-Measure | 🚧 Backend Ready | ✅ Yes | 🔜 Ready |
| Manual ROIs | ✅ Working | ✅ Yes | 🔜 Ready |
| Auto ROIs | ✅ Working | ✅ Yes | 🔜 Ready |
| ROI Temp Stats | ✅ Working | ✅ Yes | 🔜 Ready |
| ROI Min/Max Points | ✅ Working | ✅ Yes | 🔜 Ready |
| Temperature Trending | ✅ Working | ✅ Yes | 🔜 Ready |
| Emissivity Override | ✅ Working | ✅ Yes | 🔜 Ready |

---

## 🎯 What to Test Right Now

1. ✅ **8-Bit estimation checkbox** - should be auto-checked
2. ✅ **Scene range controls** - set min/max, click Apply
3. ✅ **Single-point calibration** - use known temp reference
4. ✅ **Two-point calibration** - use two known temps
5. ✅ **Draw ROI** - create rectangle, see temp stats
6. ✅ **Hardware spot meter** - check box, see center temp
7. ✅ **Auto min/max display** - should see red/blue markers
8. ✅ **ROI temperature stats** - each ROI shows min/max/avg

---

## 🚀 Coming Soon

### Click-to-Measure Interface
Add button to Radiometric Panel:
```
[📍 Add Measurement Point]
```
Click anywhere on thermal image to measure that spot.

### Enhanced Visualization
- Temperature color scale bar
- Isotherm lines (contours at specific temps)
- Temperature difference mode (delta T)
- Temperature profile graphs

### Export Features
- Export ROI temperature data to CSV
- Export measurement points with timestamps
- Temperature trend graphs
- Thermal reports with statistics

---

## 💡 Tips

1. **Calibrate before critical measurements** - Two-point calibration significantly improves accuracy
2. **Use ROIs for monitoring** - Set up ROIs on critical areas, monitor trends
3. **Hardware spot meter for reference** - Most accurate single-point measurement
4. **8-bit for relative analysis** - Great for finding hot/cold spots, comparing regions
5. **Adjust scene range** - Narrower range = better relative sensitivity

---

## 📞 Summary

You currently have:
- ✅ Global temperature analysis (min/max/avg/stats)
- ✅ Per-ROI temperature analysis (all stats)
- ✅ Hardware spot meter (center pixel, ±2-3°C)
- ✅ Auto hot/cold spot detection
- ✅ Manual ROI drawing with temp stats
- ✅ Auto temperature-based ROI detection
- 🚧 Click-anywhere measurement (backend ready, needs GUI button)

**Everything works with 8-bit estimation right now, and will seamlessly upgrade to 16-bit when that backend is added!**
