"""
Native CCI extensions for flirpy's Boson class.

flirpy's own flirpy.camera.boson.Boson implements only a subset of the
Boson CCI command set (FFC, basic info, FPA temp, averager). Everything
else previously went through a second, independent connection to the
proprietary vendor BosonSDK (thermal_inspection.sdk.boson_sdk_wrapper) -
but flirpy.camera.core.Core.connect() opens its own exclusive
serial.Serial() handle in Boson.__init__ and holds it for the object's
whole life, so a second BosonSDK connection to the same COM port always
loses with "port already in use" while flirpy is active. This is not a
timing bug to work around - it's a hard exclusivity constraint on the
Windows COM port, confirmed live (SDK connect attempts against COM7
failed with "Failed to open port #6 with error 255!" the entire time a
FlirpyThermalBackend was streaming).

This module adds the missing commands as methods on a Boson subclass,
using flirpy's own _send_packet/_decode_packet primitives - the exact
same low-level CCI protocol flirpy already speaks for do_ffc() etc. - so
one already-open flirpy connection can do everything the control panel
needs, with no second connection at all.

Function IDs and payload formats are from FLIR's own Boson Software IDD
(102-2013-42, rev300; local copy at "3.0 IDD & SDK/
Boson_SDK_Documentation_rev300.pdf"), sections 1.4 (SYSCTRL/gain),
1.7 (COLORLUT), 1.19 (RADIOMETRY), 1.29 (SYSCTRL/video). Every value
below was verified live against a real -R unit (SN 138205) before being
trusted: read-only GETs matched the vendor SDK's own readings exactly
(emissivity 99.5%, atm_transmission 100%, atm_temp 295K, gain_mode=2/
AUTO, IR16 mode=2), and a SET/restore round-trip on emissivity and IR16
mode confirmed the payload encoding (big-endian, matching every other
flirpy Boson command) actually writes and reads back correctly.

Percent-vs-fraction note: the IDD documents emissivity and
atmospheric/window transmission as "(percentage)" - i.e. 0-100, not
0.0-1.0. This matches what boson_sdk_wrapper.py's live testing already
found for the vendor SDK path (see its set_emissivity/set_atmospheric_
transmission comments); callers here get the same 0-100 raw units, and
FlirpyThermalBackend converts to/from the app-wide 0.0-1.0 convention.
"""
from __future__ import annotations

import logging
import struct
from typing import Optional

from flirpy.camera.boson import Boson

logger = logging.getLogger(__name__)

# SYSCTRL / gain
_FID_GET_GAIN_MODE = 0x00050015
_FID_SET_GAIN_MODE = 0x00050014
_FID_SET_FFC_MODE = 0x00050012
_FID_GET_LENS_NUMBER = 0x00050039
_FID_GET_TABLE_NUMBER = 0x0005003B

# COLORLUT
_FID_SET_COLOR_LUT_ID = 0x000B0003

# SYSCTRL / USB video Y16 packing (0=16-bit raw, 1=14-bit raw, 2=T-Linear)
_FID_GET_IR16_MODE = 0x000E000E
_FID_SET_IR16_MODE = 0x000E000D

# RADIOMETRY
_FID_SET_RADIOMETRY_ENABLE = 0x00420000
_FID_GET_ATM_TEMP_K = 0x00420076
_FID_SET_ATM_TEMP_K = 0x00420075
_FID_GET_ATM_TRANSMISSION_PCT = 0x0042006E
_FID_SET_ATM_TRANSMISSION_PCT = 0x0042006D
_FID_GET_EMISSIVITY_PCT = 0x00420078
_FID_SET_EMISSIVITY_PCT = 0x00420077


class BosonNative(Boson):
    """flirpy's Boson, extended with the CCI commands it doesn't implement."""

    # -- generic helpers, mirroring flirpy's own command methods --------

    def _get_float(self, function_id: int) -> Optional[float]:
        res = self._send_packet(function_id, receive_size=4)
        res = self._decode_packet(res, receive_size=4)
        if res is not None and len(res) == 4:
            return struct.unpack(">f", res)[0]
        return None

    def _set_float(self, function_id: int, value: float) -> None:
        command = struct.pack(">f", value)
        res = self._send_packet(function_id, data=command)
        self._decode_packet(res)

    def _get_uint32(self, function_id: int) -> Optional[int]:
        res = self._send_packet(function_id, receive_size=4)
        res = self._decode_packet(res, receive_size=4)
        if res is not None and len(res) == 4:
            return struct.unpack(">I", res)[0]
        return None

    def _set_uint32(self, function_id: int, value: int) -> None:
        command = struct.pack(">I", value)
        res = self._send_packet(function_id, data=command)
        self._decode_packet(res)

    # -- gain / FFC mode / palette ---------------------------------------

    def get_gain_mode(self) -> Optional[int]:
        """0=HIGH, 1=LOW, 2=AUTO."""
        return self._get_uint32(_FID_GET_GAIN_MODE)

    def set_gain_mode(self, mode: int) -> None:
        self._set_uint32(_FID_SET_GAIN_MODE, mode)

    def set_ffc_mode(self, mode: int) -> None:
        """0=MANUAL, 1=AUTO, 2=EXTERNAL, 3=SHUTTER_TEST."""
        self._set_uint32(_FID_SET_FFC_MODE, mode)

    def set_color_lut_id(self, lut_id: int) -> None:
        """FLR_COLORLUT_ID_E value, e.g. 0=WHITEHOT, 1=BLACKHOT, 4=IRONBOW."""
        self._set_uint32(_FID_SET_COLOR_LUT_ID, lut_id)

    def get_lens_number(self) -> Optional[int]:
        return self._get_uint32(_FID_GET_LENS_NUMBER)

    def get_table_number(self) -> Optional[int]:
        return self._get_uint32(_FID_GET_TABLE_NUMBER)

    # -- USB video Y16 packing / T-Linear --------------------------------

    def get_usb_video_ir16_mode(self) -> Optional[int]:
        return self._get_uint32(_FID_GET_IR16_MODE)

    def set_usb_video_ir16_mode(self, mode: int) -> None:
        """0=16-bit raw, 1=14-bit raw, 2=T-Linear radiometric.

        Must be called before the video capture is set up (i.e. before the
        first grab()/setup_video()) - flirpy's __init__ only opens the
        serial connection, not video, so calling this right after
        construction and before any read() is the correct ordering.
        """
        self._set_uint32(_FID_SET_IR16_MODE, mode)

    # -- radiometry / environmental compensation -------------------------

    def set_radiometry_enable(self, enabled: bool) -> None:
        self._set_uint32(_FID_SET_RADIOMETRY_ENABLE, 1 if enabled else 0)

    def get_atmospheric_temperature_k(self) -> Optional[float]:
        return self._get_float(_FID_GET_ATM_TEMP_K)

    def set_atmospheric_temperature_k(self, kelvin: float) -> None:
        self._set_float(_FID_SET_ATM_TEMP_K, kelvin)

    def get_atmospheric_transmission_pct(self) -> Optional[float]:
        return self._get_float(_FID_GET_ATM_TRANSMISSION_PCT)

    def set_atmospheric_transmission_pct(self, percent: float) -> None:
        self._set_float(_FID_SET_ATM_TRANSMISSION_PCT, percent)

    def get_emissivity_pct(self) -> Optional[float]:
        return self._get_float(_FID_GET_EMISSIVITY_PCT)

    def set_emissivity_pct(self, percent: float) -> None:
        self._set_float(_FID_SET_EMISSIVITY_PCT, percent)
