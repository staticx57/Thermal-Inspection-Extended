"""
GigE Vision Control Protocol (GVCP) Pure-Python Implementation.

Implements UDP-based device discovery (Port 3956), ForceIP configuration,
and bootstrap register access according to the AIA GigE Vision Standard.
"""
from __future__ import annotations

import socket
import struct
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

GVCP_PORT = 3956
GVCP_MAGIC = 0x42

# GVCP Command Codes
CMD_DISCOVERY_CMD = 0x0002
CMD_DISCOVERY_ACK = 0x0003
CMD_FORCEIP_CMD   = 0x0004
CMD_FORCEIP_ACK   = 0x0005
CMD_READREG_CMD   = 0x0080
CMD_READREG_ACK   = 0x0081
CMD_WRITEREG_CMD  = 0x0082
CMD_WRITEREG_ACK  = 0x0083


@dataclass
class GigEDeviceInfo:
    """Discovered GigE Vision Camera Metadata."""
    ip_address: str
    subnet_mask: str
    gateway: str
    mac_address: str
    manufacturer: str
    model: str
    serial_number: str
    user_name: str
    version: str
    is_thermal: bool = False
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return f"{self.manufacturer} {self.model} ({self.ip_address})"


class GVCPProtocol:
    """GVCP client for broadcast discovery and camera configuration."""

    def __init__(self, timeout: float = 1.0):
        self.timeout = timeout
        self._req_id = 1

    def _next_req_id(self) -> int:
        req = self._req_id
        self._req_id = (self._req_id + 1) & 0xFFFF
        if self._req_id == 0:
            self._req_id = 1
        return req

    def discover_devices(self) -> List[GigEDeviceInfo]:
        """
        Broadcast DISCOVERY_CMD across all network interfaces on UDP port 3956.
        Returns a list of all responding GigE Vision cameras.
        """
        devices: List[GigEDeviceInfo] = []
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(self.timeout)

        # Build GVCP Discovery Packet
        # Header: Magic(1B) | Flags(1B) | Command(2B) | Length(2B) | ReqID(2B)
        # Flags = 0x01 (ACK required) or 0x00 (Broadcast)
        req_id = self._next_req_id()
        packet = struct.pack(">BBHHH", GVCP_MAGIC, 0x01, CMD_DISCOVERY_CMD, 0, req_id)

        try:
            # Broadcast to 255.255.255.255
            sock.sendto(packet, ('<broadcast>', GVCP_PORT))

            # Collect all incoming responses until timeout
            while True:
                try:
                    data, addr = sock.recvfrom(2048)
                    if len(data) >= 8:
                        dev = self._parse_discovery_ack(data, addr[0])
                        if dev:
                            # Avoid duplicates from multi-homed broadcast
                            if not any(d.mac_address == dev.mac_address for d in devices):
                                devices.append(dev)
                except TimeoutError:
                    break
                except Exception as e:
                    logger.debug(f"Error receiving GVCP packet: {e}")
                    break

        except Exception as exc:
            logger.debug(f"GVCP broadcast failed: {exc}")
        finally:
            sock.close()

        return devices

    def _parse_discovery_ack(self, data: bytes, source_ip: str) -> Optional[GigEDeviceInfo]:
        """Parse DISCOVERY_ACK response packet."""
        try:
            # Header check: Magic=0x00 (ACK status), Command=0x0003
            # In ACK header: Status(2B) | Command(2B) | Length(2B) | ReqID(2B)
            status, cmd, length, req_id = struct.unpack(">HHHH", data[:8])
            if cmd != CMD_DISCOVERY_ACK:
                return None

            payload = data[8:]
            if len(payload) < 216:
                return None

            # Spec Version Major (2B), Minor (2B), DeviceMode (4B)
            # MAC Address: MAC High (2B) + MAC Low (4B)
            mac_high, mac_low = struct.unpack(">HI", payload[8:14])
            mac_bytes = struct.pack(">HI", mac_high, mac_low)
            mac_str = ":".join(f"{b:02X}" for b in mac_bytes)

            # IP Settings: IP Config(4B), Current IP(4B), Subnet(4B), Gateway(4B)
            curr_ip_int, subnet_int, gw_int = struct.unpack(">III", payload[24:36])
            curr_ip = socket.inet_ntoa(struct.pack(">I", curr_ip_int))
            subnet = socket.inet_ntoa(struct.pack(">I", subnet_int))
            gateway = socket.inet_ntoa(struct.pack(">I", gw_int))

            # String fields:
            # Manufacturer Name (32B, offset 36)
            # Model Name (32B, offset 68)
            # Device Version (32B, offset 100)
            # Manufacturer Specific (48B, offset 132)
            # Serial Number (16B, offset 180)
            # User Defined Name (16B, offset 196)
            manuf = payload[36:68].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
            model = payload[68:100].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
            version = payload[100:132].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
            serial = payload[180:196].split(b'\x00')[0].decode('ascii', errors='ignore').strip()
            user_name = payload[196:212].split(b'\x00')[0].decode('ascii', errors='ignore').strip()

            # Determine if this is a thermal camera (e.g. FLIR A35/A65/A300/A310, Optris, etc.)
            is_thermal = any(term in (manuf + " " + model).lower() for term in ["thermal", "flir a", "optris", "infrared", "lwir", "mwir"])

            return GigEDeviceInfo(
                ip_address=curr_ip if curr_ip != "0.0.0.0" else source_ip,
                subnet_mask=subnet,
                gateway=gateway,
                mac_address=mac_str,
                manufacturer=manuf or "GigE Vision Camera",
                model=model or "Generic GigE",
                serial_number=serial or "N/A",
                user_name=user_name or "",
                version=version or "1.0",
                is_thermal=is_thermal
            )

        except Exception as e:
            logger.debug(f"Failed to parse DISCOVERY_ACK: {e}")
            return None

    def force_ip(self, mac_address: str, new_ip: str, subnet: str, gateway: str) -> bool:
        """
        Send FORCEIP_CMD to temporarily reconfigure a camera's IP to match local subnet.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(self.timeout)

        try:
            mac_clean = mac_address.replace(":", "").replace("-", "")
            mac_bytes = bytes.fromhex(mac_clean)
            if len(mac_bytes) != 6:
                return False

            ip_bytes = socket.inet_aton(new_ip)
            sub_bytes = socket.inet_aton(subnet)
            gw_bytes = socket.inet_aton(gateway)

            # Payload structure for FORCEIP_CMD (offset 8 onward, total 64 bytes)
            # Reserved (2B) | MAC High (2B) | Reserved (2B) | MAC Low (4B) | Reserved (12B) | StaticIP (4B) | StaticSubnet (4B) | StaticGW (4B)
            payload = struct.pack(">HHHI", 0x0000, struct.unpack(">H", mac_bytes[:2])[0], 0x0000, struct.unpack(">I", mac_bytes[2:])[0])
            payload += b'\x00' * 12
            payload += ip_bytes + sub_bytes + gw_bytes
            payload += b'\x00' * (64 - len(payload))

            req_id = self._next_req_id()
            header = struct.pack(">BBHHH", GVCP_MAGIC, 0x01, CMD_FORCEIP_CMD, len(payload), req_id)
            sock.sendto(header + payload, ('<broadcast>', GVCP_PORT))

            # Await FORCEIP_ACK
            data, _ = sock.recvfrom(512)
            if len(data) >= 8:
                status, cmd, _, ack_req_id = struct.unpack(">HHHH", data[:8])
                return status == 0x0000 and cmd == CMD_FORCEIP_ACK and ack_req_id == req_id

            return False

        except Exception as e:
            logger.error(f"ForceIP failed: {e}")
            return False
        finally:
            sock.close()


def discover_gige_cameras() -> List[GigEDeviceInfo]:
    """Helper function to discover all GigE cameras on the network."""
    return GVCPProtocol().discover_devices()


def force_gige_ip(mac: str, ip: str, subnet: str = "255.255.255.0", gateway: str = "0.0.0.0") -> bool:
    """Helper function to set camera IP using ForceIP."""
    return GVCPProtocol().force_ip(mac, ip, subnet, gateway)
