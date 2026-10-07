"""Read-only probe of the Tau 2 breakout board's UVC extension unit (XU).

The board has no CDC/serial CCI line; the seller's remaining route is CCI-over-UVC-XU.  This tool answers, without
sending a single write, whether Windows exposes that XU and what each control looks like:

  1. decodes the USB descriptor (cached by libusb - the device is not opened or re-driven) to find the XU unit id,
     GUID and the control selectors the unit declares;
  2. through DirectShow (IKsTopologyInfo -> IKsControl, the same path the Windows Camera app uses) asks each declared
     selector for its BASICSUPPORT and a GET of its current value.

Only KSPROPERTY_TYPE_BASICSUPPORT and KSPROPERTY_TYPE_GET are issued.  Nothing is SET.  Output is JSON on stdout so a
run can be saved and sent to the seller:   python tools/tau2_xu_probe.py > tau2_xu.json
"""
from __future__ import annotations

import ctypes
import json
import sys
import uuid
from ctypes import POINTER, Structure, byref, c_ubyte, c_ulong, c_void_p
from typing import Dict, List, Optional

VID, PID = 0x04B4, 0x0038

UVC_VC_EXTENSION_UNIT = 0x06
KSPROPERTY_TYPE_GET = 0x1
KSPROPERTY_TYPE_BASICSUPPORT = 0x200
KSPROPERTY_TYPE_TOPOLOGY = 0x10000000

IID_IKsTopologyInfo = "{720D4AC0-7533-11D0-A5D6-28DB04C10000}"
IID_IKsControl = "{28F54685-06FD-11D2-B27A-00A0C9223196}"


def parse_xu_descriptors(extra: bytes) -> List[Dict]:
    """Extension-unit descriptors out of the VideoControl interface's class-specific bytes."""
    units, i = [], 0
    while i + 3 <= len(extra):
        length = extra[i]
        if length < 3 or i + length > len(extra):
            break
        d = extra[i:i + length]
        if d[1] == 0x24 and d[2] == UVC_VC_EXTENSION_UNIT and length >= 24:
            n_pins = d[21]
            ctl_size = d[22 + n_pins]
            bm = d[23 + n_pins:23 + n_pins + ctl_size]
            bits = int.from_bytes(bm, "little")
            units.append({
                "unit_id": d[3],
                "guid": str(uuid.UUID(bytes_le=bytes(d[4:20]))).upper(),
                "num_controls": d[20],
                "source_ids": list(d[22:22 + n_pins]),
                "selectors": [b + 1 for b in range(8 * ctl_size) if bits >> b & 1],
            })
        i += length
    return units


def read_usb_descriptor() -> Optional[Dict]:
    import usb.core
    import usb.backend.libusb1 as libusb1
    import libusb_package
    backend = libusb1.get_backend(find_library=libusb_package.find_library)
    dev = usb.core.find(idVendor=VID, idProduct=PID, backend=backend)
    if dev is None:
        return None
    out = {"interfaces": [], "xu_units": []}
    for cfg in dev:
        for intf in cfg:
            extra = bytes(intf.extra_descriptors)
            out["interfaces"].append({
                "number": intf.bInterfaceNumber, "class": intf.bInterfaceClass, "subclass": intf.bInterfaceSubClass,
                "endpoints": [hex(e.bEndpointAddress) for e in intf]})
            if intf.bInterfaceClass == 0x0E and intf.bInterfaceSubClass == 0x01:
                out["xu_units"] += parse_xu_descriptors(extra)
    return out


# ---- DirectShow side -------------------------------------------------------------------------------------------

class KSIDENTIFIER(Structure):          # KSPROPERTY: Set GUID, Id, Flags
    _fields_ = [("Set", ctypes.c_byte * 16), ("Id", c_ulong), ("Flags", c_ulong)]


class KSP_NODE(Structure):
    _fields_ = [("Property", KSIDENTIFIER), ("NodeId", c_ulong), ("Reserved", c_ulong)]


def _guid_bytes(guid: str) -> bytes:
    return uuid.UUID(guid).bytes_le


def _find_filter(name_hint: str = "tau"):
    from pygrabber.dshow_graph import FilterGraph
    graph = FilterGraph()
    names = graph.get_input_devices()
    for idx, name in enumerate(names):
        if name_hint in name.lower():
            graph.add_video_input_device(idx)
            return graph, name
    raise RuntimeError(f"no DirectShow video device matching {name_hint!r}: {names}")


def probe_directshow(xu: Dict) -> Dict:
    import comtypes
    from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
    from ctypes.wintypes import DWORD, LPWSTR

    class IKsTopologyInfo(IUnknown):
        _iid_ = GUID(IID_IKsTopologyInfo)
        _methods_ = [
            COMMETHOD([], HRESULT, "get_NumCategories", (["out"], POINTER(DWORD), "n")),
            COMMETHOD([], HRESULT, "get_Category", (["in"], DWORD, "i"), (["out"], POINTER(GUID), "g")),
            COMMETHOD([], HRESULT, "get_NumConnections", (["out"], POINTER(DWORD), "n")),
            COMMETHOD([], HRESULT, "get_ConnectionInfo", (["in"], DWORD, "i"), (["out"], c_void_p, "c")),
            COMMETHOD([], HRESULT, "get_NodeName", (["in"], DWORD, "i"), (["in"], LPWSTR, "buf"),
                      (["in"], DWORD, "len"), (["out"], POINTER(DWORD), "ret")),
            COMMETHOD([], HRESULT, "get_NumNodes", (["out"], POINTER(DWORD), "n")),
            COMMETHOD([], HRESULT, "get_NodeType", (["in"], DWORD, "i"), (["out"], POINTER(GUID), "g")),
            COMMETHOD([], HRESULT, "CreateNodeInstance", (["in"], DWORD, "i"), (["in"], POINTER(GUID), "iid"),
                      (["out"], POINTER(POINTER(IUnknown)), "obj")),
        ]

    class IKsControl(IUnknown):
        _iid_ = GUID(IID_IKsControl)
        _methods_ = [
            COMMETHOD([], HRESULT, "KsProperty", (["in"], c_void_p, "prop"), (["in"], c_ulong, "proplen"),
                      (["in"], c_void_p, "data"), (["in"], c_ulong, "datalen"), (["in"], POINTER(c_ulong), "ret")),
            COMMETHOD([], HRESULT, "KsMethod", (["in"], c_void_p, "m"), (["in"], c_ulong, "ml"),
                      (["in"], c_void_p, "d"), (["in"], c_ulong, "dl"), (["in"], POINTER(c_ulong), "r")),
            COMMETHOD([], HRESULT, "KsEvent", (["in"], c_void_p, "e"), (["in"], c_ulong, "el"),
                      (["in"], c_void_p, "d"), (["in"], c_ulong, "dl"), (["in"], POINTER(c_ulong), "r")),
        ]

    graph, device_name = _find_filter()
    flt = graph.get_input_device().instance      # the IBaseFilter of the capture device
    topo = flt.QueryInterface(IKsTopologyInfo)
    n_nodes = topo.get_NumNodes()
    nodes = []
    for i in range(n_nodes):
        t = topo.get_NodeType(i)
        nodes.append({"node_id": i, "type": str(t)})
    result = {"device": device_name, "nodes": nodes, "xu_guid": xu["guid"], "controls": []}

    xu_nodes = [n for n in nodes if n["type"].upper() == "{941C7AC0-C559-11D0-8A2B-00A0C9255AC1}"]  # DEV_SPECIFIC
    if not xu_nodes:
        result["error"] = "no KSNODETYPE_DEV_SPECIFIC node exposed - Windows is not surfacing the XU"
        return result
    node = xu_nodes[0]["node_id"]
    ctl = topo.CreateNodeInstance(node, GUID(IID_IKsControl)).QueryInterface(IKsControl)

    for sel in xu["selectors"]:
        entry = {"selector": sel}
        for label, flag, size in (("basicsupport", KSPROPERTY_TYPE_BASICSUPPORT, 64), ("get", KSPROPERTY_TYPE_GET, 64)):
            p = KSP_NODE()
            ctypes.memmove(byref(p.Property.Set), _guid_bytes(xu["guid"]), 16)
            p.Property.Id, p.Property.Flags = sel, flag | KSPROPERTY_TYPE_TOPOLOGY
            p.NodeId = node
            buf = (c_ubyte * size)()
            ret = c_ulong(0)
            try:
                ctl.KsProperty(byref(p), ctypes.sizeof(p), buf, size, byref(ret))
                entry[label] = bytes(buf[:ret.value]).hex()
            except comtypes.COMError as e:
                entry[label] = f"error 0x{e.args[0] & 0xFFFFFFFF:08X}"
        result["controls"].append(entry)
    return result


def main() -> int:
    report: Dict = {"usb": read_usb_descriptor()}
    if report["usb"] is None:
        print(json.dumps({"error": f"USB device {VID:04x}:{PID:04x} not present"}))
        return 1
    if not report["usb"]["xu_units"]:
        report["conclusion"] = "descriptor declares no extension unit"
        print(json.dumps(report, indent=1))
        return 2
    try:
        report["directshow"] = probe_directshow(report["usb"]["xu_units"][0])
    except Exception as e:                      # the descriptor half is still useful on its own
        report["directshow_error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
