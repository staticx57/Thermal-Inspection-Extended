"""
Where the app keeps its own files (config.json, the saved alignment calibration, recordings/, snapshots/).

Until now all of these were paths relative to whatever directory the app was started from, which is fine when running
from a clone but writes into the wrong place (or fails on a read-only install) anywhere else. Resolution order:

  1. THERMAL_INSPECTION_HOME, when set (explicit choice, also handy for tests and portable installs)
  2. the current directory when it already holds config.json or is a source checkout (pyproject.toml next to a
     thermal_inspection/ package): "dev mode", exactly the previous behaviour
  3. the per-user data directory (%APPDATA%\ThermalInspection, ~/Library/Application Support/ThermalInspection, or
     $XDG_DATA_HOME/thermal-inspection, ~/.local/share/thermal-inspection)
"""
import os
import platform
import sys
from pathlib import Path

ENV_VAR = "THERMAL_INSPECTION_HOME"


def user_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "ThermalInspection"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ThermalInspection"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "thermal-inspection"


def data_dir() -> Path:
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    cwd = Path.cwd()
    if (cwd / "config.json").exists() or ((cwd / "pyproject.toml").exists() and (cwd / "thermal_inspection").is_dir()):
        return cwd
    return user_data_dir()


def data_path(relative) -> Path:
    """A path under data_dir(); absolute paths are returned unchanged."""
    p = Path(relative)
    return p if p.is_absolute() else data_dir() / p


def default_serial_port() -> str:
    """A sensible first guess for the Boson/Tau control port on this OS (the UI and config can still override it)."""
    if sys.platform.startswith("win"):
        return "COM7"
    if sys.platform == "darwin":
        import glob
        found = sorted(glob.glob("/dev/tty.usbmodem*") + glob.glob("/dev/cu.usbmodem*"))
        return found[0] if found else "/dev/tty.usbmodem1"
    return "/dev/ttyACM0"
