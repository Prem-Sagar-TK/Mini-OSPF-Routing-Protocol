"""
Virtual Packet Bus for in-process multi-router simulation.

Delivers serialized OSPF packets between router instances without real sockets.
Simulates link delay, packet loss, and link state changes.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("mini_ospf.simulator.bus")


@dataclass
class VirtualLink:
    """Represents a point-to-point virtual link between two routers."""

    router_a: str
    router_b: str
    delay_ms: float = 1.0          # One-way propagation delay
    loss_percent: float = 0.0      # Packet drop probability (0-100)
    is_up: bool = True
    bytes_tx: int = 0
    packets_tx: int = 0
    created_at: float = field(default_factory=time.monotonic)

    @property
    def link_key(self) -> tuple[str, str]:
        return (min(self.router_a, self.router_b), max(self.router_a, self.router_b))


@dataclass
class PacketEvent:
    """Represents a packet in-flight on the virtual bus."""
    src_router_id: str
    dst_router_id: str
    src_ip: str
    dst_ip: str
    ifname_src: str
    ifname_dst: str
    raw_bytes: bytes
    deliver_at: float   # monotonic time when to deliver
    port: int = 8989


class VirtualPacketBus:
    """
    Central message broker for the multi-router simulation.

    Each router registers a receive callback. When a router sends a packet,
    the bus routes it to the correct peer(s), simulating link delay and loss.
    """

    def __init__(self) -> None:
        self._receivers: dict[str, Callable[[bytes, str, str, int], None]] = {}
        self._links: dict[tuple[str, str], VirtualLink] = {}
        self._if_to_router: dict[tuple[str, str], str] = {}   # (router_id, ifname) -> peer_router_id
        self._if_map: dict[tuple[str, str], tuple[str, str]] = {}  # (router_a, ifa) -> (router_b, ifb)
        self._event_log: list[dict[str, Any]] = []
        self._running: bool = False
        self._queue: asyncio.Queue[PacketEvent] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None

    def register_router(
        self,
        router_id: str,
        receive_cb: Callable[[bytes, str, str, int], None],
    ) -> None:
        self._receivers[router_id] = receive_cb
        logger.debug("Bus: registered router %s", router_id)

    def add_link(
        self,
        router_a: str, ifname_a: str, ip_a: str,
        router_b: str, ifname_b: str, ip_b: str,
        delay_ms: float = 1.0,
        loss_percent: float = 0.0,
    ) -> VirtualLink:
        """Add a bidirectional virtual link between two routers."""
        link = VirtualLink(router_a=router_a, router_b=router_b,
                           delay_ms=delay_ms, loss_percent=loss_percent)
        self._links[link.link_key] = link
        # Interface mappings
        self._if_map[(router_a, ifname_a)] = (router_b, ifname_b)
        self._if_map[(router_b, ifname_b)] = (router_a, ifname_a)
        # IP mappings for src_ip on delivery
        self._if_to_router[(router_a, ifname_a)] = router_b
        self._if_to_router[(router_b, ifname_b)] = router_a
        logger.info(
            "Bus: link %s/%s <--> %s/%s (delay=%.1fms loss=%.1f%%)",
            router_a, ifname_a, router_b, ifname_b, delay_ms, loss_percent
        )
        return link

    def get_link(self, router_a: str, router_b: str) -> VirtualLink | None:
        key = (min(router_a, router_b), max(router_a, router_b))
        return self._links.get(key)

    def set_link_state(self, router_a: str, router_b: str, up: bool) -> bool:
        link = self.get_link(router_a, router_b)
        if link is None:
            return False
        link.is_up = up
        self._event_log.append({
            "ts": time.monotonic(),
            "type": "link_up" if up else "link_down",
            "router_a": router_a,
            "router_b": router_b,
        })
        logger.info("Bus: link %s<->%s set to %s", router_a, router_b, "UP" if up else "DOWN")
        return True

    def send_packet(
        self,
        src_router_id: str,
        ifname: str,
        raw_bytes: bytes,
        dest_ip: str,
        dest_port: int,
        src_ip: str,
    ) -> None:
        """Enqueue a packet for delivery to the peer on the given interface."""
        peer_key = self._if_map.get((src_router_id, ifname))
        if peer_key is None:
            return  # No peer connected — stub network

        peer_router_id, peer_ifname = peer_key
        link = self.get_link(src_router_id, peer_router_id)
        if link is None or not link.is_up:
            return  # Link is down

        # Packet loss simulation
        if link.loss_percent > 0 and random.random() * 100 < link.loss_percent:
            logger.debug("Bus: packet dropped on %s->%s (%.1f%% loss)", src_router_id, peer_router_id, link.loss_percent)
            return

        link.bytes_tx += len(raw_bytes)
        link.packets_tx += 1

        deliver_at = time.monotonic() + (link.delay_ms / 1000.0)
        evt = PacketEvent(
            src_router_id=src_router_id,
            dst_router_id=peer_router_id,
            src_ip=src_ip,
            dst_ip=dest_ip,
            ifname_src=ifname,
            ifname_dst=peer_ifname,
            raw_bytes=raw_bytes,
            deliver_at=deliver_at,
            port=dest_port,
        )
        self._queue.put_nowait(evt)

        self._event_log.append({
            "ts": time.monotonic(),
            "type": "packet",
            "src": src_router_id,
            "dst": peer_router_id,
            "bytes": len(raw_bytes),
        })
        if len(self._event_log) > 500:
            self._event_log = self._event_log[-500:]

    async def _deliver_loop(self) -> None:
        """Background coroutine delivering queued packets after their simulated delay."""
        while self._running:
            try:
                evt = await asyncio.wait_for(self._queue.get(), timeout=0.05)
            except TimeoutError:
                continue

            now = time.monotonic()
            wait = evt.deliver_at - now
            if wait > 0:
                await asyncio.sleep(wait)

            recv_cb = self._receivers.get(evt.dst_router_id)
            if recv_cb is not None:
                try:
                    recv_cb(evt.raw_bytes, evt.ifname_dst, evt.src_ip, evt.port)
                except Exception as e:
                    logger.error("Bus: delivery error to %s: %s", evt.dst_router_id, e)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._deliver_loop())
        logger.info("Virtual packet bus started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Virtual packet bus stopped")

    def snapshot(self) -> dict[str, Any]:
        """Return bus state for dashboard consumption."""
        return {
            "links": [
                {
                    "router_a": lnk.router_a,
                    "router_b": lnk.router_b,
                    "delay_ms": lnk.delay_ms,
                    "loss_percent": lnk.loss_percent,
                    "is_up": lnk.is_up,
                    "packets_tx": lnk.packets_tx,
                    "bytes_tx": lnk.bytes_tx,
                }
                for lnk in self._links.values()
            ],
            "recent_events": self._event_log[-20:],
        }
