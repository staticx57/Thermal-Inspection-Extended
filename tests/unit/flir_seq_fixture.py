"""
Builds synthetic FLIR .seq / .fff files for tests, following the layout flirpy's own parser reads (FFF header, record
directory, raw-image record, camera-info record with Planck constants), so the playback path can be tested without a
FLIR camera or a real recording. Frames are generated from known temperatures by inverting the Planck equation with
emissivity 1 and no atmosphere/window loss, so flirpy's raw2temp must give the temperatures back (to the sensor's
quantisation, ~0.02 C).
"""
import math
import struct

import numpy as np

R1, R2, B, F, O = 21106.77, 0.012545258, 1501.0, 1.0, -7340


def planck_raw(celsius):
    t = np.asarray(celsius, dtype=np.float64) + 273.15
    return np.rint(R1 / (R2 * (np.exp(B / t) - F)) - O).astype(np.uint16)


def _camera_info(width, height, fps, model=b"A315", serial=b"SN12345"):
    d = bytearray(0x470)
    struct.pack_into("<H", d, 0, 2)                      # little-endian marker flirpy checks
    struct.pack_into("<HH", d, 0x02, width, height)
    kelvin20 = 273.14 + 20.0
    for off, val in ((0x20, 1.0),                        # emissivity
                     (0x24, 1.0),                        # object distance (m)
                     (0x28, kelvin20), (0x2C, kelvin20), (0x30, kelvin20),
                     (0x34, 1.0),                        # IR window transmission
                     (0x3C, 0.5),                        # humidity
                     (0x58, R1), (0x5C, B), (0x60, F), (0x30C, R2),
                     (0x70, 0.0), (0x74, 0.0), (0x78, 0.0), (0x7C, 0.0),   # no atmospheric absorption
                     (0x80, 1.0),
                     (0x90, 273.14 + 150), (0x94, 273.14 - 20), (0x98, 273.14 + 150), (0x9C, 273.14 - 20),
                     (0xA0, 273.14 + 150), (0xA4, 273.14 - 20), (0xA8, 273.14 + 150), (0xAC, 273.14 - 20),
                     (0x1B4, 25.0), (0x45C, 1.0)):
        struct.pack_into("<f", d, off, val)
    struct.pack_into("<i", d, 0x308, int(O))
    struct.pack_into("<HH", d, 0x310, 0, 65535)
    struct.pack_into("<H", d, 0x338, 20000)
    struct.pack_into("<H", d, 0x33C, 40000)
    struct.pack_into("<I", d, 0x384, 1_700_000_000)
    struct.pack_into("<H", d, 0x390, 0)
    struct.pack_into("<H", d, 0x464, fps)
    for off, n, val in ((0xD4, 32, model), (0xF4, 16, b"PN-1"), (0x104, 16, serial), (0x114, 16, b"1.0"),
                        (0x170, 32, b"25 deg"), (0x190, 16, b"LPN"), (0x1A0, 16, b"LSN"),
                        (0x1EC, 16, b"F"), (0x1FC, 16, b"FP"), (0x21C, 16, b"FS")):
        d[off:off + n] = val.ljust(n, b"\x00")[:n]
    return bytes(d)


def fff_frame(celsius, fps=9, **info):
    """One FFF frame (bytes) whose image encodes the given Celsius field."""
    raw = planck_raw(celsius)
    h, w = raw.shape
    raw_record = bytearray(0x20)
    struct.pack_into("<H", raw_record, 0, 2)
    struct.pack_into("<HH", raw_record, 2, w, h)
    raw_record += raw.astype("<u2").tobytes()
    cam = _camera_info(w, h, fps, **info)

    dir_offset = 64
    records = [(0x01, bytes(raw_record)), (0x20, cam)]
    data_start = dir_offset + len(records) * 32
    out = bytearray()
    entries = []
    pos = data_start
    for rtype, blob in records:
        entries.append(struct.pack("<HHIIIIIII", rtype, 1, 100, 1, pos, len(blob), 0, 0, 0))
        out += blob
        pos += len(blob)
    header = struct.pack("<4s16sIIIIH7HIII", b"FFF\x00", b"CAMCTRL".ljust(16, b"\x00"), 100, dir_offset,
                         len(records), 2, 0, *([0] * 7), 0, 0, 0)
    assert len(header) == 64
    return header + b"".join(entries) + bytes(out)


def write_seq(path, frames_celsius, fps=9, **info):
    with open(path, "wb") as f:
        for c in frames_celsius:
            f.write(fff_frame(c, fps=fps, **info))


def write_fff(path, celsius, fps=9, **info):
    with open(path, "wb") as f:
        f.write(fff_frame(celsius, fps=fps, **info))


def gradient(h, w, lo, hi, offset=0.0):
    """A horizontal temperature ramp lo..hi (C) plus an optional constant."""
    return (np.tile(np.linspace(lo, hi, w), (h, 1)) + offset).astype(np.float64)
