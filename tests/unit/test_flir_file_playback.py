"""FLIR .seq/.fff playback (flirpy's SEQ/FFF reader) as a radiometric thermal source."""
import numpy as np
import pytest

pytest.importorskip("flirpy")
from thermal_inspection.sdk.flir_file_reader import flirpy_can_read_files, flirpy_version  # noqa: E402

pytestmark = pytest.mark.skipif(not flirpy_can_read_files(),
                                reason=f"FLIR file playback needs flirpy >= 0.6 (installed {flirpy_version()})")

from tests.unit import flir_seq_fixture as fx
from thermal_inspection.cameras.flir_file_backend import FlirFileBackend
from thermal_inspection.cameras.plugin import get_registry
from thermal_inspection.cameras.plugin.camera_plugin import CameraRole
from thermal_inspection.cameras.plugins.flir_file import plugin as ffplugin
from thermal_inspection.processing.radiometric_converter import TLinearConverter
from thermal_inspection.sdk.flir_file_reader import FlirFileError, FlirFileSource, celsius_to_y16

H, W = 24, 32


@pytest.fixture
def seq(tmp_path):
    frames = [fx.gradient(H, W, 20, 60, offset=5.0 * i) for i in range(3)]
    path = tmp_path / "rec.seq"
    fx.write_seq(path, frames, fps=15)
    return str(path), frames


def test_source_reads_every_frame_with_its_own_temperatures(seq):
    path, frames = seq
    src = FlirFileSource(path)
    assert len(src) == 3 and (src.width, src.height) == (W, H) and src.fps == 15
    for i, truth in enumerate(frames):
        y16, celsius, meta = src.read(i)
        assert y16.dtype == np.uint16 and celsius.dtype == np.float32 and y16.shape == (H, W)
        assert np.abs(celsius - truth).max() < 0.1                      # Planck inversion, sensor quantisation
    d = src.describe()
    assert d["frames"] == 3 and d["model"] == "A315" and d["serial"] == "SN12345" and d["emissivity"] == 1.0


def test_y16_is_the_boson_kelvin_times_100_convention_so_the_pipeline_works_unchanged(seq):
    path, frames = seq
    y16, celsius, _ = FlirFileSource(path).read(1)
    assert np.abs(y16.astype(np.float64) / 100.0 - 273.15 - celsius).max() < 0.006
    converted = TLinearConverter().convert_frame(y16)               # the app's own radiometric conversion
    assert np.abs(converted - celsius).max() < 0.01


def test_single_fff_file(tmp_path):
    p = tmp_path / "one.fff"
    fx.write_fff(p, fx.gradient(H, W, 30, 50))
    src = FlirFileSource(str(p))
    assert len(src) == 1 and abs(src.read(0)[1][0, 0] - 30) < 0.1


def test_unusable_files_are_reported_clearly(tmp_path):
    with pytest.raises(FlirFileError, match="csq"):
        FlirFileSource(str(tmp_path / "x.csq"))
    with pytest.raises(FlirFileError, match="Unsupported"):
        FlirFileSource(str(tmp_path / "x.mp4"))
    with pytest.raises(FlirFileError, match="not found"):
        FlirFileSource(str(tmp_path / "missing.seq"))
    junk = tmp_path / "junk.seq"
    junk.write_bytes(b"this is not a FLIR file" * 50)
    with pytest.raises(FlirFileError):
        FlirFileSource(str(junk))


def test_celsius_to_y16_clips_and_survives_bad_values():
    y = celsius_to_y16(np.array([-300.0, 20.0, 1000.0, np.nan, np.inf]))
    assert y.dtype == np.uint16 and y[1] == 29315 and y[0] == 0 and y[2] == 65535 and y[3] == 0


def test_backend_plays_loops_seeks_and_measures(seq):
    path, frames = seq
    b = FlirFileBackend(path, realtime=False)
    assert not b.is_opened() and b.read() == (False, None)
    assert b.open() and b.is_radiometric() and b.get_resolution() == (W, H) and b.frame_count == 3
    seen = []
    for _ in range(7):                                                  # loops past the end
        ok, y = b.read()
        assert ok and y.shape == (H, W)
        seen.append(b.get_spot_temperature(0, 0))
    assert seen == pytest.approx([20, 25, 30, 20, 25, 30, 20], abs=0.1)
    assert b.get_temperature_map().shape == (H, W)
    assert b.get_spot_temperature(W + 5, 0) is None
    b.seek(2)
    b.read()
    assert b.get_spot_temperature(0, 0) == pytest.approx(30, abs=0.1)
    b.loop = False
    b.seek(2)
    assert b.read()[0] and b.read() == (False, None)
    assert b.get_info()["backend"] == "FLIR file" and b.get_info()["model"] == "A315"
    b.release()
    assert not b.is_opened()


def test_backend_open_fails_cleanly(tmp_path):
    b = FlirFileBackend(str(tmp_path / "nope.seq"))
    assert b.open() is False and "not found" in b.last_error


def test_backend_paces_at_the_recording_frame_rate(seq):
    import time
    path, _ = seq
    b = FlirFileBackend(path, realtime=True)                            # 15 fps in the file
    b.open()
    t0 = time.monotonic()
    for _ in range(4):
        b.read()
    assert 0.17 <= time.monotonic() - t0 < 0.6                          # 3 intervals of 1/15 s, not a spin


class TestPlugin:
    def setup_method(self):
        ffplugin.set_source(None)

    teardown_method = setup_method

    def test_registered_thermal_plugin_that_never_matches_without_a_source(self):
        p = get_registry().get_plugin("flir_file")
        assert p is not None and p.camera_role == CameraRole.THERMAL and p.detect() == []

    def test_detect_create_and_sdk(self, seq):
        path, _ = seq
        ffplugin.set_source(path)
        p = get_registry().get_plugin("flir_file")
        (m,) = p.detect()
        assert m.score >= 1000 and m.extra["path"].endswith("rec.seq")
        backend = p.create_backend(m)
        assert backend.open()
        sdk = p.create_sdk(m)
        assert sdk.connect() and "seek" in sdk.get_supported_commands()
        assert sdk.execute("get_camera_info")["frames"] == 3
        assert sdk.execute("seek", {"frame": 2})["frame"] == 2
        assert sdk.execute("set_loop", {"loop": False}) == {"success": True, "loop": False}
        assert sdk.execute("set_radiometric_mode", {"enabled": True}) == {"success": True}
        assert sdk.execute("set_radiometric_mode", {"enabled": False})["success"] is False
        assert sdk.execute("nope")["success"] is False
        assert p.get_capabilities(m).radiometric

    def test_chosen_file_outranks_live_cameras_in_discovery(self, seq):
        path, _ = seq
        ffplugin.set_source(path)
        matches = get_registry().discover(roles=[CameraRole.THERMAL])
        assert matches and matches[0].plugin_id == "flir_file"

    def test_wrong_extension_or_missing_file_does_not_match(self, tmp_path):
        p = get_registry().get_plugin("flir_file")
        bad = tmp_path / "a.mp4"
        bad.write_bytes(b"x")
        for path in (str(bad), str(tmp_path / "gone.seq")):
            ffplugin.set_source(path)
            assert p.detect() == []


class TestCommandLine:
    def parse(self, *argv):
        from thermal_inspection.cli import parse_arguments
        return parse_arguments(list(argv))

    def test_playback_file_implies_playback_mode_and_reaches_appconfig(self, seq):
        from thermal_inspection.app import AppConfig
        args = self.parse("--playback-file", seq[0])
        assert args.mode == "playback" and AppConfig.from_args(args).playback_file == seq[0]

    def test_bad_playback_arguments_are_rejected(self, tmp_path, capsys):
        for argv, message in ((["--mode", "playback"], "needs --playback-file"),
                              (["--playback-file", str(tmp_path / "x.csq")], "csq"),
                              (["--playback-file", str(tmp_path / "x.mp4")], ".seq or .fff"),
                              (["--playback-file", str(tmp_path / "missing.seq")], "not found")):
            with pytest.raises(SystemExit):
                self.parse(*argv)
            assert message in capsys.readouterr().err

    def test_default_launch_is_unchanged(self):
        args = self.parse()
        assert args.mode == "realtime" and args.playback_file is None


def test_old_flirpy_is_reported_not_crashed(monkeypatch, tmp_path):
    from thermal_inspection.sdk import flir_file_reader as r
    monkeypatch.setattr(r, "flirpy_version", lambda: (0, 3, 0))
    p = tmp_path / "a.seq"
    p.write_bytes(b"x")
    with pytest.raises(FlirFileError, match="flirpy >= 0.6"):
        FlirFileSource(str(p))
    assert FlirFileBackend(str(p)).is_available() is False
