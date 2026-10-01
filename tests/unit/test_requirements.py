"""requirements.txt must keep up with what the code actually imports (the audit of 2026-10-01 found flirpy, scipy, pyusb
and setuptools unlisted, an unused opencv-contrib that conflicts with opencv-python, a stale numpy<2 cap and a
too-old pyqtgraph minimum)."""
import ast
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REQ = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()

# import name -> distribution name as written in requirements.txt (matched case-insensitively, '-'/'_' equivalent)
DISTRIBUTION = {
    "cv2": "opencv-python", "numpy": "numpy", "scipy": "scipy", "PIL": "Pillow", "PyQt6": "PyQt6",
    "pyqtgraph": "pyqtgraph", "OpenGL": "PyOpenGL", "psutil": "psutil", "serial": "pyserial",
    "pygrabber": "pygrabber", "comtypes": "comtypes", "flirpy": "flirpy", "usb": "pyusb", "pyrealsense2": "pyrealsense2",
    "open3d": "open3d", "torch": "torch", "transformers": "transformers", "torch_directml": "torch-directml",
    "PySpin": "PySpin", "jtop": "jtop", "vpi": "vpi",
}
# not third-party packages: this project's own top-level modules reached through sys.path tweaks, an env var that
# looks like an import, or a guarded PyQt5 fallback in a file nothing else imports
NOT_PACKAGES = {"SDK_USER_PERMISSIONS", "boson_serial", "radiometric_calibration", "spot_meter_exporter",
                "spot_meter_panel", "PyQt5"}


def third_party_imports():
    found = {}
    for top in ("thermal_inspection", "tools"):
        for d, _, files in os.walk(os.path.join(ROOT, top)):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(d, f)
                try:
                    tree = ast.parse(open(path, encoding="utf-8", errors="ignore").read())
                except SyntaxError:
                    continue
                for n in ast.walk(tree):
                    mods = []
                    if isinstance(n, ast.Import):
                        mods = [a.name.split(".")[0] for a in n.names]
                    elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                        mods = [n.module.split(".")[0]]
                    for m in mods:
                        if m not in sys.stdlib_module_names and m != "thermal_inspection" and m not in NOT_PACKAGES:
                            found.setdefault(m, os.path.relpath(path, ROOT))
    return found


def normalised(text):
    return re.sub(r"[-_.]", "", text.lower())


def test_every_third_party_import_is_documented():
    missing, unknown = [], []
    req = normalised(REQ)
    for module, where in sorted(third_party_imports().items()):
        dist = DISTRIBUTION.get(module)
        if dist is None:
            unknown.append(f"{module} (first seen in {where})")
        elif normalised(dist) not in req:
            missing.append(f"{dist} (imported as '{module}' in {where})")
    assert not unknown, ("new third-party import with no known distribution: add it to DISTRIBUTION here AND to "
                         "requirements.txt: " + ", ".join(unknown))
    assert not missing, "not mentioned in requirements.txt: " + ", ".join(missing)


def active_lines():
    return [ln.split("#")[0].strip() for ln in REQ.splitlines() if ln.split("#")[0].strip()]


def test_required_core_packages_are_active_not_commented():
    active = " ".join(active_lines()).lower()
    for pkg in ("opencv-python", "numpy", "pyqt6", "pyqtgraph", "psutil", "pyserial", "flirpy", "scipy", "pillow"):
        assert pkg in active, f"{pkg} should be an active requirement"


def test_no_conflicting_or_stale_pins():
    active = [ln.lower() for ln in active_lines()]
    assert not any(ln.startswith("opencv-contrib-python") for ln in active), \
        "opencv-contrib-python overwrites opencv-python's cv2 and nothing uses it"
    assert not any(ln.startswith("numpy") and "<2" in ln.replace(" ", "") for ln in active), "stale numpy<2 cap"
    pg = next(ln for ln in active if ln.startswith("pyqtgraph"))
    assert ">=0.14" in pg.replace(" ", ""), "the 3D world viewer needs pyqtgraph 0.14's projectionMatrix(region, viewport)"
    assert any(ln.startswith("setuptools<81") for ln in active), "flirpy needs pkg_resources (removed in setuptools 81)"


def test_installer_fallbacks_do_not_name_removed_packages():
    for script in ("scripts/install_windows.bat", "scripts/install_linux.sh"):
        text = open(os.path.join(ROOT, script), encoding="utf-8", errors="ignore").read()
        assert "ultralytics" not in text and "supervision" not in text, f"{script} still installs removed ADAS packages"
        for line in text.splitlines():
            if "pip" in line and "install" in line:
                assert "opencv-contrib-python" not in line, f"{script}: {line.strip()}"


def test_installed_environment_satisfies_the_pins():
    """The environment the tests run in is the one the pins were verified against."""
    import importlib.metadata as md

    def ver(name):
        return tuple(int(x) for x in re.findall(r"\d+", md.version(name))[:2])

    assert ver("pyqtgraph") >= (0, 14)
    assert ver("numpy") >= (1, 24)
    assert ver("opencv-python") >= (4, 8)
    try:
        assert ver("setuptools") < (81, 0)
    except md.PackageNotFoundError:
        pytest.skip("setuptools not installed")
