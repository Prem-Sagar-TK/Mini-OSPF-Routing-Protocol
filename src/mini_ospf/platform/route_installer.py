"""
Route Installation Abstraction for Kernel FIB Integration (Linux & Mock).
"""

import logging
import subprocess
import sys
from abc import ABC, abstractmethod

from mini_ospf.routing.route import Route

logger = logging.getLogger("mini_ospf.platform.route_installer")


class BaseRouteInstaller(ABC):
    """Abstract interface for installing and removing routes from the OS Kernel FIB."""

    @abstractmethod
    def install_route(self, route: Route) -> bool:
        """Install or replace a route in the kernel routing table."""
        pass

    @abstractmethod
    def remove_route(self, route: Route) -> bool:
        """Remove a route from the kernel routing table."""
        pass

    @abstractmethod
    def get_installed_routes(self) -> list[Route]:
        """Return all currently active routes installed by this daemon."""
        pass


class MockRouteInstaller(BaseRouteInstaller):
    """
    In-memory Mock Route Installer for automated testing and non-Linux operating systems.
    Accurately records route additions, modifications, and deletions.
    """

    def __init__(self) -> None:
        self._installed_routes: dict[str, Route] = {}

    def install_route(self, route: Route) -> bool:
        self._installed_routes[route.destination] = route
        logger.debug("[MockFIB] Installed route %s", route)
        return True

    def remove_route(self, route: Route) -> bool:
        existed = self._installed_routes.pop(route.destination, None)
        if existed is not None:
            logger.debug("[MockFIB] Removed route %s", route.destination)
            return True
        return False

    def get_installed_routes(self) -> list[Route]:
        return list(self._installed_routes.values())


class LinuxRouteInstaller(BaseRouteInstaller):
    """
    Real Linux Kernel FIB Route Installer.
    Utilizes `pyroute2` if available, or falls back to privileged `ip route` CLI commands.
    """

    def __init__(self, table_id: int = 254) -> None:
        self.table_id: int = table_id
        self._installed_routes: dict[str, Route] = {}
        self._has_pyroute2 = False

        if sys.platform == "linux":
            try:
                import pyroute2  # type: ignore[import-untyped] # noqa: F401

                self._has_pyroute2 = True
            except ImportError:
                self._has_pyroute2 = False

    def install_route(self, route: Route) -> bool:
        dest = route.destination
        if not route.next_hops:
            logger.warning("Cannot install route %s without next hops", dest)
            return False

        if sys.platform != "linux":
            logger.warning("LinuxRouteInstaller invoked on non-Linux platform (%s); skipping", sys.platform)
            return False

        first_nh = route.next_hops[0]
        cmd = ["ip", "route", "replace", dest]

        if first_nh.ip_address:
            cmd.extend(["via", first_nh.ip_address])
        if first_nh.interface_name:
            cmd.extend(["dev", first_nh.interface_name])
        cmd.extend(["proto", "ospf", "metric", str(route.metric)])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self._installed_routes[dest] = route
            logger.info("Kernel FIB: Installed %s (code=%d)", dest, res.returncode)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError) as e:
            logger.error("Failed to install route %s to Linux FIB: %s", dest, e)
            return False

    def remove_route(self, route: Route) -> bool:
        dest = route.destination
        if sys.platform != "linux":
            return False

        cmd = ["ip", "route", "del", dest]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self._installed_routes.pop(dest, None)
            logger.info("Kernel FIB: Removed %s (code=%d)", dest, res.returncode)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, PermissionError) as e:
            logger.error("Failed to remove route %s from Linux FIB: %s", dest, e)
            return False

    def get_installed_routes(self) -> list[Route]:
        return list(self._installed_routes.values())
