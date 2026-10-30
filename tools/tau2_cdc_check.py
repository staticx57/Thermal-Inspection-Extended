"""Check a Tau 2 board's serial (CDC) control line with the same protocol code the app uses.

Read-only: it only sends NO-OP and GET commands, nothing is written to the camera.

  python tools/tau2_cdc_check.py --list-ports
  python tools/tau2_cdc_check.py --port COM5            (Linux: --port /dev/ttyACM0)
  python tools/tau2_cdc_check.py --port COM5 --baud 115200

Step 1 sends one raw NO-OP frame and prints the bytes that come back, so a framing, baud or CRC problem is visible
before any parsing.  Step 2 runs the app's own Tau2Serial class through a set of GET commands and prints PASS/FAIL
for each.  Exit code is 0 only if every check passes.

Needs: pip install pyserial   (run from anywhere; the repo root is added to the import path)
"""
from __future__ import annotations

import argparse
import binascii
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial
import serial.tools.list_ports


def noop_frame() -> bytes:
    """Process code 0x6E, status 0, reserved 0, function 0 (NO-OP), 0 argument bytes, CRC-CCITT of the first 6 bytes."""
    header = struct.pack(">BBBBH", 0x6E, 0x00, 0x00, 0x00, 0)
    return header + struct.pack(">H", binascii.crc_hqx(header, 0))


def list_ports() -> int:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return 1
    for p in ports:
        print(f"{p.device:12} {p.description}  [{p.hwid}]")
    return 0


def raw_step(port: str, baud: int) -> bool:
    frame = noop_frame()
    print(f"Step 1: raw NO-OP at {baud} 8N1 on {port}")
    print(f"  sent     {frame.hex(' ').upper()}")
    try:
        with serial.Serial(port, baud, bytesize=8, parity="N", stopbits=1, timeout=1.5) as ser:
            ser.reset_input_buffer()
            ser.write(frame)
            ser.flush()
            reply = ser.read(8)
    except serial.SerialException as e:
        print(f"  FAIL     could not open or use the port: {e}")
        return False
    if not reply:
        print("  FAIL     no reply (wrong port or baud, bridge not forwarding, or camera not powered)")
        return False
    print(f"  received {reply.hex(' ').upper()}")
    if len(reply) < 8:
        print("  FAIL     short reply (expected an 8-byte header)")
        return False
    crc_ok = struct.unpack(">H", reply[6:8])[0] == binascii.crc_hqx(reply[:6], 0)
    status = reply[1]
    print(f"  process code 0x{reply[0]:02X}, status 0x{status:02X}, header CRC {'ok' if crc_ok else 'BAD'}")
    ok = reply[0] == 0x6E and status == 0 and crc_ok
    print("  PASS" if ok else "  FAIL     reply is not a valid OK header (status 0x02 = camera not ready, retry)")
    return ok


def class_step(port: str, baud: int) -> bool:
    from thermal_inspection.sdk.tau2_serial import Tau2Serial

    print(f"\nStep 2: Tau2Serial class (the code the app uses) on {port} at {baud}")
    try:
        cam = Tau2Serial(port=port, baudrate=baud)
    except Exception as e:
        print(f"  FAIL     open: {e}")
        return False
    checks = [
        ("ping", cam.ping),
        ("serial number", cam.get_serial_number),
        ("firmware revision", cam.get_revision),
        ("gain mode", cam.get_gain_mode),
        ("FFC mode", cam.get_ffc_mode),
        ("AGC type", cam.get_agc_type),
        ("colour LUT", cam.get_color_lut),
        ("T-Linear mode", cam.get_tlinear_mode),
        ("FPA temperature", cam.get_fpa_temperature),
        ("housing temperature", cam.get_housing_temperature),
    ]
    passed = 0
    for name, fn in checks:
        try:
            value = fn()
            if name == "ping" and value is not True:
                raise RuntimeError("no valid reply")
            print(f"  PASS     {name}: {value}")
            passed += 1
        except Exception as e:
            print(f"  FAIL     {name}: {type(e).__name__}: {e}")
    cam.close()
    print(f"\n{passed}/{len(checks)} checks passed")
    return passed == len(checks)


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only check of a Tau 2 serial (CDC) control line")
    ap.add_argument("--port", help="serial port, e.g. COM5 or /dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=57600, help="default 57600 (the Tau 2 CCI default)")
    ap.add_argument("--list-ports", action="store_true", help="list serial ports and exit")
    args = ap.parse_args()
    if args.list_ports:
        return list_ports()
    if not args.port:
        ap.error("--port is required (use --list-ports to see what is available)")
    raw_ok = raw_step(args.port, args.baud)
    cls_ok = class_step(args.port, args.baud) if raw_ok else False
    if not raw_ok:
        print("\nSkipping step 2: fix the raw link first.")
    return 0 if raw_ok and cls_ok else 1


if __name__ == "__main__":
    sys.exit(main())
