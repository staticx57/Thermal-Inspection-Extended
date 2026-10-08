"""What the Help > About window shows: version, the environment, where data lives, and recent camera problems."""
from __future__ import annotations

import html
import importlib.util
import platform
import sys
from typing import Dict, List, Optional

# optional features, as (label, import name); only whether each can be imported is reported, nothing is imported here
OPTIONAL_PACKAGES = (
    ("flirpy (radiometric Boson)", "flirpy"),
    ("pyrealsense2 (RealSense)", "pyrealsense2"),
    ("open3d (3D Mapping)", "open3d"),
    ("PySpin (Firefly)", "PySpin"),
    ("pygrabber (Windows camera list)", "pygrabber"),
    ("torch (depth / detection models)", "torch"),
)


def optional_packages() -> Dict[str, bool]:
    found = {}
    for label, module in OPTIONAL_PACKAGES:
        try:
            found[label] = importlib.util.find_spec(module) is not None
        except (ImportError, ValueError):
            found[label] = False
    return found


def environment_lines() -> List[str]:
    """Versions of the pieces that most often explain a problem."""
    lines = [f"Python {platform.python_version()} on {platform.system()} {platform.release()}"]
    try:
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        lines.append(f"Qt {QT_VERSION_STR} (PyQt6 {PYQT_VERSION_STR})")
    except Exception:
        lines.append("Qt: not available")
    for name in ("cv2", "numpy"):
        try:
            module = __import__(name)
            lines.append(f"{'OpenCV' if name == 'cv2' else 'NumPy'} {module.__version__}")
        except Exception:
            lines.append(f"{name}: not available")
    return lines


def about_html(version: str, data_folder: str, failures: Optional[str] = None,
               packages: Optional[Dict[str, bool]] = None, env: Optional[List[str]] = None) -> str:
    """The About text (rich text). `failures` is CameraPluginHost.describe_failures(); '' or None means none."""
    esc = html.escape
    packages = optional_packages() if packages is None else packages
    env = environment_lines() if env is None else env
    rows = "".join(f"<tr><td>{esc(label)}&nbsp;&nbsp;</td><td>{'available' if ok else 'not installed'}</td></tr>"
                   for label, ok in packages.items())
    problems = (f"<p><b>Recent camera problems</b><br>{esc(failures).replace(chr(10), '<br>')}</p>" if failures
                else "<p><b>Recent camera problems</b><br>none since the app started</p>")
    return (
        f"<h3>Thermal Inspection Fusion Tool</h3><p>Version {esc(version)}</p>"
        f"<p>{'<br>'.join(esc(line) for line in env)}</p>"
        f"<p><b>Optional features</b></p><table cellspacing='2'>{rows}</table>"
        f"<p><b>Settings and recordings</b><br>{esc(data_folder)}</p>"
        f"{problems}"
        "<p>Troubleshooting: run with <code>--log-level INFO --log-file debug.log</code>, or use the launcher's "
        "diagnostic option. If cameras are missing after a crash, run <code>--reset-camera-cache</code>.</p>"
    )
