"""
Multi-Router OSPF Network Simulator.

Orchestrates multiple OSPFDaemon instances connected via a VirtualPacketBus,
providing a complete in-process OSPF convergence laboratory.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from mini_ospf.app.daemon import OSPFDaemon
from mini_ospf.config.loader import load_config_file
from mini_ospf.config.models import DaemonConfig
from mini_ospf.observability.logging import setup_logging
from mini_ospf.protocol.serializer import serialize_packet
from mini_ospf.simulator.virtual_bus import VirtualPacketBus

logger = logging.getLogger("mini_ospf.simulator.network")


@dataclass
class RouterNode:
    """A router node in the simulated network."""
    router_id: str
    daemon: OSPFDaemon
    config: DaemonConfig
    started_at: float = 0.0
    is_running: bool = False


# ── pre-built 4-router topology ──────────────────────────────────────────────
# R1 ─── R2
# │       │
# R3 ─── R4
#
# R1=1.1.1.1  R2=2.2.2.2  R3=3.3.3.3  R4=4.4.4.4
# Link costs: R1-R2=10, R1-R3=10, R2-R4=20, R3-R4=10
# Shortest path R1->R4:  R1-R3-R4 (cost 20)  vs  R1-R2-R4 (cost 30)

_BUILTIN_TOPOLOGY: list[dict[str, Any]] = [
    # router_id, interfaces [(name, ip, netmask, peer_router_id, peer_ifname, peer_ip, cost)]
    {
        "router_id": "1.1.1.1",
        "interfaces": [
            {"name": "eth0", "ip": "10.12.0.1", "mask": "255.255.255.0",
             "peer_id": "2.2.2.2", "peer_if": "eth0", "peer_ip": "10.12.0.2", "cost": 10},
            {"name": "eth1", "ip": "10.13.0.1", "mask": "255.255.255.0",
             "peer_id": "3.3.3.3", "peer_if": "eth0", "peer_ip": "10.13.0.3", "cost": 10},
        ],
    },
    {
        "router_id": "2.2.2.2",
        "interfaces": [
            {"name": "eth0", "ip": "10.12.0.2", "mask": "255.255.255.0",
             "peer_id": "1.1.1.1", "peer_if": "eth0", "peer_ip": "10.12.0.1", "cost": 10},
            {"name": "eth1", "ip": "10.24.0.2", "mask": "255.255.255.0",
             "peer_id": "4.4.4.4", "peer_if": "eth0", "peer_ip": "10.24.0.4", "cost": 20},
        ],
    },
    {
        "router_id": "3.3.3.3",
        "interfaces": [
            {"name": "eth0", "ip": "10.13.0.3", "mask": "255.255.255.0",
             "peer_id": "1.1.1.1", "peer_if": "eth1", "peer_ip": "10.13.0.1", "cost": 10},
            {"name": "eth1", "ip": "10.34.0.3", "mask": "255.255.255.0",
             "peer_id": "4.4.4.4", "peer_if": "eth1", "peer_ip": "10.34.0.4", "cost": 10},
        ],
    },
    {
        "router_id": "4.4.4.4",
        "interfaces": [
            {"name": "eth0", "ip": "10.24.0.4", "mask": "255.255.255.0",
             "peer_id": "2.2.2.2", "peer_if": "eth1", "peer_ip": "10.24.0.2", "cost": 20},
            {"name": "eth1", "ip": "10.34.0.4", "mask": "255.255.255.0",
             "peer_id": "3.3.3.3", "peer_if": "eth1", "peer_ip": "10.34.0.3", "cost": 10},
        ],
    },
]


def _make_daemon_config(router_id: str, interfaces: list[dict[str, Any]]) -> DaemonConfig:
    """Build a DaemonConfig object programmatically for a simulated router."""
    from mini_ospf.config.loader import load_config_from_dict

    raw: dict[str, Any] = {
        "router": {"router_id": router_id},
        "areas": [{"id": "0.0.0.0", "type": "standard"}],
        "interfaces": [
            {
                "name": ifc["name"],
                "ip_address": ifc["ip"],
                "netmask": ifc["mask"],
                "area": "0.0.0.0",
                "hello_interval": 5,
                "dead_interval": 20,
                "metric": ifc["cost"],
                "udp_port": 8989,
            }
            for ifc in interfaces
        ],
        "spf": {"init_delay_ms": 50, "hold_time_ms": 100, "max_delay_ms": 2000},
        "logging": {"level": "INFO", "format": "text"},
        "server": {"api_enabled": False, "unix_socket_path": "", "http_port": 0},
        "install_kernel_routes": False,
    }
    return load_config_from_dict(raw)


class SimulatedNetwork:
    """
    Orchestrates a simulated multi-router OSPF network running entirely in-process.
    """

    def __init__(self) -> None:
        self.bus = VirtualPacketBus()
        self.routers: dict[str, RouterNode] = {}
        self._topology_desc: list[dict[str, Any]] = []
        self._started_at: float = 0.0
        self._tasks: list[asyncio.Task[None]] = []

    def load_builtin_topology(self) -> None:
        """Load the built-in 4-router diamond topology."""
        self._topology_desc = _BUILTIN_TOPOLOGY
        self._build_from_desc()

    def _build_from_desc(self) -> None:
        """Instantiate daemons and wire bus links from topology description."""
        # Create router daemons
        for rdef in self._topology_desc:
            rid = rdef["router_id"]
            cfg = _make_daemon_config(rid, rdef["interfaces"])
            daemon = OSPFDaemon(cfg, use_mock_sockets=True)

            # Override send function to route through bus
            self._wire_daemon_to_bus(daemon, rid, rdef["interfaces"])

            node = RouterNode(router_id=rid, daemon=daemon, config=cfg)
            self.routers[rid] = node
            self.bus.register_router(rid, daemon.handle_raw_packet)

        # Add virtual links
        seen_links: set[tuple[str, str]] = set()
        for rdef in self._topology_desc:
            rid = rdef["router_id"]
            for ifc in rdef["interfaces"]:
                peer_id = ifc["peer_id"]
                lkey = (min(rid, peer_id), max(rid, peer_id))
                if lkey not in seen_links:
                    seen_links.add(lkey)
                    # Find matching peer interface
                    peer_rdef = next(r for r in self._topology_desc if r["router_id"] == peer_id)
                    peer_ifc = next(i for i in peer_rdef["interfaces"] if i["peer_id"] == rid)
                    self.bus.add_link(
                        rid, ifc["name"], ifc["ip"],
                        peer_id, peer_ifc["name"], peer_ifc["ip"],
                        delay_ms=1.0,
                    )

    def _wire_daemon_to_bus(self, daemon: OSPFDaemon, router_id: str, interfaces: list[dict[str, Any]]) -> None:
        """Override the daemon's send_raw_packet to go through the virtual bus."""
        ip_by_ifname = {ifc["name"]: ifc["ip"] for ifc in interfaces}

        def bus_sender(
            raw_bytes: bytes,
            interface_name: str,
            dest_ip: str | None = None,
            dest_port: int | None = None,
        ) -> bool:
            daemon.metrics.inc("packets_tx_total")
            src_ip = ip_by_ifname.get(interface_name, "0.0.0.0")
            self.bus.send_packet(
                src_router_id=router_id,
                ifname=interface_name,
                raw_bytes=raw_bytes,
                dest_ip=dest_ip or "224.0.0.5",
                dest_port=dest_port or 8989,
                src_ip=src_ip,
            )
            return True

        daemon.send_raw_packet = bus_sender  # type: ignore[method-assign]

    async def start(self) -> None:
        """Start the virtual bus and all router daemons."""
        setup_logging(level="INFO", log_format="text")
        await self.bus.start()

        for node in self.routers.values():
            await node.daemon.start()
            node.started_at = time.monotonic()
            node.is_running = True
            logger.info("Started simulated router %s", node.router_id)

        self._started_at = time.monotonic()

    async def stop(self) -> None:
        """Stop all routers and the bus."""
        for node in self.routers.values():
            await node.daemon.stop()
            node.is_running = False
        await self.bus.stop()

    def toggle_link(self, router_a: str, router_b: str) -> bool:
        """Toggle a link between two routers and trigger SPF on both sides."""
        link = self.bus.get_link(router_a, router_b)
        if link is None:
            return False
        new_state = not link.is_up
        self.bus.set_link_state(router_a, router_b, new_state)
        # Trigger SPF on both router sides
        for rid in (router_a, router_b):
            node = self.routers.get(rid)
            if node and node.is_running:
                node.daemon.spf_scheduler.trigger()
        return True

    def set_link_loss(self, router_a: str, router_b: str, loss_pct: float) -> bool:
        link = self.bus.get_link(router_a, router_b)
        if link is None:
            return False
        link.loss_percent = max(0.0, min(100.0, loss_pct))
        return True

    def snapshot(self) -> dict[str, Any]:
        """Full network state snapshot for dashboard."""
        routers_state: list[dict[str, Any]] = []
        for rid, node in self.routers.items():
            d = node.daemon
            ifaces = [
                {
                    "name": iface.name,
                    "ip_address": iface.ip_address,
                    "netmask": iface.netmask,
                    "cidr": iface.cidr,
                    "area_id": iface.area_id,
                    "metric": iface.metric,
                    "is_up": iface.is_up,
                }
                for iface in d.interfaces.values()
            ]
            neighbors = [
                {
                    "router_id": n.router_id,
                    "ip_address": n.ip_address,
                    "interface_name": n.interface_name,
                    "state": n.state.name,
                    "priority": n.router_priority,
                }
                for n in d.neighbors.values()
            ]
            routes = [
                {
                    "destination": r.destination,
                    "metric": r.metric,
                    "route_type": r.route_type.name,
                    "next_hops": [str(nh) for nh in r.next_hops],
                }
                for r in d.rib.all_routes()
            ]
            lsas = [
                {
                    "ls_type": lsa.header.ls_type.name,
                    "link_state_id": lsa.header.link_state_id,
                    "advertising_router": lsa.header.advertising_router,
                    "ls_age": lsa.header.ls_age,
                    "ls_sequence_number": lsa.header.ls_sequence_number,
                }
                for lsa in d.lsdb.all_lsas()
            ]
            metrics = d.metrics.snapshot()
            health = d.health_checker.check()
            uptime = round(time.monotonic() - node.started_at, 1) if node.started_at else 0.0

            routers_state.append({
                "router_id": rid,
                "area_id": d.area_id,
                "is_running": node.is_running,
                "uptime_seconds": uptime,
                "interfaces": ifaces,
                "neighbors": neighbors,
                "routes": routes,
                "lsas": lsas,
                "metrics": metrics,
                "health": health,
            })

        return {
            "network": {
                "uptime_seconds": round(time.monotonic() - self._started_at, 1) if self._started_at else 0.0,
                "router_count": len(self.routers),
                "topology": self._topology_desc,
            },
            "routers": routers_state,
            "bus": self.bus.snapshot(),
        }
