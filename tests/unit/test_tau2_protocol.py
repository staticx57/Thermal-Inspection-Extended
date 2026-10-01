"""Tau 2 CCI: our Tau2Serial against flirpy's independent implementation and the Tau 2 IDD facts.

The previous function-code table was wrong in several places (AGC at 0x0E = FFC temperature delta, digital output at
0x11 = video orientation, shutter position at 0x1E = LENS NUMBER, READ_SENSOR at 0x4E, a Boson-style gain enum), so a
write on a real camera would have changed an unrelated setting. These tests pin the corrected table to flirpy's.
"""
import binascii
import struct

import pytest

from thermal_inspection.sdk import tau2_serial as t2
from thermal_inspection.sdk.tau2_serial import Tau2Serial, Tau2StatusError


class FakeSerial:
    """A serial port that records writes and answers with a canned Tau response."""

    def __init__(self):
        self.written = b""
        self._rx = b""
        self.is_open = True

    def queue_response(self, func, payload=b"", status=0):
        header = struct.pack(">BBBBH", 0x6E, status, 0x00, func, len(payload))
        out = header + struct.pack(">H", binascii.crc_hqx(header, 0))
        if payload:
            out += payload + struct.pack(">H", binascii.crc_hqx(payload, 0))
        self._rx += out

    def write(self, data):
        self.written += bytes(data)

    def read(self, n):
        out, self._rx = self._rx[:n], self._rx[n:]
        return out

    def reset_input_buffer(self):
        self._rx_backup = self._rx

    def flush(self):
        pass

    def close(self):
        self.is_open = False


@pytest.fixture
def tau():
    t = Tau2Serial.__new__(Tau2Serial)
    t.port, t.baudrate, t.timeout = "FAKE", 57600, 1.0
    t.ser = FakeSerial()
    return t


def answer(tau, func, payload=b"", status=0):
    """Queue the camera's reply; reset_input_buffer in send_command must not discard it."""
    tau.ser.queue_response(func, payload, status)
    tau.ser.reset_input_buffer = lambda: None


class TestTableMatchesTheIdd:
    def test_status_codes(self):
        assert (t2.STATUS_CAM_OK, t2.STATUS_CAM_NOT_READY, t2.STATUS_CAM_RANGE_ERROR, t2.STATUS_CAM_UNDEFINED_ERROR,
                t2.STATUS_CAM_TIMEOUT_ERROR, t2.STATUS_CAM_BYTE_COUNT_ERROR, t2.STATUS_CAM_FEATURE_NOT_ENABLED) == \
               (0x00, 0x02, 0x03, 0x04, 0x07, 0x09, 0x0A)

    def test_function_codes(self):
        assert (t2.CMD_GAIN_MODE, t2.CMD_FFC_MODE, t2.CMD_DO_FFC, t2.CMD_COLOR_LUT) == (0x0A, 0x0B, 0x0C, 0x10)
        assert t2.CMD_DIGITAL_OUTPUT_MODE == 0x12 and t2.CMD_AGC_TYPE == 0x13
        assert t2.CMD_READ_SENSOR == 0x20 and t2.CMD_SHUTTER_POSITION == 0x79 and t2.CMD_TLINEAR == 0x8E
        assert t2.CMD_LENS_NUMBER == 0x1E and t2.CMD_BAUD_RATE == 0x07
        # nothing we send may share a code with a different setting
        written = [t2.CMD_GAIN_MODE, t2.CMD_FFC_MODE, t2.CMD_DO_FFC, t2.CMD_COLOR_LUT, t2.CMD_AGC_TYPE,
                   t2.CMD_SHUTTER_POSITION, t2.CMD_TLINEAR, t2.CMD_TEST_PATTERN]
        assert t2.CMD_LENS_NUMBER not in written and len(set(written)) == len(written)

    def test_gain_mode_values_are_the_tau_ones_not_the_bosons(self):
        assert (t2.GainMode.AUTO, t2.GainMode.LOW, t2.GainMode.HIGH, t2.GainMode.MANUAL) == (0, 1, 2, 3)

    def test_tlinear_resolutions(self):
        assert t2.TLINEAR_KELVIN_PER_COUNT == {True: 0.04, False: 0.4}


class TestPacketsMatchFlirpy:
    @pytest.fixture
    def flirpy_tau(self):
        pytest.importorskip("flirpy")
        pytest.importorskip("pyftdi")
        from flirpy.camera import tau as ft

        class Conn:
            sent = b""

            def write(self, data):
                self.sent += bytes(data)

            def flush(self):
                pass

        t = ft.Tau.__new__(ft.Tau)
        t.conn = Conn()
        return t, ft

    def ours(self, tau, func, arg=b""):
        answer(tau, func)
        try:
            tau.send_command(func, arg)
        except Exception:
            pass
        return tau.ser.written

    @pytest.mark.parametrize("name,func,arg", [
        ("NO_OP", t2.CMD_NO_OP, b""),
        ("SET_GAIN_MODE", t2.CMD_GAIN_MODE, struct.pack(">H", 2)),
        ("SET_FFC_MODE", t2.CMD_FFC_MODE, struct.pack(">H", 1)),
        ("DO_FFC_SHORT", t2.CMD_DO_FFC, b""),
        ("SET_SHUTTER_POSITION", t2.CMD_SHUTTER_POSITION, struct.pack(">H", 1)),
        ("READ_SENSOR_TEMPERATURE", t2.CMD_READ_SENSOR, struct.pack(">H", 0x0000)),
        ("SET_TEST_PATTERN", t2.CMD_TEST_PATTERN, struct.pack(">H", 1)),
    ])
    def test_same_bytes_on_the_wire(self, tau, flirpy_tau, name, func, arg):
        ft_tau, ft = flirpy_tau
        command = getattr(ft.ptc, name)
        assert command.code == func, f"{name}: flirpy uses 0x{command.code:02X}, we use 0x{func:02X}"
        ft_tau._send_packet(command, arg if arg else [])
        theirs, ours = ft_tau.conn.sent, self.ours(tau, func, arg)
        if arg:
            assert theirs == ours
        else:
            # flirpy pads argument-less commands with three extra zero bytes; the IDD packet is header + CRC1 only
            # (8 bytes), which is what we send. The meaningful part is identical.
            assert theirs[:len(ours)] == ours and set(theirs[len(ours):]) <= {0} and len(ours) == 8


class TestCommands:
    def test_temperatures_use_the_cameras_units(self, tau):
        answer(tau, t2.CMD_READ_SENSOR, struct.pack(">h", 253))                # 25.3 C in 0.1 C
        assert tau.get_fpa_temperature() == pytest.approx(25.3)
        assert tau.ser.written[3] == 0x20 and tau.ser.written[8:10] == struct.pack(">H", 0x0000)
        tau.ser.written = b""
        answer(tau, t2.CMD_READ_SENSOR, struct.pack(">h", 3125))               # 31.25 C in 0.01 C
        assert tau.get_housing_temperature() == pytest.approx(31.25)
        assert tau.ser.written[8:10] == struct.pack(">H", 0x000A)

    def test_negative_fpa_temperature(self, tau):
        answer(tau, t2.CMD_READ_SENSOR, struct.pack(">h", -50))
        assert tau.get_fpa_temperature() == pytest.approx(-5.0)

    def test_core_status_flags(self, tau):
        answer(tau, t2.CMD_READ_SENSOR, struct.pack(">H", (1 << 2) | (1 << 6)))
        s = tau.get_core_status()
        assert s["needs_ffc"] and s["ffc_in_progress"] and not s["overtemp"] and not s["suggest_gain_switch"]
        assert tau.ser.written[8:10] == struct.pack(">H", 0x0011)

    def test_tlinear_resolution_uses_the_idd_subcommand(self, tau):
        answer(tau, t2.CMD_TLINEAR)
        assert tau.set_tlinear_resolution(True)
        assert tau.ser.written[3] == 0x8E and tau.ser.written[8:12] == struct.pack(">HH", 0x0010, 1)
        tau.ser.written = b""
        answer(tau, t2.CMD_TLINEAR, struct.pack(">H", 0))
        assert tau.get_tlinear_resolution() is False
        assert tau.ser.written[8:10] == struct.pack(">H", 0x0010)

    def test_tlinear_cannot_be_switched_off_through_this_command(self, tau):
        assert tau.set_tlinear_mode(False) is False and tau.ser.written == b""

    def test_gain_mode_sends_the_tau_value(self, tau):
        from thermal_inspection.cameras.plugins.tau2.plugin import Tau2CameraSDK
        sdk = Tau2CameraSDK(com_port="FAKE")
        sdk.serial, sdk._is_connected = tau, True
        answer(tau, t2.CMD_GAIN_MODE)
        assert sdk.execute("set_gain_mode", {"mode": "high"})["success"]
        assert tau.ser.written[8:10] == struct.pack(">H", 2)                    # HIGH is 2 on a Tau, not the Boson's 0

    def test_status_errors_say_what_they_mean(self, tau):
        answer(tau, t2.CMD_NO_OP, status=t2.STATUS_CAM_NOT_READY)
        with pytest.raises(Tau2StatusError, match="not ready"):
            tau.send_command(t2.CMD_NO_OP)
        answer(tau, t2.CMD_GAIN_MODE, status=t2.STATUS_CAM_FEATURE_NOT_ENABLED)
        with pytest.raises(Tau2StatusError, match="not enabled"):
            tau.send_command(t2.CMD_GAIN_MODE)

    def test_plugin_exposes_the_new_commands(self):
        from thermal_inspection.cameras.plugins.tau2.plugin import Tau2CameraSDK
        assert {"get_core_status", "set_test_pattern"} <= set(Tau2CameraSDK().get_supported_commands())
