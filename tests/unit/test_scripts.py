"""The launch/install/repair scripts and LAUNCHER_GUIDE.md must stay true to the code (audit of 2026-10-01 found a debug
launcher that did not enable debugging, documented flags that were removed, installers checking for a removed package,
step counters that disagreed, stale feature counts, LF-only .bat files and CRLF .sh files)."""
import glob
import logging
import os
import re
import shutil
import subprocess

import pytest

from thermal_inspection import cli

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CR, LF = b"\r\n", b"\n"


def path(*parts):
    return os.path.join(ROOT, *parts)


def text(*parts):
    return open(path(*parts), encoding="utf-8", errors="ignore").read()


BATS = [path("launch.bat")] + sorted(glob.glob(path("scripts", "*.bat")))
SHELLS = sorted(glob.glob(path("scripts", "*.sh")))
POWERSHELL = sorted(glob.glob(path("scripts", "*.ps1")))
USER_FACING = BATS + SHELLS + POWERSHELL + [path("LAUNCHER_GUIDE.md")]


class TestCliDiagnostics:
    def test_log_options_exist_with_safe_defaults(self):
        args = cli.build_parser().parse_args([])
        assert args.log_level == "WARNING" and args.log_file is None

    def test_log_level_is_case_insensitive_and_validated(self):
        assert cli.build_parser().parse_args(["--log-level", "debug"]).log_level == "DEBUG"
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["--log-level", "loud"])

    def test_configure_logging_writes_the_file_at_the_requested_level(self, tmp_path):
        root = logging.getLogger()
        saved_handlers, saved_level = list(root.handlers), root.level
        try:
            log_file = str(tmp_path / "debug.log")
            assert cli.configure_logging("DEBUG", log_file) == logging.DEBUG
            logging.getLogger("scripts.test").debug("hello from the debug log")
            for h in root.handlers:
                h.flush()
            content = open(log_file, encoding="utf-8").read()
            assert "hello from the debug log" in content and "DEBUG:scripts.test" in content
            assert re.match(r"\d{4}-\d{2}-\d{2} ", content)                      # the file has timestamps
            cli.configure_logging("WARNING")
            assert root.level == logging.WARNING
        finally:
            for h in list(root.handlers):
                root.removeHandler(h)
                h.close()
            for h in saved_handlers:
                root.addHandler(h)
            root.setLevel(saved_level)

    def test_unwritable_log_file_does_not_stop_the_app(self, tmp_path, capsys):
        root = logging.getLogger()
        saved_handlers, saved_level = list(root.handlers), root.level
        try:
            cli.configure_logging("INFO", str(tmp_path / "no_such_dir" / "x.log"))
            assert "Could not open log file" in capsys.readouterr().err
        finally:
            for h in list(root.handlers):
                root.removeHandler(h)
                h.close()
            for h in saved_handlers:
                root.addHandler(h)
            root.setLevel(saved_level)


class TestFlagsAreReal:
    INSTALLER_FLAGS = {"--with-firefly", "--with-3d-mapping", "--with-realsense-l515", "--help",
                       "--system-site-packages", "--user", "--upgrade", "--index-url", "--version", "--list-devices",
                       "--break-system-packages"}

    def real_options(self):
        opts = set(cli.build_parser()._option_string_actions)
        return opts | self.INSTALLER_FLAGS

    PLACEHOLDERS = {"--your-custom-args"}                                       # an example name in the guide

    @staticmethod
    def app_lines(file):
        """Lines that talk about the APP's options. Installers and the L515 build script also call other tools
        (systemctl --reload-rules, cmake --build, git --depth ...), so there only app launches count."""
        lines = open(file, encoding="utf-8", errors="ignore").read().splitlines()
        name = os.path.basename(file)
        if name.startswith(("install_", "repair_", "setup_")):
            return [ln for ln in lines if "thermal_inspection" in ln and "--" in ln]
        return lines

    @pytest.mark.parametrize("file", USER_FACING)
    def test_every_double_dash_flag_is_a_real_option(self, file):
        known = self.real_options() | self.PLACEHOLDERS
        bad = set()
        for line in self.app_lines(file):
            for flag in re.findall(r"(?<![\w-])(--[a-z][a-z0-9_-]+)", line):
                if flag not in known:
                    bad.add(flag)
        assert not bad, f"{os.path.relpath(file, ROOT)} mentions options the app does not have: {sorted(bad)}"

    def test_the_debug_launcher_really_turns_debugging_on(self):
        body = text("scripts", "quick-debug.bat")
        assert "--log-level DEBUG" in body and "--log-file thermal_inspection_debug.log" in body


class TestNoStaleClaims:
    STALE = ["Thermal Road Monitor", "ultralytics", "supervision", "opencv-contrib", "Version 3.0.0", "Python 3.8",
             "45 Thermal", "7 Fusion", "9 fusion", "9 Fusion", "cp38", "--thermal-backend flirpy"]

    @pytest.mark.parametrize("file", USER_FACING)
    def test_no_stale_phrases(self, file):
        content = open(file, encoding="utf-8", errors="ignore").read()
        found = [s for s in self.STALE if s in content]
        assert not found, f"{os.path.relpath(file, ROOT)} still says {found}"

    @pytest.mark.parametrize("file", [f for f in BATS + SHELLS if "install" in f or "repair" in f])
    def test_python_version_floor_matches_the_project(self, file):
        content = open(file, encoding="utf-8", errors="ignore").read()
        assert "3.10" in content, os.path.relpath(file, ROOT)
        assert "requires-python = \">=3.10\"" in text("pyproject.toml")

    @pytest.mark.parametrize("file", [f for f in BATS + SHELLS if "install" in f])
    def test_step_counters_agree(self, file):
        content = open(file, encoding="utf-8", errors="ignore").read()
        steps = re.findall(r"\[(\d+(?:\.\d+)?)/(\d+)\]", content)
        assert steps, file
        assert len({total for _, total in steps}) == 1, f"{os.path.relpath(file, ROOT)} mixes totals: {sorted(set(steps))}"

    @pytest.mark.parametrize("file", [f for f in BATS + SHELLS if "install" in f or "repair" in f])
    def test_files_named_in_checks_exist(self, file):
        content = open(file, encoding="utf-8", errors="ignore").read()
        missing = []
        for rel in set(re.findall(r"thermal_inspection[\\/][\w\\/]+\.py", content)):
            if not os.path.exists(path(*re.split(r"[\\/]", rel))):
                missing.append(rel)
        assert not missing, f"{os.path.relpath(file, ROOT)} checks for files that do not exist: {missing}"

    def test_missing_config_json_is_not_reported_as_a_failure(self):
        # config.json is git-ignored and created on first run: a fresh clone must not read as a broken install
        for f in (path("scripts", "install_windows.bat"), path("scripts", "repair_windows.bat")):
            assert "config.json - MISSING" not in open(f, encoding="utf-8", errors="ignore").read()


class TestLineEndingsAndBatchTraps:
    @pytest.mark.parametrize("file", BATS + POWERSHELL)
    def test_windows_scripts_are_crlf(self, file):
        raw = open(file, "rb").read()
        assert raw.count(LF) == raw.count(CR), f"{os.path.relpath(file, ROOT)} has LF-only lines (cmd.exe mis-parses these)"
        assert raw.endswith(CR), f"{os.path.relpath(file, ROOT)} must end with a newline"

    @pytest.mark.parametrize("file", SHELLS)
    def test_shell_scripts_are_lf(self, file):
        raw = open(file, "rb").read()
        assert b"\r" not in raw, f"{os.path.relpath(file, ROOT)} has CRLF (bash: '\\r: command not found')"
        assert raw.endswith(LF)

    @pytest.mark.parametrize("file", BATS)
    def test_batch_files_use_call_for_python(self, file):
        """With pyenv-win `python` is a python.bat shim; invoking it from a .bat without `call` never returns control, so
        the script silently stops at its first python command."""
        bad = [ln.strip() for ln in open(file, encoding="utf-8", errors="ignore") if re.match(r"\s*python\s", ln)]
        assert not bad, f"{os.path.relpath(file, ROOT)}: use 'call python': {bad[:3]}"

    @staticmethod
    def working_bash():
        """A bash that really runs (on Windows `bash` is often the empty WSL launcher, which prints a help text)."""
        exe = shutil.which("bash")
        if exe is None:
            return None
        try:
            out = subprocess.run([exe, "-c", "echo ok"], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return None
        return exe if out.returncode == 0 and out.stdout.strip() == "ok" else None

    @pytest.mark.parametrize("file", SHELLS)
    def test_shell_scripts_parse(self, file):
        exe = self.working_bash()
        if exe is None:
            pytest.skip("no working bash on this machine")
        result = subprocess.run([exe, "-n", file], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_gitattributes_pins_the_endings(self):
        attrs = text(".gitattributes")
        for rule in ("*.bat  text eol=crlf", "*.ps1  text eol=crlf", "*.sh   text eol=lf"):
            assert rule in attrs, rule
