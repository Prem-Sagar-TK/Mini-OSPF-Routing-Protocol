"""
Mini-OSPF Core Routing Daemon (RFC 2328).
"""

import asyncio
import logging
import signal
import sys
import time
from typing import Any

from mini_ospf.api.server import APIServer
from mini_ospf.config.loader import load_config_file
from mini_ospf.config.models import DaemonConfig
from mini_ospf.lsdb.aging import LSAgingManager
from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.observability.health import HealthChecker
from mini_ospf.observability.logging import setup_logging
from mini_ospf.observability.metrics import MetricsCollector
from mini_ospf.ospf.database_description import DBDHandler
from mini_ospf.ospf.flooding import FloodingEngine
from mini_ospf.ospf.hello import HelloHandler
from mini_ospf.ospf.link_state_ack import LSAckHandler
from mini_ospf.ospf.link_state_request import LSRHandler
from mini_ospf.ospf.link_state_update import LSUHandler
from mini_ospf.ospf.neighbor import Neighbor
from mini_ospf.ospf.neighbor_fsm import NeighborEvent, NeighborState
from mini_ospf.platform.interfaces import Interface
from mini_ospf.platform.route_installer import (
    BaseRouteInstaller,
    LinuxRouteInstaller,
    MockRouteInstaller,
)
from mini_ospf.platform.socket_backend import SocketBackend
from mini_ospf.protocol.constants import (
    LSA_INITIAL_SEQUENCE_NUMBER,
    LSAType,
    RouterLinkType,
)
from mini_ospf.protocol.packet import (
    DatabaseDescriptionPacket,
    HelloPacket,
    LinkStateAckPacket,
    LinkStateRequestPacket,
    LinkStateUpdatePacket,
    LSAHeader,
    RouterLink,
    RouterLSA,
)
from mini_ospf.protocol.parser import parse_packet
from mini_ospf.protocol.serializer import serialize_packet
from mini_ospf.protocol.validation import validate_header_context, validate_raw_packet
from mini_ospf.routing.rib import RIB
from mini_ospf.security.limits import RateLimiter, ResourceLimits
from mini_ospf.spf.dijkstra import run_dijkstra_spt
from mini_ospf.spf.graph import build_topology_graph
from mini_ospf.spf.next_hop import generate_route_candidates
from mini_ospf.spf.scheduler import SPFScheduler
from mini_ospf.transport.receiver import PacketReceiver
from mini_ospf.transport.sender import PacketSender

logger = logging.getLogger("mini_ospf.daemon")


class OSPFDaemon:
    """
    Production-oriented OSPFv2 Routing Daemon coordinating all protocol subsystems.
    """

    def __init__(
        self,
        config: DaemonConfig,
        route_installer: BaseRouteInstaller | None = None,
        use_mock_sockets: bool = False,
    ) -> None:
        self.config = config
        self.router_id: str = config.router_id
        self.area_id: str = config.areas[0].id if config.areas else "0.0.0.0"

        # State Subsystems
        self.lsdb = LinkStateDatabase(area_id=self.area_id)
        self.rib = RIB()
        self.metrics = MetricsCollector()
        self.limits = ResourceLimits()
        self.rate_limiter = RateLimiter(rate_per_sec=self.limits.max_packet_rate_per_sec)

        # Route Installer
        if route_installer is not None:
            self.route_installer = route_installer
        elif config.install_kernel_routes and sys.platform == "linux":
            self.route_installer = LinuxRouteInstaller()
        else:
            self.route_installer = MockRouteInstaller()

        # Interfaces & Neighbors
        self.interfaces: dict[str, Interface] = {}
        self.neighbors: dict[str, Neighbor] = {}  # router_id -> Neighbor
        self.socket_backends: dict[str, SocketBackend] = {}
        self.use_mock_sockets = use_mock_sockets

        for if_cfg in config.interfaces:
            iface = Interface(
                name=if_cfg.name,
                ip_address=if_cfg.ip_address,
                netmask=if_cfg.netmask,
                area_id=if_cfg.area,
                hello_interval=if_cfg.hello_interval,
                dead_interval=if_cfg.dead_interval,
                metric=if_cfg.metric,
                router_priority=if_cfg.priority,
                udp_port=if_cfg.udp_port,
            )
            self.interfaces[if_cfg.name] = iface
            if not use_mock_sockets:
                self.socket_backends[if_cfg.name] = SocketBackend(
                    interface_name=if_cfg.name,
                    bind_ip=if_cfg.ip_address,
                    port=if_cfg.udp_port,
                )

        # Protocol Handlers
        self.hello_handler = HelloHandler(self.router_id, self.area_id)
        self.dbd_handler = DBDHandler(self.router_id, self.area_id)
        self.lsr_handler = LSRHandler(self.router_id, self.area_id)
        self.lsu_handler = LSUHandler(self.router_id, self.area_id)
        self.lsack_handler = LSAckHandler(self.router_id, self.area_id)

        # Transports
        self.sender = PacketSender(self.socket_backends)
        self.receiver = PacketReceiver(self.handle_raw_packet)
        self.flooding_engine = FloodingEngine(
            self.router_id, self.area_id, send_raw_func=self.send_raw_packet
        )

        # SPF Engine & Timers
        self.spf_scheduler = SPFScheduler(
            spf_callback=self.run_spf_calculation,
            init_delay=config.spf.init_delay_ms / 1000.0,
            hold_time=config.spf.hold_time_ms / 1000.0,
            max_delay=config.spf.max_delay_ms / 1000.0,
        )
        self.aging_manager = LSAgingManager(self.lsdb, on_max_age=self._on_lsa_max_age)

        # API Server
        self.api_server: APIServer | None = None
        if config.server.api_enabled:
            self.api_server = APIServer(
                get_state_callback=self.handle_api_command,
                unix_socket_path=config.server.unix_socket_path,
                tcp_port=config.server.http_port,
            )

        self.health_checker = HealthChecker(self)
        self.is_running: bool = False
        self._router_lsa_seq: int = LSA_INITIAL_SEQUENCE_NUMBER
        self._tasks: list[asyncio.Task[None]] = []

    def send_raw_packet(
        self,
        raw_bytes: bytes,
        interface_name: str,
        dest_ip: str | None = None,
        dest_port: int | None = None,
    ) -> bool:
        """Send raw serialized packet bytes out an interface."""
        self.metrics.inc("packets_tx_total")
        if self.use_mock_sockets:
            return True
        return self.sender.send_packet(raw_bytes, interface_name, dest_ip, dest_port)

    def generate_self_router_lsa(self) -> RouterLSA:
        """Construct self-originated Type 1 Router-LSA based on local interfaces and FULL neighbors."""
        links: list[RouterLink] = []

        # 1. Connected Stub Networks
        for iface in self.interfaces.values():
            if iface.is_up:
                links.append(
                    RouterLink(
                        link_id=iface.ip_address,
                        link_data=iface.netmask,
                        link_type=RouterLinkType.STUB_NETWORK,
                        metric=iface.metric,
                    )
                )

        # 2. Point-to-Point links to FULL neighbors
        for neigh in self.neighbors.values():
            if neigh.is_full():
                links.append(
                    RouterLink(
                        link_id=neigh.router_id,
                        link_data=neigh.ip_address,
                        link_type=RouterLinkType.POINT_TO_POINT,
                        metric=self.interfaces.get(neigh.interface_name, Interface("eth0", "0.0.0.0")).metric,
                    )
                )

        self._router_lsa_seq += 1
        hdr = LSAHeader(
            ls_age=0,
            options=0x02,
            ls_type=LSAType.ROUTER,
            link_state_id=self.router_id,
            advertising_router=self.router_id,
            ls_sequence_number=self._router_lsa_seq,
        )
        lsa = RouterLSA(header=hdr, num_links=len(links), links=links)
        self.lsdb.install(lsa)
        self.flooding_engine.flood_lsa(lsa, self.neighbors)
        return lsa

    def handle_raw_packet(
        self, raw_bytes: bytes, interface_name: str, src_ip: str, src_port: int
    ) -> None:
        """Primary packet ingestion pipeline with defensive guards and error handling."""
        self.metrics.inc("packets_rx_total")

        if not self.rate_limiter.allow():
            self.metrics.inc("packets_rate_limited")
            return

        try:
            validate_raw_packet(raw_bytes)
            pkt = parse_packet(raw_bytes)
            validate_header_context(pkt.header, self.area_id, self.router_id)
        except Exception as e:
            self.metrics.inc("packet_validation_errors")
            logger.debug("Dropped invalid packet on %s from %s: %s", interface_name, src_ip, e)
            return

        sender_id = pkt.header.router_id

        # Dispatch based on packet type
        match pkt:
            case HelloPacket():
                self.metrics.inc("hello_rx_total")
                neigh, is_new = self.hello_handler.process_incoming_hello(
                    pkt, src_ip, interface_name, self.neighbors
                )
                neigh.fsm.on_state_change = self._on_neighbor_state_change
                if is_new:
                    self.metrics.inc("neighbors_discovered")

            case DatabaseDescriptionPacket():
                self.metrics.inc("dbd_rx_total")
                target_neigh = self.neighbors.get(sender_id)
                if target_neigh is not None:
                    target_neigh.touch()
                    resp_dbd = self.dbd_handler.process_incoming_dbd(pkt, target_neigh, self.lsdb)
                    if resp_dbd:
                        raw_resp = serialize_packet(resp_dbd)
                        self.send_raw_packet(raw_resp, interface_name, src_ip, src_port)

                    # If in LOADING state, send LSRs
                    if target_neigh.state == NeighborState.LOADING:
                        lsr = self.lsr_handler.create_lsr_packet(target_neigh)
                        if lsr:
                            self.send_raw_packet(
                                serialize_packet(lsr), interface_name, src_ip, src_port
                            )

            case LinkStateRequestPacket():
                self.metrics.inc("lsr_rx_total")
                target_neigh = self.neighbors.get(sender_id)
                if target_neigh is not None:
                    target_neigh.touch()
                    lsu = self.lsr_handler.process_incoming_lsr(pkt, self.lsdb)
                    if lsu.lsas:
                        self.send_raw_packet(
                            serialize_packet(lsu), interface_name, src_ip, src_port
                        )

            case LinkStateUpdatePacket():
                self.metrics.inc("lsu_rx_total")
                target_neigh = self.neighbors.get(sender_id)
                if target_neigh is not None:
                    target_neigh.touch()
                    installed_lsas, ack_pkt = self.lsu_handler.process_incoming_lsu(
                        pkt, target_neigh, self.lsdb
                    )
                    # Send LSAck back
                    if ack_pkt.lsa_headers:
                        self.send_raw_packet(
                            serialize_packet(ack_pkt), interface_name, src_ip, src_port
                        )

                    # Flood newly installed LSAs
                    for lsa in installed_lsas:
                        self.flooding_engine.flood_lsa(
                            lsa, self.neighbors, exclude_neighbor_id=sender_id
                        )

                    if installed_lsas:
                        self.spf_scheduler.trigger()

            case LinkStateAckPacket():
                self.metrics.inc("lsack_rx_total")
                target_neigh = self.neighbors.get(sender_id)
                if target_neigh is not None:
                    target_neigh.touch()
                    self.lsack_handler.process_incoming_ack(pkt, target_neigh)

    def _on_neighbor_state_change(
        self, old_state: NeighborState, new_state: NeighborState, event: NeighborEvent
    ) -> None:
        self.metrics.inc("neighbor_state_changes_total")
        logger.info(
            "[%s] Neighbor state changed: %s -> %s (event: %s)",
            self.router_id,
            old_state.name,
            new_state.name,
            event.name,
        )

        # If neighbor reached FULL or dropped from FULL: update self Router-LSA and run SPF
        if new_state == NeighborState.FULL or old_state == NeighborState.FULL:
            self.generate_self_router_lsa()
            self.spf_scheduler.trigger()

    def _on_lsa_max_age(self, lsa: Any) -> None:
        logger.warning(
            "[%s] LSA MaxAge expired for (%s, %s)",
            self.router_id,
            lsa.header.ls_type,
            lsa.header.link_state_id,
        )
        self.spf_scheduler.trigger()

    def run_spf_calculation(self) -> None:
        """Run Dijkstra Shortest Path Tree computation, update RIB and kernel FIB."""
        start_ts = time.monotonic()
        graph = build_topology_graph(self.lsdb)
        spt = run_dijkstra_spt(graph, self.router_id)

        # Build direct neighbors mapping
        direct_map = {n.router_id: n.ip_address for n in self.neighbors.values() if n.is_full()}
        candidates = generate_route_candidates(graph, spt, direct_map)

        added, modified, deleted = self.rib.update_from_candidates(candidates)

        # Synchronize Kernel FIB
        for r in added + modified:
            self.route_installer.install_route(r)
        for r in deleted:
            self.route_installer.remove_route(r)

        duration = time.monotonic() - start_ts
        self.metrics.record_spf_run(duration)
        self.metrics.set_gauge("routes_total", float(self.rib.count()))
        logger.info(
            "[%s] SPF recalculated in %.3f ms: %d routes (added: %d, mod: %d, del: %d)",
            self.router_id,
            duration * 1000.0,
            self.rib.count(),
            len(added),
            len(modified),
            len(deleted),
        )

    # Periodic background loops
    async def _hello_loop(self) -> None:
        while self.is_running:
            for iface in self.interfaces.values():
                if iface.is_up:
                    active_neighs = [n.router_id for n in self.neighbors.values()]
                    hello_pkt = self.hello_handler.create_hello(
                        interface_mask=iface.netmask,
                        hello_interval=iface.hello_interval,
                        dead_interval=iface.dead_interval,
                        router_priority=iface.router_priority,
                        designated_router=iface.designated_router,
                        backup_designated_router=iface.backup_designated_router,
                        known_neighbors=active_neighs,
                    )
                    raw_hello = serialize_packet(hello_pkt)
                    self.send_raw_packet(raw_hello, iface.name, "224.0.0.5", iface.udp_port)

            await asyncio.sleep(min(iface.hello_interval for iface in self.interfaces.values()))

    async def _dead_timer_loop(self) -> None:
        while self.is_running:
            now = time.monotonic()
            for n_id, neigh in list(self.neighbors.items()):
                if neigh.is_dead(now) and neigh.state != NeighborState.DOWN:
                    logger.warning(
                        "[%s] Neighbor %s dead timer expired; tearing down adjacency",
                        self.router_id,
                        n_id,
                    )
                    neigh.trigger_event(NeighborEvent.INACTIVITY_TIMER)

            # Also tick LSA ages
            self.aging_manager.tick(1)
            await asyncio.sleep(1.0)

    def handle_api_command(self, cmd_line: str) -> dict[str, Any]:
        """Handle CLI inspection queries."""
        tokens = cmd_line.strip().split()
        sub = tokens[1] if len(tokens) > 1 else "status"

        match sub:
            case "interfaces":
                return {
                    "router_id": self.router_id,
                    "interfaces": [
                        {
                            "name": iface.name,
                            "ip_address": iface.ip_address,
                            "netmask": iface.netmask,
                            "cidr": iface.cidr,
                            "area_id": iface.area_id,
                            "is_up": iface.is_up,
                            "metric": iface.metric,
                            "hello_interval": iface.hello_interval,
                            "dead_interval": iface.dead_interval,
                            "designated_router": iface.designated_router,
                        }
                        for iface in self.interfaces.values()
                    ],
                }

            case "neighbors":
                return {
                    "router_id": self.router_id,
                    "neighbors": [
                        {
                            "router_id": n.router_id,
                            "ip_address": n.ip_address,
                            "interface_name": n.interface_name,
                            "state": n.state.name,
                            "priority": n.router_priority,
                            "dead_time_remaining": max(
                                0, int(n.dead_interval - (time.monotonic() - n.last_received_hello))
                            ),
                        }
                        for n in self.neighbors.values()
                    ],
                }

            case "lsdb":
                return {
                    "router_id": self.router_id,
                    "area_id": self.area_id,
                    "lsas": [
                        {
                            "ls_type": lsa.header.ls_type.name,
                            "link_state_id": lsa.header.link_state_id,
                            "advertising_router": lsa.header.advertising_router,
                            "ls_age": lsa.header.ls_age,
                            "ls_sequence_number": lsa.header.ls_sequence_number,
                            "ls_checksum": lsa.header.ls_checksum,
                            "length": lsa.header.length,
                        }
                        for lsa in self.lsdb.all_lsas()
                    ],
                }

            case "routes":
                prefix_filter = tokens[2] if len(tokens) > 2 else None
                all_r = self.rib.all_routes()
                if prefix_filter:
                    all_r = [r for r in all_r if r.destination.startswith(prefix_filter)]
                return {
                    "router_id": self.router_id,
                    "routes": [
                        {
                            "destination": r.destination,
                            "metric": r.metric,
                            "admin_distance": r.admin_distance,
                            "route_type": r.route_type.name,
                            "next_hops": [str(nh) for nh in r.next_hops],
                        }
                        for r in all_r
                    ],
                }

            case "spf":
                snap = self.metrics.snapshot()
                raw_spf_sum = snap.get("spf_summary")
                spf_sum = raw_spf_sum if isinstance(raw_spf_sum, dict) else {}
                return {
                    "router_id": self.router_id,
                    "total_runs": spf_sum.get("total_runs", 0),
                    "avg_duration_ms": spf_sum.get("avg_duration_ms", 0.0),
                    "last_duration_ms": spf_sum.get("last_duration_ms", 0.0),
                }

            case "statistics":
                return {
                    "router_id": self.router_id,
                    "metrics": self.metrics.snapshot(),
                    "health": self.health_checker.check(),
                }

            case _:
                return {"status": "ok", "router_id": self.router_id, "healthy": True}

    async def start(self) -> None:
        """Start daemon background tasks and sockets."""
        logger.info("Starting Mini-OSPF Daemon for router_id=%s (Area %s)", self.router_id, self.area_id)
        self.is_running = True

        if not self.use_mock_sockets:
            for ifname, backend in self.socket_backends.items():
                self.receiver.register_interface(backend, ifname)

        if self.api_server:
            await self.api_server.start()

        # Generate initial Router-LSA and calculate baseline SPF
        self.generate_self_router_lsa()
        self.run_spf_calculation()

        # Launch periodic tasks
        self._tasks.append(asyncio.create_task(self._hello_loop()))
        self._tasks.append(asyncio.create_task(self._dead_timer_loop()))

    async def stop(self) -> None:
        """Gracefully stop daemon."""
        logger.info("Stopping Mini-OSPF Daemon %s", self.router_id)
        self.is_running = False

        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

        self.receiver.stop()
        if self.api_server:
            await self.api_server.stop()

        for backend in self.socket_backends.values():
            backend.close()


def run_daemon_from_config(config_path: str, simulate: bool = False) -> int:
    """Entry point for running daemon from CLI."""
    config = load_config_file(config_path)
    setup_logging(
        level=config.logging.level,
        log_format=config.logging.format,
        log_file=config.logging.file,
    )

    # On Windows, real UDP multicast/raw sockets require admin rights and are not
    # available without proper network interfaces. Auto-enable simulation mode.
    use_mock = simulate or sys.platform == "win32"
    if use_mock and not simulate:
        logger.info(
            "Windows detected: running in simulation mode (mock sockets). "
            "Use Linux for live packet exchange."
        )

    daemon = OSPFDaemon(config, use_mock_sockets=use_mock)

    async def _runner() -> None:
        await daemon.start()
        stop_event = asyncio.Event()

        def _handle_signal() -> None:
            logger.info("Signal received, stopping...")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handle_signal)
            except (NotImplementedError, AttributeError):
                # Windows: add_signal_handler is not supported on ProactorEventLoop.
                # Register a plain signal handler as fallback.
                import signal as _signal

                def _win_signal_handler(signum: int, frame: object) -> None:  # noqa: ARG001
                    stop_event.set()

                _signal.signal(sig, _win_signal_handler)

        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await daemon.stop()

    try:
        asyncio.run(_runner())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        logger.error("Daemon crashed: %s", e, exc_info=True)
        return 1


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: mini-ospf-daemon <config.yaml>")
        sys.exit(1)
    sys.exit(run_daemon_from_config(sys.argv[1]))


if __name__ == "__main__":
    main()
