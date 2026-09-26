"""
Link State Acknowledgment (LSAck) packet processing (RFC 2328 Section 13.7).
"""

from mini_ospf.ospf.neighbor import Neighbor
from mini_ospf.protocol.constants import OSPFPacketType
from mini_ospf.protocol.packet import LinkStateAckPacket, LSAHeader, OSPFHeader


class LSAckHandler:
    def __init__(self, router_id: str, area_id: str = "0.0.0.0") -> None:
        self.router_id = router_id
        self.area_id = area_id

    def create_ack_packet(self, headers: list[LSAHeader]) -> LinkStateAckPacket:
        """Create an LSAck packet acknowledging the given LSA headers."""
        hdr = OSPFHeader(
            type=OSPFPacketType.LINK_STATE_ACK,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        return LinkStateAckPacket(header=hdr, lsa_headers=list(headers))

    def process_incoming_ack(
        self,
        ack: LinkStateAckPacket,
        neighbor: Neighbor,
    ) -> int:
        """
        Process an incoming LSAck packet from a neighbor.
        Removes acknowledged LSAs from the neighbor's retransmission list.
        Returns the number of acknowledged LSAs.
        """
        count = 0
        for lsa_hdr in ack.lsa_headers:
            if neighbor.sync_state.acknowledge_lsa(lsa_hdr.key):
                count += 1
        return count
