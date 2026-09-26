"""
Platform, interfaces, socket backends, and Linux FIB integration.
"""

from mini_ospf.platform.interfaces import Interface
from mini_ospf.platform.linux_netlink import get_interface_addresses, is_interface_up
from mini_ospf.platform.route_installer import (
    BaseRouteInstaller,
    LinuxRouteInstaller,
    MockRouteInstaller,
)
from mini_ospf.platform.socket_backend import SocketBackend

__all__ = [
    "BaseRouteInstaller",
    "Interface",
    "LinuxRouteInstaller",
    "MockRouteInstaller",
    "SocketBackend",
    "get_interface_addresses",
    "is_interface_up",
]
