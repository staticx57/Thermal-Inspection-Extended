"""UVC extension-unit (XU) access for the Tau 2 breakout board, over DirectShow (IKsTopologyInfo -> IKsControl).

The board has no CDC/serial CCI line; its XU is the vendor-defined control channel.  This module is only the transport
(read/write a selector's bytes); what each selector means is not documented and is being worked out empirically - see
tools/tau2_xu_probe.py and docs/tau2_xu_probe_*.json.  Windows only.
"""
from __future__ import annotations

import ctypes
import struct
import uuid
from ctypes import POINTER, Structure, byref, c_ubyte, c_ulong, c_void_p
from typing import Dict, Optional

KSPROPERTY_TYPE_GET = 0x1
KSPROPERTY_TYPE_SET = 0x2
KSPROPERTY_TYPE_BASICSUPPORT = 0x200
KSPROPERTY_TYPE_TOPOLOGY = 0x10000000
KSNODETYPE_DEV_SPECIFIC = "{941C7AC0-C559-11D0-8A2B-00A0C9255AC1}"
IID_IKsTopologyInfo = "{720D4AC0-7533-11D0-A5D6-28DB04C10000}"
IID_IKsControl = "{28F54685-06FD-11D2-B27A-00A0C9223196}"

# The XU the board declares in its USB descriptor (unit 3), read with tools/tau2_xu_probe.py
TAU2_XU_GUID = "ACB6890C-A3B3-4060-8B9A-DF34EEF39A2E"


class _KSIDENTIFIER(Structure):
    _fields_ = [("Set", ctypes.c_byte * 16), ("Id", c_ulong), ("Flags", c_ulong)]


class _KSP_NODE(Structure):
    _fields_ = [("Property", _KSIDENTIFIER), ("NodeId", c_ulong), ("Reserved", c_ulong)]


def decode_basic_support(raw: bytes) -> Dict:
    """KSPROPERTY_DESCRIPTION (+ one members header and its range) as returned for BASICSUPPORT.

    Layout: AccessFlags, DescriptionSize, PropTypeSet{GUID,Id,Flags}, MembersListCount, Reserved, then per list a
    KSPROPERTY_MEMBERSHEADER{MembersFlags, MembersSize, MembersCount, Flags} followed by the members; for a range the
    member is KSPROPERTY_STEPPING_LONG{SteppingDelta, Reserved, Bounds{Min, Max}} (little-endian)."""
    out: Dict = {"raw": raw.hex()}
    if len(raw) < 40:
        return out
    access, _desc_size = struct.unpack_from("<II", raw, 0)
    out["get"], out["set"] = bool(access & 1), bool(access & 2)
    out["value_type"] = struct.unpack_from("<I", raw, 24)[0]
    members = struct.unpack_from("<I", raw, 32)[0]
    if members and len(raw) >= 48 + 4:
        # the range members are 4-byte-aligned in the buffer's tail: step, reserved, then min and max
        tail = raw[48:]
        if len(tail) >= 16:
            step, _r, lo, hi = struct.unpack_from("<IIii", tail, 0)
            out.update(step=step, min=lo, max=hi)
        else:
            out["range_tail"] = tail.hex()
    return out


class Tau2XU:
    """Open the Tau 2 capture filter and talk to its XU node.  Holds COM objects: keep one instance and close() it."""

    def __init__(self, name_hint: str = "tau", xu_guid: str = TAU2_XU_GUID):
        import comtypes
        from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
        from ctypes.wintypes import DWORD, LPWSTR
        from pygrabber.dshow_graph import FilterGraph

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

        self._comtypes = comtypes
        self._guid_bytes = uuid.UUID(xu_guid).bytes_le
        graph = FilterGraph()
        names = graph.get_input_devices()
        index = next((i for i, n in enumerate(names) if name_hint in n.lower()), None)
        if index is None:
            raise RuntimeError(f"no DirectShow video device matching {name_hint!r}: {names}")
        graph.add_video_input_device(index)
        self.device_name = names[index].strip()
        self._graph = graph                      # keeps the filter alive
        topo = graph.get_input_device().instance.QueryInterface(IKsTopologyInfo)
        self.nodes = [str(topo.get_NodeType(i)).upper() for i in range(topo.get_NumNodes())]
        if KSNODETYPE_DEV_SPECIFIC not in self.nodes:
            raise RuntimeError("Windows exposes no device-specific (extension unit) node for this camera")
        self.node = self.nodes.index(KSNODETYPE_DEV_SPECIFIC)
        self._ctl = topo.CreateNodeInstance(self.node, GUID(IID_IKsControl)).QueryInterface(IKsControl)

    def _prop(self, selector: int, flags: int) -> _KSP_NODE:
        p = _KSP_NODE()
        ctypes.memmove(byref(p.Property.Set), self._guid_bytes, 16)
        p.Property.Id = selector
        p.Property.Flags = flags | KSPROPERTY_TYPE_TOPOLOGY
        p.NodeId = self.node
        return p

    def _call(self, selector: int, flags: int, data: Optional[bytes], size: int) -> bytes:
        p = self._prop(selector, flags)
        buf = (c_ubyte * max(size, 1))(*(data or b""))
        ret = c_ulong(0)
        self._ctl.KsProperty(byref(p), ctypes.sizeof(p), buf, size, byref(ret))
        return bytes(buf[:ret.value])

    def support(self, selector: int) -> Dict:
        try:
            return decode_basic_support(self._call(selector, KSPROPERTY_TYPE_BASICSUPPORT, None, 64))
        except self._comtypes.COMError as e:
            return {"error": f"0x{e.args[0] & 0xFFFFFFFF:08X}"}

    def get(self, selector: int, size: int = 64) -> bytes:
        """GET_CUR; returns exactly the bytes the control carries."""
        return self._call(selector, KSPROPERTY_TYPE_GET, None, size)

    def set(self, selector: int, value: bytes) -> None:
        """SET_CUR.  Writes to a vendor control; callers must know what the selector does."""
        self._call(selector, KSPROPERTY_TYPE_SET, value, len(value))

    def close(self) -> None:
        self._ctl = None
        self._graph = None
