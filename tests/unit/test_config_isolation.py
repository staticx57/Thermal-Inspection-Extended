"""
Regression test for a shared-mutable-default bug found during a general
best-practices audit (2026-09-03): Config.__init__ built self.config via
DEFAULT_CONFIG.copy() - a shallow copy. DEFAULT_CONFIG nests mutable
objects (rgb_resolution/thermal_resolution lists, the serial_ports
dict-of-dicts), so every Config instance shared the SAME underlying list/
dict objects. No in-place mutation existed anywhere in the codebase at
the time this was found, so it was a latent footgun rather than a live
bug - but any future ".append()" or item assignment on one instance's
config would have silently corrupted DEFAULT_CONFIG for every other
instance created for the rest of the process.
"""
import pytest

from thermal_inspection.utils.config import Config


@pytest.mark.unit
class TestConfigInstanceIsolation:

    def test_mutating_one_instances_list_does_not_affect_another(self, tmp_path):
        config_a = Config(config_file=str(tmp_path / "a.json"))
        config_b = Config(config_file=str(tmp_path / "b.json"))

        config_a.config["rgb_resolution"].append(999)

        assert config_b.config["rgb_resolution"] == [640, 480]
        assert Config.DEFAULT_CONFIG["rgb_resolution"] == [640, 480]

    def test_mutating_one_instances_nested_dict_does_not_affect_another(self, tmp_path):
        config_a = Config(config_file=str(tmp_path / "a.json"))
        config_b = Config(config_file=str(tmp_path / "b.json"))

        config_a.config["serial_ports"]["flir_boson"]["port"] = "COM99"

        assert config_b.config["serial_ports"]["flir_boson"]["port"] == "COM7"
        assert Config.DEFAULT_CONFIG["serial_ports"]["flir_boson"]["port"] == "COM7"
