"""
USB FSLP Transport Layer

Implements FLIR Serial Link Protocol (FSLP) over direct USB bulk transfers.
Allows sending SDK commands to Boson camera without using COM port.
"""

import time
import logging
from typing import Optional, Tuple
import usb.core
import usb.util

logger = logging.getLogger(__name__)


class USBFslpTransport:
    """
    FSLP protocol transport over USB bulk endpoints.

    Implements the same framing and CRC as PySerialFslp but uses USB
    bulk transfers instead of serial port communication.
    """

    # FSLP protocol constants
    START_FRAME_BYTE = 0x8E
    ESCAPE_BYTE = 0x9E
    END_FRAME_BYTE = 0xAE
    ESCAPED_START_FRAME_BYTE = 0x81
    ESCAPED_ESCAPE_BYTE = 0x91
    ESCAPED_END_FRAME_BYTE = 0xA1

    # CRC-16-CCITT lookup table (same as PySerialFslp)
    CCITT_16_TABLE = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
        0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
        0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
        0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
        0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
        0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
        0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
        0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
        0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
        0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
        0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
        0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
        0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
        0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
        0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
        0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
        0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
        0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
        0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
        0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
        0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
        0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
        0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
    ]

    def __init__(self, usb_device, ctrl_in_endpoint, ctrl_out_endpoint):
        """
        Initialize USB FSLP transport.

        Args:
            usb_device: PyUSB device object
            ctrl_in_endpoint: Control interface IN endpoint address
            ctrl_out_endpoint: Control interface OUT endpoint address
        """
        self.dev = usb_device
        self.ctrl_in_ep = ctrl_in_endpoint
        self.ctrl_out_ep = ctrl_out_endpoint
        self.read_timeout = 5000  # 5 seconds in milliseconds
        self.write_timeout = 1000  # 1 second

    def _byte_crc16(self, value: int, crcin: int) -> int:
        """Calculate CRC-16-CCITT for a single byte."""
        bottom_byte = (crcin << 8) & 0xFFFF
        top_byte = (crcin >> 8) & 0xFFFF
        value = value & 0xFF
        tbl_index = top_byte ^ value & 0xFF
        crcout = bottom_byte ^ self.CCITT_16_TABLE[tbl_index]
        return crcout

    def _calc_crc16_bytes(self, buffer: bytes) -> int:
        """Calculate CRC-16-CCITT for byte array."""
        crc = 0x1d0f
        for cur_byte in buffer:
            crc = self._byte_crc16(cur_byte, crc)
        return crc

    def sendFrame(self, channelID: int, data: bytearray, dataSize: int):
        """
        Send FSLP frame via USB bulk transfer.

        Args:
            channelID: FSLP channel (0x00 for command channel)
            data: Payload data
            dataSize: Size of payload
        """
        # Build unescaped payload: [channelID][data][CRC-16]
        temppayload = bytearray([channelID])
        temppayload.extend(data[:dataSize])

        # Calculate CRC-16 for payload
        payload_crc = self._calc_crc16_bytes(temppayload)
        temppayload.append((payload_crc >> 8) & 0xFF)
        temppayload.append(payload_crc & 0xFF)

        # Build escaped packet: [START][escaped_payload][END]
        packet = bytearray([self.START_FRAME_BYTE])

        # Escape special bytes in payload
        for byte in temppayload:
            if byte == self.START_FRAME_BYTE:
                packet.extend([self.ESCAPE_BYTE, self.ESCAPED_START_FRAME_BYTE])
            elif byte == self.END_FRAME_BYTE:
                packet.extend([self.ESCAPE_BYTE, self.ESCAPED_END_FRAME_BYTE])
            elif byte == self.ESCAPE_BYTE:
                packet.extend([self.ESCAPE_BYTE, self.ESCAPED_ESCAPE_BYTE])
            else:
                packet.append(byte)

        packet.append(self.END_FRAME_BYTE)

        # Send via USB bulk OUT
        try:
            bytes_written = self.dev.write(self.ctrl_out_ep, packet, self.write_timeout)
            logger.debug(f"Sent {bytes_written} bytes via USB (FSLP frame)")
        except usb.core.USBError as e:
            logger.error(f"USB write error: {e}")
            raise

    def readFrame(self, channelID: int, expectedReceiveBytes: int) -> bytearray:
        """
        Read FSLP frame via USB bulk transfer.

        Args:
            channelID: Expected channel ID
            expectedReceiveBytes: Expected data bytes (excluding header/CRC)

        Returns:
            bytearray: Received data (no channel ID, no CRC)

        Raises:
            Exception: On timeout, CRC mismatch, or wrong channel
        """
        packet = bytearray()
        inFrame = False
        escapeNext = False
        start_time = time.time()

        # Read bytes from USB until we have a complete frame
        while True:
            # Check for timeout
            if (time.time() - start_time) > self.read_timeout / 1000.0:
                raise Exception("Timeout in readFrame")

            try:
                # Read up to 512 bytes at a time from USB
                data = self.dev.read(self.ctrl_in_ep, 512, self.read_timeout)

                # Process each byte
                for byte_val in data:
                    if byte_val == self.START_FRAME_BYTE and not escapeNext:
                        inFrame = True
                        packet = bytearray()  # Reset packet on new frame start
                        escapeNext = False
                        continue

                    if inFrame:
                        if escapeNext:
                            # Previous byte was escape, unescape this one
                            if byte_val == self.ESCAPED_START_FRAME_BYTE:
                                packet.append(self.START_FRAME_BYTE)
                            elif byte_val == self.ESCAPED_END_FRAME_BYTE:
                                packet.append(self.END_FRAME_BYTE)
                            elif byte_val == self.ESCAPED_ESCAPE_BYTE:
                                packet.append(self.ESCAPE_BYTE)
                            else:
                                raise Exception("Packet corrupt. Improperly escaped bytes encountered.")
                            escapeNext = False
                        elif byte_val == self.ESCAPE_BYTE:
                            # Next byte will be escaped
                            escapeNext = True
                        elif byte_val == self.END_FRAME_BYTE:
                            # Frame complete, exit both loops
                            inFrame = False
                            break
                        else:
                            # Normal data byte
                            packet.append(byte_val)

                # Check if frame is complete
                if not inFrame and len(packet) > 0:
                    break

            except usb.core.USBError as e:
                if e.errno == 60:  # Timeout
                    continue  # Keep trying
                else:
                    logger.error(f"USB read error: {e}")
                    raise

        # Verify we have enough data
        if len(packet) < 3:
            raise Exception(f"Packet too short (got {len(packet)} bytes)")

        # Verify CRC
        packet_crc = self._calc_crc16_bytes(packet[:-2])
        packet_crc_bytes = bytes([packet_crc >> 8, packet_crc & 0x00FF])
        received_crc = bytes([packet[-2], packet[-1]])

        if packet_crc_bytes != received_crc:
            raise Exception(f"Packet corrupt. CRC doesn't match (expected: {packet_crc_bytes.hex()}, got: {received_crc.hex()})")

        # Verify channel ID
        if packet[0] != channelID:
            raise Exception(f"Response for wrong channel received (expected: {channelID}, got: {packet[0]})")

        # Verify length
        data_length = len(packet) - 3  # Subtract channel ID (1) + CRC (2)
        if data_length != expectedReceiveBytes:
            raise Exception(f"Did not receive expected number of bytes (expected: {expectedReceiveBytes}, got: {data_length})")

        # Return data only (no channel ID, no CRC)
        return packet[1:-2]


class USBFslpPort:
    """
    Wrapper to make USBFslpTransport compatible with SDK's port interface.

    The SDK expects a 'port' object with isOpen() method.
    """

    def __init__(self, usb_device, ctrl_in_endpoint, ctrl_out_endpoint):
        self.transport = USBFslpTransport(usb_device, ctrl_in_endpoint, ctrl_out_endpoint)
        self._is_open = True

    def isOpen(self) -> bool:
        """Check if port is open."""
        return self._is_open

    def open(self):
        """Open port (no-op for USB, already open)."""
        self._is_open = True

    def close(self):
        """Close port."""
        self._is_open = False

    def sendFrame(self, channelID: int, data: bytearray, dataSize: int):
        """Send FSLP frame."""
        return self.transport.sendFrame(channelID, data, dataSize)

    def readFrame(self, channelID: int, expectedReceiveBytes: int) -> bytearray:
        """Read FSLP frame."""
        return self.transport.readFrame(channelID, expectedReceiveBytes)
