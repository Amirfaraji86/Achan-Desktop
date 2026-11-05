"""Windows interface selection helpers for bypassing the local TUN route."""
from __future__ import annotations

import ctypes
import ipaddress
import socket
import struct
import sys
from ctypes import wintypes

IP_UNICAST_IF = 31
IPV6_UNICAST_IF = 31


class SOCKADDR_IN6(ctypes.Structure):
    _fields_ = [
        ("sin6_family", ctypes.c_ushort),
        ("sin6_port", ctypes.c_ushort),
        ("sin6_flowinfo", ctypes.c_ulong),
        ("sin6_addr", ctypes.c_ubyte * 16),
        ("sin6_scope_id", ctypes.c_ulong),
    ]


def get_default_interface_indices() -> dict[str, int | None]:
    """Capture physical default-route interface indexes before TUN routes are added."""
    if sys.platform != "win32":
        raise OSError("This application is designed for Windows 7 SP1 or later.")

    iphlpapi = ctypes.WinDLL("iphlpapi.dll")
    ipv4_index = wintypes.DWORD(0)
    # 1.1.1.1 is intentionally used as a route probe, not as a DNS resolver.
    dest_v4 = int.from_bytes(socket.inet_aton("1.1.1.1"), byteorder="little")
    result = iphlpapi.GetBestInterface(wintypes.DWORD(dest_v4), ctypes.byref(ipv4_index))
    if result != 0 or ipv4_index.value == 0:
        raise OSError(f"Windows could not identify the IPv4 default interface (code {result}).")

    # ctypes.byref() only accepts an actual ctypes instance.  Keep the output
    # buffer separate from the Python-level optional value; passing None here
    # raises: "byref() argument must be a ctypes instance, not 'NoneType'".
    ipv6_index_out = wintypes.DWORD(0)
    ipv6_index: int | None = None
    try:
        raw_v6 = socket.inet_pton(socket.AF_INET6, "2001:4860:4860::8888")
        address = SOCKADDR_IN6()
        address.sin6_family = socket.AF_INET6
        address.sin6_port = 0
        address.sin6_flowinfo = 0
        address.sin6_addr = (ctypes.c_ubyte * 16).from_buffer_copy(raw_v6)
        address.sin6_scope_id = 0

        get_best_interface_ex = iphlpapi.GetBestInterfaceEx
        get_best_interface_ex.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        get_best_interface_ex.restype = wintypes.DWORD
        result6 = get_best_interface_ex(ctypes.byref(address), ctypes.byref(ipv6_index_out))
        if result6 == 0 and ipv6_index_out.value != 0:
            ipv6_index = int(ipv6_index_out.value)
    except (AttributeError, OSError, ValueError, TypeError):
        # IPv6 is optional. IPv4 still works, so don't fail the whole startup.
        ipv6_index = None

    return {"ipv4": int(ipv4_index.value), "ipv6": ipv6_index}


def bind_socket_to_physical_interface(sock: socket.socket, address: str, indices: dict[str, int | None]) -> None:
    """Pin a proxy's upstream socket to the pre-tunnel physical adapter.

    This is essential: without it, the proxy's own outbound connection could be
    caught by the system-wide TUN route and loop back into tun2proxy.
    """
    ip = ipaddress.ip_address(address)
    if ip.is_loopback or ip.is_link_local:
        return

    if ip.version == 4:
        index = indices.get("ipv4")
        if not index:
            raise OSError("No saved physical IPv4 interface index is available.")
        # IP_UNICAST_IF expects the interface index in network byte order.
        sock.setsockopt(socket.IPPROTO_IP, IP_UNICAST_IF, struct.pack("!I", int(index)))
    else:
        index = indices.get("ipv6")
        if not index:
            raise OSError("No saved physical IPv6 interface index is available.")
        # IPV6_UNICAST_IF expects the interface index in host byte order.
        sock.setsockopt(socket.IPPROTO_IPV6, IPV6_UNICAST_IF, struct.pack("=I", int(index)))
