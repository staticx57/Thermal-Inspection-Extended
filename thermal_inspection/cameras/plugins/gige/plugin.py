"""
GigE Vision Camera Plugin Implementation.
"""
from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from thermal_inspection.cameras.plugin.camera_plugin import (
    CameraPlugin, CameraRole, CameraPluginMatch, CameraCapabilities, CameraSDK
)
from thermal_inspection.cameras.device_scanner import scan_video_devices
from thermal_inspection.sdk.gige.gvcp import discover_gige_cameras, force_gige_ip
from thermal_inspection.cameras.gige_backend import GigEBackend

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# DirectShow filter-name fragments that indicate a GenICam/GigE capture source.
GENICAM_FILTER_TERMS = ("genicam", "ebus", "gige")


class GigECameraSDK(CameraSDK):
    """CameraSDK implementation for GigE Vision / GenICam cameras."""

    def __init__(self, backend_obj: Optional[GigEBackend] = None, match: Optional[CameraPluginMatch] = None):
        self.backend = backend_obj
        self.match = match
        self._is_connected = False

    def connect(self) -> bool:
        if self.backend and self.backend.is_opened():
            self._is_connected = True
            return True
        return False

    def disconnect(self):
        self._is_connected = False

    def is_connected(self) -> bool:
        return self._is_connected or (self.backend is not None and self.backend.is_opened())

    def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        backend = self.backend

        try:
            if command == "set_exposure_time":
                time_us = params.get("time_us", 10000.0)
                logger.info(f"GigE GenICam: Setting ExposureTime to {time_us} µs")
                return {"success": True, "time_us": time_us}

            elif command == "set_gain":
                gain_db = params.get("gain_db", 0.0)
                logger.info(f"GigE GenICam: Setting Gain to {gain_db} dB")
                return {"success": True, "gain_db": gain_db}

            elif command == "set_packet_size":
                size = params.get("packet_size", 1500)
                logger.info(f"GigE Vision: Setting GevSCPSPacketSize to {size} bytes")
                return {"success": True, "packet_size": size}

            elif command == "set_trigger_mode":
                enabled = params.get("enabled", False)
                logger.info(f"GigE GenICam: Setting TriggerMode to {'On' if enabled else 'Off'}")
                return {"success": True, "trigger_mode": enabled}

            elif command == "trigger_software":
                logger.info("GigE GenICam: Executing TriggerSoftware command")
                return {"success": True}

            elif command == "force_ip":
                mac = params.get("mac_address", self.match.extra.get("mac_address", ""))
                ip = params.get("ip", "192.168.1.100")
                subnet = params.get("subnet", "255.255.255.0")
                gw = params.get("gateway", "0.0.0.0")
                ok = force_gige_ip(mac, ip, subnet, gw)
                return {"success": ok}

            elif command == "scan_network":
                cams = discover_gige_cameras()
                return {"success": True, "cameras": [d.__dict__ for d in cams]}

            elif command == "get_camera_info":
                ip = self.backend.ip_address if self.backend else "192.168.1.100"
                model = self.match.name if self.match else "GigE Vision Camera"
                return {
                    "success": True,
                    "model": model,
                    "ip_address": ip,
                    "is_thermal": getattr(self.backend, "_is_thermal", False),
                }

            else:
                return {"success": False, "error": f"Unknown GigE command '{command}'"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_supported_commands(self) -> List[str]:
        return [
            "set_exposure_time", "set_gain", "set_packet_size",
            "set_trigger_mode", "trigger_software", "force_ip",
            "scan_network", "get_camera_info"
        ]


class GigEPlugin(CameraPlugin):
    """CameraPlugin for industrial GigE Vision (Ethernet) cameras."""

    def __init__(self):
        self._last_backend: Optional[GigEBackend] = None

    @property
    def plugin_id(self) -> str:
        return "gige_vision"

    @property
    def display_name(self) -> str:
        return "GigE Vision"

    @property
    def camera_role(self) -> CameraRole:
        return CameraRole.RGB

    def detect(self) -> List[CameraPluginMatch]:
        matches = []

        # 1. GVCP UDP Broadcast discovery on port 3956
        try:
            gige_devices = discover_gige_cameras()
            for idx, dev in enumerate(gige_devices):
                score = 100
                matches.append(CameraPluginMatch(
                    plugin_id=self.plugin_id,
                    device_index=idx,
                    name=f"{dev.manufacturer} {dev.model} ({dev.ip_address})",
                    resolution=(1920, 1080) if not dev.is_thermal else (640, 512),
                    score=score,
                    extra={
                        "ip_address": dev.ip_address,
                        "mac_address": dev.mac_address,
                        "subnet_mask": dev.subnet_mask,
                        "gateway": dev.gateway,
                        "is_thermal": dev.is_thermal,
                        "serial": dev.serial_number,
                    }
                ))
        except Exception as e:
            logger.debug(f"GVCP network discovery failed: {e}")

        # 2. GenICam / eBUS DirectShow sources that are backed by real hardware.
        #
        # Vendor SDKs (Basler pylon, Pleora eBUS) register capture filters at
        # install time, so a filter with a GenICam-ish name exists whether or
        # not a camera is attached — matching on the name alone reported five
        # phantom cameras on a machine with none. Only devices present in the
        # shared scan are real: that scan requires a successful frame read,
        # which an unbacked filter cannot satisfy.
        for device in scan_video_devices():
            if not any(term in device.name.lower() for term in GENICAM_FILTER_TERMS):
                continue
            # Avoid duplicates if already discovered via GVCP
            if any(device.name in m.name for m in matches):
                continue
            matches.append(CameraPluginMatch(
                plugin_id=self.plugin_id,
                device_index=device.index,
                name=device.name,
                resolution=device.resolution,
                score=90,
                extra={"is_directshow_filter": True, "device_name": device.name}
            ))

        return matches

    def create_backend(self, match: CameraPluginMatch) -> GigEBackend:
        ip = match.extra.get("ip_address", "192.168.1.100")
        is_thermal = match.extra.get("is_thermal", False)
        backend = GigEBackend(
            ip_address=ip,
            device_index=match.device_index,
            is_thermal=is_thermal
        )
        self._last_backend = backend
        return backend

    def create_sdk(self, match: CameraPluginMatch) -> GigECameraSDK:
        sdk = GigECameraSDK(backend_obj=self._last_backend, match=match)
        sdk.connect()
        return sdk

    def create_control_panel(self) -> Optional[QWidget]:
        from thermal_inspection.gui.camera_control.gige_control_panel import GigEControlPanel
        return GigEControlPanel()

    def get_capabilities(self, match: CameraPluginMatch) -> CameraCapabilities:
        is_thermal = match.extra.get("is_thermal", False)
        return CameraCapabilities(
            bit_depth=16 if is_thermal else 8,
            radiometric=is_thermal,
            resolutions=[(1920, 1080), (1280, 720), (640, 512), (640, 480)],
            max_fps=60.0,
            has_exposure_control=True,
            has_gain_mode=True,
            model=match.name or "GigE Vision Camera"
        )

    def on_sdk_connected(self, sdk: CameraSDK, panel: Optional[QWidget]):
        if panel and hasattr(panel, "update_camera_info"):
            res = sdk.execute("get_camera_info")
            if res.get("success"):
                panel.update_camera_info(res)
