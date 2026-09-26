"""
Linux Netlink and Interface Status Inspection.
"""

import logging
import socket
import struct
import sys

logger = logging.getLogger("mini_ospf.platform.netlink")


def get_interface_addresses(ifname: str) -> list[str]:
    """
    Retrieve IPv4 addresses assigned to an interface.
    Uses Linux SIOCGIFADDR ioctl or standard socket bindings.
    """
    if sys.platform != "linux":
        return []

    try:
        import fcntl

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 0x8915 = SIOCGIFADDR
        res = fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", ifname[:15].encode("utf-8")))
        ip = socket.inet_ntoa(res[20:24])
        return [ip]
    except Exception as e:
        logger.debug("Could not query IP address for interface %s: %s", ifname, e)
        return []


def is_interface_up(ifname: str) -> bool:
    """Check if interface flags contain IFF_UP."""
    if sys.platform != "linux":
        return True

    try:
        import fcntl

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 0x8913 = SIOCGIFFLAGS
        res = fcntl.ioctl(s.fileno(), 0x8913, struct.pack("256s", ifname[:15].encode("utf-8")))
        flags = struct.unpack("H", res[16:18])[0]
        # IFF_UP = 0x1
        return bool(flags & 0x1)
    except Exception as e:
        logger.debug("Could not query IFF_UP flags for %s: %s", ifname, e)
        return True
