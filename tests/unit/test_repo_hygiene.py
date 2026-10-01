"""Repository hygiene: .gitignore must cover transient/user files, and nothing tracked may match it (the audit of
2026-10-01 found ~90 stale Python 3.10 .pyc files and a per-machine .claude/settings.local.json tracked in git, and an
.egg-info rule that matched nothing)."""
import os
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HAVE_GIT = shutil.which("git") is not None and os.path.isdir(os.path.join(ROOT, ".git"))
pytestmark = pytest.mark.skipif(not HAVE_GIT, reason="needs a git checkout")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def ignored(path):
    return git("check-ignore", "-q", "--no-index", path).returncode == 0


def test_nothing_tracked_matches_an_ignore_rule():
    out = git("ls-files", "-ci", "--exclude-standard").stdout.split()
    assert not out, f"tracked files that .gitignore says should not be tracked (git rm --cached them): {out[:8]}"


@pytest.mark.parametrize("p", [
    "thermal_inspection/__pycache__/app.cpython-312.pyc", "tests/unit/__pycache__/x.cpython-312-pytest-9.pyc",
    ".pytest_cache/v/cache/lastfailed", ".coverage", ".coverage.host.123", "htmlcov/index.html", "coverage.xml",
    ".mypy_cache/x", ".ruff_cache/x", ".hypothesis/x", "thermal_inspection.egg-info/PKG-INFO", "dist/x.whl",
    "build/lib/x.py", ".venv/Scripts/python.exe", "config.json", "camera_registry.json", "settings_editor_theme.json",
    "thermal_inspection_debug.log", "debug.log", "recordings/a.avi", "snapshots/a.png", "world_maps/w.ply",
    "world_maps/w.ply.thermal.npz", "roi_sets/rois.json", "scratch/anything.py", "notes.txt.bak", "x.py.orig",
    ".claude/settings.local.json", "nul", "boson_sdk/SDK_USER_PERMISSIONS/x",
])
def test_transient_and_user_files_are_ignored(p):
    assert ignored(p), f"{p} should be ignored"


@pytest.mark.parametrize("p", [
    "requirements.txt", "pyproject.toml", "settings_schema.json", "launch.bat", "scripts/install_windows.bat",
    "scripts/install_linux.sh", "Media/banner_hero.png", "Media/Logo.svg", "docs/superpowers/plans/x.md",
    "tests/unit/test_repo_hygiene.py", "tests/unit/mapping_synth.py", "tools/mapping_motion_test.py",
    "thermal_inspection/app.py", "boson_sdk/README.md", "README.md", "TODO.md", "CHANGELOG.md",
])
def test_real_project_files_are_not_ignored(p):
    assert not ignored(p), f"{p} must not be ignored"


def test_running_the_tests_leaves_no_untracked_clutter():
    """New untracked files after a run would mean a test writes into the repo instead of a tmp dir."""
    untracked = [ln[3:] for ln in git("status", "--short", "--untracked-files=all").stdout.splitlines() if ln.startswith("??")]
    clutter = [u for u in untracked if u.endswith((".log", ".ply", ".npz", ".avi", ".mp4", ".csv", ".png", ".pyc"))]
    assert not clutter, clutter


def test_importing_the_package_does_not_configure_logging():
    """Nine library modules used to call logging.basicConfig(level=INFO) at import time, so merely importing the package
    reconfigured the root logger (and made the CLI's own setup unreliable). Only cli.configure_logging may do that."""
    import sys
    code = ("import logging, thermal_inspection.app, thermal_inspection.gui.main_window; "
            "r = logging.getLogger(); print(len(r.handlers), r.level)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120,
                         env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    last = out.stdout.strip().splitlines()[-1]
    assert last == "0 30", f"root logger was configured at import (handlers, level) = {last!r}; stderr: {out.stderr[-300:]}"


def test_no_module_level_basicconfig_in_the_package():
    import re
    offenders = []
    for d, _, files in os.walk(os.path.join(ROOT, "thermal_inspection")):
        for f in files:
            if f.endswith(".py") and f != "cli.py":
                p = os.path.join(d, f)
                if re.search(r"(?m)^logging\.basicConfig\(", open(p, encoding="utf-8", errors="ignore").read()):
                    offenders.append(os.path.relpath(p, ROOT))
    assert not offenders, offenders
