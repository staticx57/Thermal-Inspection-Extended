"""A plain-text report of the machine, for debugging "it won't start / my camera isn't found" remotely.

Standard library only at import time, so it also runs as a bare script before any dependency is installed:

    python3 thermal_inspection/utils/system_info.py          # works even when pip install has not run yet
    python -m thermal_inspection --system-info                # same report, from the app

Every section is collected independently: one failing probe prints its error and the rest still run.
"""
from __future__ import annotations

import glob
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from typing import Callable, List, Optional

REQUIRED_MODULES = (("numpy", "numpy"), ("cv2", "OpenCV"), ("PyQt6.QtWidgets", "PyQt6"), ("pyqtgraph", "pyqtgraph"),
                    ("psutil", "psutil"), ("serial", "pyserial"), ("scipy", "SciPy"), ("flirpy", "flirpy"))
OPTIONAL_MODULES = (("pyrealsense2", "pyrealsense2"), ("open3d", "open3d"), ("PySpin", "PySpin"),
                    ("OpenGL", "PyOpenGL"), ("torch", "torch"), ("usb", "pyusb"))
# system libraries a pip-installed PyQt6 needs on Ubuntu (xcb platform plugin); (soname fragment, apt package)
LINUX_QT_LIBS = (("xcb-cursor", "libxcb-cursor0"), ("xkbcommon-x11", "libxkbcommon-x11-0"), ("GL", "libgl1"))


def _run(cmd: List[str], timeout: float = 5.0) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (out.stdout or out.stderr or "").strip()
    except Exception as e:  # missing binary, timeout, permissions
        return f"({cmd[0]}: {e.__class__.__name__}: {e})"


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return ""


def _os_release() -> dict:
    info = {}
    for line in _read("/etc/os-release").splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            info[key] = value.strip('"')
    return info


def section_system() -> List[str]:
    lines = [f"Platform : {platform.system()} {platform.release()} ({platform.machine()})",
             f"Python   : {platform.python_version()} at {sys.executable}",
             f"Virtualenv: {os.environ.get('VIRTUAL_ENV') or 'none (system Python)'}"]
    if platform.system() == "Linux":
        rel = _os_release()
        lines.append(f"Distro   : {rel.get('PRETTY_NAME', 'unknown')}")
        if os.path.exists("/etc/nv_tegra_release"):
            lines.append("Jetson   : yes")
        stdlib = os.path.dirname(os.__file__)
        if os.path.exists(os.path.join(stdlib, "EXTERNALLY-MANAGED")):
            lines.append("PEP 668  : system Python is externally managed - install inside a venv")
        if sys.version_info < (3, 10):
            lines.append("WARNING  : Python 3.10 or newer is required")
        elif sys.version_info >= (3, 13):
            lines.append("NOTE     : Python 3.13+ is not tested; Open3D has no wheel for it")
        lines.append(f"Session  : XDG_SESSION_TYPE={os.environ.get('XDG_SESSION_TYPE', '-')} "
                     f"DISPLAY={os.environ.get('DISPLAY', '-')} WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '-')} "
                     f"QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM', '-')}")
    return lines


# import name -> PyPI distribution name, for the few that differ
_DIST = {"cv2": "opencv-python", "PyQt6.QtWidgets": "PyQt6", "serial": "pyserial", "usb": "pyusb",
         "OpenGL": "PyOpenGL", "PySpin": "spinnaker-python"}


def module_state(module: str) -> str:
    """'ok <version>' / 'not installed' WITHOUT importing the module.

    Importing here would be wrong twice over: torch/open3d are order-sensitive on Windows (importing them after Qt
    reports a DLL failure the real app never has, because the app preloads them first) and a probe must never be able
    to crash or slow the thing it is diagnosing."""
    try:
        spec = importlib.util.find_spec(module)
    except (ImportError, ValueError):
        spec = None
    if spec is None:
        return "not installed"
    try:
        from importlib import metadata
        return f"ok {metadata.version(_DIST.get(module, module.split('.')[0]))}"
    except Exception:
        return "ok (version unknown)"


def preflight(headless: bool = False) -> tuple:
    """(blocking, warnings): human-readable lines. Never imports anything and never raises.

    `blocking` lists what the app cannot start without, each with the exact command that fixes it; `warnings` lists
    things that will degrade or abort later (missing Qt system libraries) but where we cannot be sure."""
    blocking: List[str] = []
    warnings: List[str] = []
    try:
        if sys.version_info < (3, 10):
            blocking.append(f"Python 3.10 or newer is required (this is {platform.python_version()}).")
        hard = [("numpy", "numpy"), ("cv2", "opencv-python"), ("psutil", "psutil")]
        if not headless:
            hard += [("PyQt6.QtWidgets", "PyQt6"), ("pyqtgraph", "pyqtgraph")]
        for module, dist in hard:
            if module_state(module) == "not installed":
                blocking.append(f"{module.split('.')[0]} is not installed -> pip install {dist}")
        for module, dist in (("serial", "pyserial"), ("scipy", "scipy"), ("flirpy", "flirpy")):
            if module_state(module) == "not installed":
                warnings.append(f"{dist} is not installed; features that use it will be unavailable "
                                f"(pip install {dist})")
        if platform.system() == "Linux" and not headless:
            missing = missing_qt_libs()
            if missing:
                warnings.append("Qt may fail to start (\"Could not load the Qt platform plugin xcb\") because system "
                                f"libraries are missing -> sudo apt install {' '.join(missing)}")
    except Exception as e:  # a broken check must never stop the app from trying to start
        warnings.append(f"dependency check could not finish ({e.__class__.__name__}: {e})")
    return blocking, warnings


def section_packages() -> List[str]:
    lines = [f"{label:<14}: {module_state(module)}" for module, label in REQUIRED_MODULES]
    lines.append("-- optional (found, not imported) --")
    lines += [f"{label:<14}: {module_state(module)}" for module, label in OPTIONAL_MODULES]
    return lines


def missing_qt_libs() -> List[str]:
    """apt packages whose shared library cannot be found (Linux only)."""
    import ctypes.util
    return [apt for fragment, apt in LINUX_QT_LIBS if ctypes.util.find_library(fragment) is None]


def section_linux_access() -> List[str]:
    lines = []
    missing = missing_qt_libs()
    lines.append("Qt system libraries: " + ("all present" if not missing else
                                            f"MISSING -> sudo apt install {' '.join(missing)}"))
    try:
        import grp
        names = sorted({grp.getgrgid(g).gr_name for g in os.getgroups()})
        user = os.environ.get("USER", "?")
        lines.append(f"User {user} groups: {' '.join(names)}")
        for needed, why in (("dialout", "serial ports"), ("video", "cameras")):
            if needed not in names:
                lines.append(f"  MISSING group '{needed}' ({why}) -> sudo usermod -aG {needed} {user}, then log out/in")
    except Exception as e:
        lines.append(f"groups: unavailable ({e})")
    if shutil.which("systemctl"):
        state = _run(["systemctl", "is-active", "ModemManager"])
        lines.append(f"ModemManager: {state}"
                     + ("  (may grab serial ports - see scripts/linux_setup.sh --fix)" if state == "active" else ""))
    lines.append(f"v4l2-ctl: {'present' if shutil.which('v4l2-ctl') else 'MISSING -> sudo apt install v4l-utils'}")
    return lines


def section_serial() -> List[str]:
    try:
        from serial.tools import list_ports
    except Exception as e:
        return [f"pyserial not importable ({e}); install it to list ports"]
    ports = sorted(list_ports.comports(), key=lambda p: p.device)
    if not ports:
        return ["no serial ports found"]
    lines = []
    for p in ports:
        vidpid = f"{p.vid:04X}:{p.pid:04X}" if p.vid is not None else "----:----"
        access = ""
        if platform.system() == "Linux":
            access = "  [no read/write access]" if not os.access(p.device, os.R_OK | os.W_OK) else ""
        lines.append(f"{p.device:<14} {vidpid}  {p.description or '-'}  ({p.manufacturer or '-'}){access}")
    return lines


def section_video() -> List[str]:
    if platform.system() != "Linux":
        return ["(DirectShow device list is shown in Help > About / the camera panel on this platform)"]
    nodes = sorted(glob.glob("/dev/video*"), key=lambda p: int(p[10:]) if p[10:].isdigit() else 0)
    if not nodes:
        return ["no /dev/video* nodes"]
    lines = []
    for node in nodes:
        name = _read(f"/sys/class/video4linux/{os.path.basename(node)}/name") or "-"
        access = "" if os.access(node, os.R_OK | os.W_OK) else "  [no read/write access]"
        lines.append(f"{node:<14} {name}{access}")
    lines.append("(each camera usually has two nodes; only the first one carries video)")
    if shutil.which("v4l2-ctl"):
        lines.append(_run(["v4l2-ctl", "--list-devices"]))
    return lines


def section_usb() -> List[str]:
    if platform.system() == "Linux" and shutil.which("lsusb"):
        return _run(["lsusb"]).splitlines()
    return ["(lsusb not available)"]


# keep in sync with sdk.tau2_serial.scan_tau2_ports (a test asserts it); duplicated so the report never has to import
# the app package (which pulls in torch) just to match three words
TAU2_PORT_KEYWORDS = ("tau", "ftdi", "thermalcapture")


def section_tau2() -> List[str]:
    try:
        from serial.tools import list_ports
        found = [p.device for p in list_ports.comports()
                 if any(k in (p.description or "").lower() or k in (p.hwid or "").lower() for k in TAU2_PORT_KEYWORDS)]
    except Exception as e:
        return [f"scan unavailable ({e.__class__.__name__}: {e})"]
    return [f"Tau 2 CCI port found by name match: {', '.join(found) if found else 'none'}",
            "(if your board's port is listed above but not matched, send its VID:PID)"]


SECTIONS: List[tuple] = [
    ("System", section_system),
    ("Python packages", section_packages),
    ("Linux access (Qt libraries, groups, ModemManager)", section_linux_access),
    ("Serial ports (device, VID:PID, description)", section_serial),
    ("Video devices", section_video),
    ("USB devices", section_usb),
    ("Tau 2 detection", section_tau2),
]


def collect_report(only_linux_sections: Optional[bool] = None) -> str:
    on_linux = platform.system() == "Linux" if only_linux_sections is None else only_linux_sections
    out: List[str] = []
    for title, fn in SECTIONS:  # type: ignore[assignment]
        if title.startswith("Linux access") and not on_linux:
            continue
        if title.startswith("USB devices") and not on_linux:
            continue
        out.append(f"== {title} ==")
        try:
            out += fn()  # type: ignore[operator]
        except Exception as e:
            out.append(f"(failed: {e.__class__.__name__}: {e})")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    print(collect_report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
