# Setting Up Python 3.10 Virtual Environment for PySpin

## Why Python 3.10?

PySpin (Spinnaker Python wrapper) typically supports Python 3.7-3.10 (sometimes 3.11).
Your current Python 3.12 is likely too new for existing PySpin wheels.

## Step 1: Install Python 3.10

### Download Python 3.10

1. Go to: https://www.python.org/downloads/release/python-31011/
2. Scroll down to "Files"
3. Download: **Windows installer (64-bit)**
   - File: `python-3.10.11-amd64.exe`

### Install Python 3.10

1. Run the installer
2. **IMPORTANT**: Check these boxes:
   - ☑ Add Python 3.10 to PATH
   - ☑ Install for all users (optional)
3. Click "Customize installation"
4. Check all optional features
5. In "Advanced Options":
   - ☑ Install for all users
   - ☑ Add Python to environment variables
   - Set install location: `C:\Python310\`
6. Click Install

### Verify Installation

After installation, open a NEW command prompt:
```cmd
py -3.10 --version
```
Should output: `Python 3.10.11`

## Step 2: I'll Create the Virtual Environment

Once Python 3.10 is installed, I can automatically:
1. Create a virtual environment with Python 3.10
2. Install all project requirements
3. Prepare it for PySpin installation

## Step 3: Install PySpin in the New Environment

After you download the PySpin wheel from FLIR:
1. Activate the venv
2. Install the wheel

## Quick Start (After Installing Python 3.10)

Just tell me when Python 3.10 is installed and I'll run:
```bash
py -3.10 -m venv venv_py310
venv_py310\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
# Then install PySpin wheel when you get it
```

---

## Alternative: Let Me Guide You Through Manual Setup

If you prefer to do it yourself, here are the exact commands:

```cmd
# Navigate to project
cd "C:\Users\stati\Desktop\Projects\ThermalFusionDrivingAssist"

# Create virtual environment with Python 3.10
py -3.10 -m venv venv_py310

# Activate it
venv_py310\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install project requirements
pip install -r requirements.txt

# When you get PySpin wheel:
pip install path\to\spinnaker_python-X.X.X-cp310-cp310-win_amd64.whl

# Verify
python verify_pyspin.py
```

## Using the Virtual Environment

**Activate:**
```cmd
cd "C:\Users\stati\Desktop\Projects\ThermalFusionDrivingAssist"
venv_py310\Scripts\activate
```

**Run application:**
```cmd
python main.py
```

**Deactivate:**
```cmd
deactivate
```

---

Ready to proceed? Let me know when you've installed Python 3.10!
