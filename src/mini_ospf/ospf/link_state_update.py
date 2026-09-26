"""
Link State Update (LSU) processing and generation (RFC 2328 Section 13).
"""

import logging

from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.ospf.neighbor import Neighbor
from mini_ospf.ospf.neighbor_fsm import NeighborEvent, NeighborState
from mini_ospf.protocol.constants import OSPFPacketType
from mini_ospf.protocol.packet import (
    AnyLSA,
    LinkStateAckPacket,
    LinkStateUpdatePacket,
    LSAHeader,
    OSPFHeader,
)

logger = logging.getLogger("mini_ospf.ospf.lsu")


class LSUHandler:
    def __init__(self, router_id: str, area_id: str = "0.0.0.0") -> None:
        self.router_id = router_id
        self.area_id = area_id

    def create_lsu_packet(self, lsas: list[AnyLSA]) -> LinkStateUpdatePacket:
        """Create an LSU packet with the given list of LSAs."""
        hdr = OSPFHeader(
            type=OSPFPacketType.LINK_STATE_UPDATE,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        return LinkStateUpdatePacket(header=hdr, num_lsas=len(lsas), lsas=lsas)

    def process_incoming_lsu(
        self,
        lsu: LinkStateUpdatePacket,
        neighbor: Neighbor,
        lsdb: LinkStateDatabase,
    ) -> tuple[list[AnyLSA], LinkStateAckPacket]:
        """
        Process incoming LSU from a neighbor:
        1. Install or update valid LSAs into the LSDB.
        2. Remove received LSAs from the neighbor's Request list.
        3. Check if loading is complete.
        4. Return newly installed LSAs for flooding and an acknowledgment packet.
        """
        installed_lsas: list[AnyLSA] = []
        acknowledged_headers: list[LSAHeader] = []

        for lsa in lsu.lsas:
            installed, reason = lsdb.install(lsa)
            key = lsa.header.key

            # Acknowledge the LSA
            acknowledged_headers.append(lsa.header)

            # If neighbor was requesting this LSA, remove it from the request list
            neighbor.sync_state.remove_from_request_list(key)

            if installed:
                logger.debug(
                    "[%s] Installed LSA (%s, %s) from %s: %s",
                    self.router_id,
                    lsa.header.ls_type,
                    lsa.header.link_state_id,
                    neighbor.router_id,
                    reason,
                )
                installed_lsas.append(lsa)

        # Check if loading completed
        if neighbor.state == NeighborState.LOADING and neighbor.sync_state.is_loading_complete():
            neighbor.trigger_event(NeighborEvent.LOADING_DONE)

        ack_hdr = OSPFHeader(
            type=OSPFPacketType.LINK_STATE_ACK,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        ack_packet = LinkStateAckPacket(header=ack_hdr, lsa_headers=acknowledged_headers)

        return installed_lsas, ack_packet
