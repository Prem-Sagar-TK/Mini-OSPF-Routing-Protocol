"""
Link State Request (LSR) processing and generation (RFC 2328 Section 10.7).
"""

import logging

from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.ospf.neighbor import Neighbor
from mini_ospf.protocol.constants import OSPFPacketType
from mini_ospf.protocol.packet import (
    AnyLSA,
    LinkStateRequestPacket,
    LinkStateUpdatePacket,
    OSPFHeader,
)

logger = logging.getLogger("mini_ospf.ospf.lsr")


class LSRHandler:
    def __init__(self, router_id: str, area_id: str = "0.0.0.0") -> None:
        self.router_id = router_id
        self.area_id = area_id

    def create_lsr_packet(self, neighbor: Neighbor, max_items: int = 50) -> LinkStateRequestPacket | None:
        """Create an LSR packet requesting missing or newer LSAs from neighbor."""
        items = list(neighbor.sync_state.ls_request_list.values())[:max_items]
        if not items:
            return None

        hdr = OSPFHeader(
            type=OSPFPacketType.LINK_STATE_REQUEST,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        return LinkStateRequestPacket(header=hdr, requests=items)

    def process_incoming_lsr(
        self,
        lsr: LinkStateRequestPacket,
        lsdb: LinkStateDatabase,
    ) -> LinkStateUpdatePacket:
        """
        Process an incoming LSR packet, looking up each requested LSA in the LSDB,
        and returning a Link State Update packet containing them.
        """
        found_lsas: list[AnyLSA] = []
        for req in lsr.requests:
            lsa = lsdb.get(req.ls_type, req.link_state_id, req.advertising_router)
            if lsa is not None:
                found_lsas.append(lsa)
            else:
                logger.warning(
                    "Requested LSA (%s, %s, %s) not found in local LSDB",
                    req.ls_type,
                    req.link_state_id,
                    req.advertising_router,
                )

        hdr = OSPFHeader(
            type=OSPFPacketType.LINK_STATE_UPDATE,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        return LinkStateUpdatePacket(header=hdr, num_lsas=len(found_lsas), lsas=found_lsas)
