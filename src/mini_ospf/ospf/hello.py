"""
OSPF Hello Packet Generation and Processing (RFC 2328 Section 9.5 & 10.5).
"""

from mini_ospf.ospf.neighbor import Neighbor
from mini_ospf.ospf.neighbor_fsm import NeighborEvent, NeighborState
from mini_ospf.protocol.constants import OSPFPacketType
from mini_ospf.protocol.packet import HelloPacket, OSPFHeader


class HelloHandler:
    """
    Handles generation of periodic Hello packets and processing of received Hello packets.
    """

    def __init__(self, router_id: str, area_id: str = "0.0.0.0") -> None:
        self.router_id = router_id
        self.area_id = area_id

    def create_hello(
        self,
        interface_mask: str,
        hello_interval: int,
        dead_interval: int,
        router_priority: int,
        designated_router: str,
        backup_designated_router: str,
        known_neighbors: list[str],
    ) -> HelloPacket:
        """Construct an outgoing Hello packet."""
        hdr = OSPFHeader(
            type=OSPFPacketType.HELLO,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        return HelloPacket(
            header=hdr,
            network_mask=interface_mask,
            hello_interval=hello_interval,
            dead_interval=dead_interval,
            router_priority=router_priority,
            designated_router=designated_router,
            backup_designated_router=backup_designated_router,
            neighbors=list(known_neighbors),
        )

    def process_incoming_hello(
        self,
        hello: HelloPacket,
        src_ip: str,
        interface_name: str,
        neighbors: dict[str, Neighbor],
    ) -> tuple[Neighbor, bool]:
        """
        Process an incoming Hello packet on an interface.
        Returns tuple of (Neighbor instance, is_new_neighbor: bool).
        """
        sender_rtr_id = hello.header.router_id
        neighbor = neighbors.get(sender_rtr_id)
        is_new = False

        if neighbor is None:
            neighbor = Neighbor(
                router_id=sender_rtr_id,
                ip_address=src_ip,
                interface_name=interface_name,
                dead_interval=hello.dead_interval,
            )
            neighbor.fsm.router_id = self.router_id
            neighbors[sender_rtr_id] = neighbor
            neighbor.trigger_event(NeighborEvent.HELLO_RECEIVED)
            is_new = True

        neighbor.touch()
        neighbor.router_priority = hello.router_priority
        neighbor.designated_router = hello.designated_router
        neighbor.backup_designated_router = hello.backup_designated_router

        # Check if our own router ID is in the neighbor's list of active neighbors (2-Way)
        if self.router_id in hello.neighbors:
            if neighbor.state == NeighborState.INIT:
                neighbor.trigger_event(NeighborEvent.TWO_WAY_RECEIVED)
        else:
            # We are not in neighbor's list -> 1-Way
            if neighbor.state != NeighborState.INIT and neighbor.state != NeighborState.DOWN:
                neighbor.trigger_event(NeighborEvent.ONE_WAY_RECEIVED)

        return neighbor, is_new
