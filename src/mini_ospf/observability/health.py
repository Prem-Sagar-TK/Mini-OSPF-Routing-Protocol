"""
Health Check and Diagnostics.
"""

from typing import Any


class HealthChecker:
    """Assesses runtime health and returns status for monitoring endpoints."""

    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon

    def check(self) -> dict[str, Any]:
        issues = []
        is_healthy = True

        if not self.daemon.is_running:
            is_healthy = False
            issues.append("Daemon is not in RUNNING state")

        # Check for interfaces down
        down_ifaces = [
            name for name, iface in self.daemon.interfaces.items() if not iface.is_up
        ]
        if down_ifaces:
            issues.append(f"Interfaces DOWN: {', '.join(down_ifaces)}")

        return {
            "status": "HEALTHY" if is_healthy else "DEGRADED",
            "healthy": is_healthy,
            "router_id": self.daemon.config.router_id,
            "interfaces_total": len(self.daemon.interfaces),
            "neighbors_total": len(self.daemon.neighbors),
            "lsas_in_db": self.daemon.lsdb.count(),
            "routes_in_rib": self.daemon.rib.count(),
            "issues": issues,
        }
