"""BosonNative against flirpy's REAL framing code (whichever flirpy is installed) and a simulated Boson on the wire.
A flirpy upgrade that changes the FSLP packet handling the extension relies on fails here instead of on hardware."""
import binascii
import logging
import struct

import pytest

pytest.importorskip("flirpy")
from thermal_inspection.sdk import boson_flirpy_ext as ext


class SimulatedBoson:
    """Just enough of a serial port + camera: answers CCI get/set commands from a register file."""

    def __init__(self, boson):
        self.boson = boson
        self.regs = {}
        self.sent = []
        self._reply = b""

    def write(self, data):
        data = bytes(data)
        # request: 8E ch seq(4) fid(4) 0xFFFFFFFF payload(bitstuffed) crc(2) AE
        fid = struct.unpack(">I", data[6:10])[0]
        body = data[14:-3]
        payload = self.boson._unstuff(body) if body else b""
        self.sent.append((fid, payload))
        if payload:                                        # a SET
            self.regs[fid] = payload
            reply_payload = b""
        else:                                              # a GET: the matching SET fid is the one below
            reply_payload = self.regs.get(fid - 1, b"\x00\x00\x00\x00")
        header = bytearray(struct.pack(">BBIII", 0x8E, 0, 0, fid, 0))
        crc = binascii.crc_hqx(bytes(header[1:]) + reply_payload, 0x1D0F)
        # a real camera escapes marker bytes in the payload AND in the CRC; flirpy's decoder unstuffs both
        stuffed = bytes(self.boson._bitstuff(reply_payload + struct.pack(">H", crc)))
        self._reply = bytes(header) + stuffed + bytes([0xAE])

    def read(self, n):
        out, self._reply = self._reply[:n] if len(self._reply) > n else self._reply, self._reply[n:] if len(self._reply) > n else b""
        return out

    def read_all(self):
        out, self._reply = self._reply, b""
        return out

    def flush(self):
        pass

    def reset_input_buffer(self):
        self._reply = b""


@pytest.fixture
def boson():
    b = ext.BosonNative.__new__(ext.BosonNative)
    b.command_count = 0
    b.logger = logging.getLogger("flirpy-test")
    b.conn = SimulatedBoson(b)
    b.send = lambda payload: b.conn.write(payload)     # the transport hop; framing above it is flirpy's own
    return b


def test_gain_mode_round_trips(boson):
    boson.set_gain_mode(1)
    assert boson.conn.sent[-1] == (0x00050014, struct.pack(">I", 1))
    assert boson.get_gain_mode() == 1


def test_emissivity_and_atmosphere_round_trip_through_real_framing(boson):
    boson.set_emissivity_pct(95.0)
    assert boson.get_emissivity_pct() == pytest.approx(95.0)
    boson.set_atmospheric_temperature_k(293.15)
    assert boson.get_atmospheric_temperature_k() == pytest.approx(293.15, abs=1e-3)
    boson.set_usb_video_ir16_mode(2)
    assert boson.get_usb_video_ir16_mode() == 2


def test_payload_with_frame_marker_bytes_survives_bitstuffing(boson):
    # a value whose big-endian bytes contain 0x8E / 0xAE / 0x9E must be escaped on the wire and restored
    boson.set_color_lut_id(0x8EAE9E00)
    assert boson.conn.sent[-1][1] == struct.pack(">I", 0x8EAE9E00)
    boson.set_gain_mode(0x8E9EAE00)
    assert boson.get_gain_mode() == 0x8E9EAE00


def test_opencv_mixed_install_is_reported(monkeypatch):
    from importlib import metadata
    from thermal_inspection import cli

    def fake(versions):
        def version(name):
            if name in versions:
                return versions[name]
            raise metadata.PackageNotFoundError(name)
        return version

    monkeypatch.setattr(metadata, "version", fake({"opencv-python": "4.12.0.88", "opencv-python-headless": "5.0.0.93"}))
    assert len(cli.check_opencv_packages()) == 1
    monkeypatch.setattr(metadata, "version", fake({"opencv-python": "5.0.0.93", "opencv-python-headless": "5.0.0.93"}))
    assert cli.check_opencv_packages() == []
    monkeypatch.setattr(metadata, "version", fake({"opencv-python": "4.12.0.88"}))
    assert cli.check_opencv_packages() == []
