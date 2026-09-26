"""
Database Description (DBD) packet exchange logic (RFC 2328 Section 10.6 & 10.8).
"""

import logging

from mini_ospf.lsdb.database import LinkStateDatabase
from mini_ospf.ospf.neighbor import Neighbor
from mini_ospf.ospf.neighbor_fsm import NeighborEvent, NeighborState
from mini_ospf.protocol.constants import (
    DBD_FLAG_I,
    DBD_FLAG_M,
    DBD_FLAG_MS,
    OSPFPacketType,
)
from mini_ospf.protocol.packet import DatabaseDescriptionPacket, OSPFHeader

logger = logging.getLogger("mini_ospf.ospf.dbd")


class DBDHandler:
    def __init__(self, router_id: str, area_id: str = "0.0.0.0") -> None:
        self.router_id = router_id
        self.area_id = area_id

    def create_initial_dbd(self, neighbor: Neighbor, sequence_number: int) -> DatabaseDescriptionPacket:
        """Create initial Master ExStart DBD packet (Init=1, More=1, Master=1)."""
        flags = DBD_FLAG_I | DBD_FLAG_M | DBD_FLAG_MS
        neighbor.is_master = True
        neighbor.dd_sequence_number = sequence_number

        hdr = OSPFHeader(
            type=OSPFPacketType.DATABASE_DESCRIPTION,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        return DatabaseDescriptionPacket(
            header=hdr,
            interface_mtu=1500,
            options=0x02,
            flags=flags,
            sequence_number=sequence_number,
            lsa_headers=[],
        )

    def create_dbd_summary(
        self, neighbor: Neighbor, lsdb: LinkStateDatabase
    ) -> DatabaseDescriptionPacket:
        """Create an Exchange DBD packet populated with LSA summary headers."""
        if not neighbor.sync_state.db_summary_list:
            neighbor.sync_state.populate_summary_list(lsdb.get_headers())

        headers_chunk = neighbor.sync_state.next_db_summary_chunk(max_headers=30)
        has_more = neighbor.sync_state.has_more_summaries()

        flags = 0
        if has_more:
            flags |= DBD_FLAG_M
        if neighbor.is_master:
            flags |= DBD_FLAG_MS

        hdr = OSPFHeader(
            type=OSPFPacketType.DATABASE_DESCRIPTION,
            router_id=self.router_id,
            area_id=self.area_id,
        )
        return DatabaseDescriptionPacket(
            header=hdr,
            interface_mtu=1500,
            options=0x02,
            flags=flags,
            sequence_number=neighbor.dd_sequence_number,
            lsa_headers=headers_chunk,
        )

    def process_incoming_dbd(
        self,
        dbd: DatabaseDescriptionPacket,
        neighbor: Neighbor,
        lsdb: LinkStateDatabase,
    ) -> DatabaseDescriptionPacket | None:
        """
        Process an incoming DBD packet from neighbor according to RFC 2328 Section 10.6.
        Returns a response DBD packet if required (e.g. Master/Slave response), else None.
        """
        sender = dbd.header.router_id
        is_init = bool(dbd.flags & DBD_FLAG_I)
        is_more = bool(dbd.flags & DBD_FLAG_M)
        is_master = bool(dbd.flags & DBD_FLAG_MS)

        if neighbor.state == NeighborState.EXSTART:
            # ExStart Master/Slave negotiation
            if is_init and is_more and is_master and len(dbd.lsa_headers) == 0:
                # Neighbor claims to be Master
                if sender > self.router_id:
                    # Neighbor has higher router ID -> Accept as Master; we become Slave
                    neighbor.is_master = False
                    neighbor.dd_sequence_number = dbd.sequence_number
                    neighbor.trigger_event(NeighborEvent.NEGOTIATION_DONE)
                    # Prepare our summary list and send response with Master's sequence number
                    neighbor.sync_state.populate_summary_list(lsdb.get_headers())
                    return self.create_dbd_summary(neighbor, lsdb)
                else:
                    # We have higher router ID -> We remain Master; ignore or retransmit our initial DBD
                    return None

            elif not is_init and not is_master and dbd.sequence_number == neighbor.dd_sequence_number:
                # We are Master and neighbor responded as Slave with our sequence number
                neighbor.is_master = True
                neighbor.trigger_event(NeighborEvent.NEGOTIATION_DONE)
                # Send our next DBD packet with incremented sequence number
                neighbor.dd_sequence_number += 1
                return self.create_dbd_summary(neighbor, lsdb)

        elif neighbor.state == NeighborState.EXCHANGE:
            # Process received summary headers
            for lsa_hdr in dbd.lsa_headers:
                local_lsa = lsdb.get(
                    lsa_hdr.ls_type, lsa_hdr.link_state_id, lsa_hdr.advertising_router
                )
                local_hdr = local_lsa.header if local_lsa else None
                neighbor.sync_state.process_incoming_summary(lsa_hdr, local_hdr)

            if not is_more and not neighbor.sync_state.has_more_summaries():
                # Both sides finished sending summaries
                if neighbor.sync_state.is_loading_complete():
                    neighbor.trigger_event(NeighborEvent.LOADING_DONE)
                else:
                    neighbor.trigger_event(NeighborEvent.EXCHANGE_DONE)

            if not neighbor.is_master:
                # Slave sends DBD response echoing Master's sequence number
                neighbor.dd_sequence_number = dbd.sequence_number
                return self.create_dbd_summary(neighbor, lsdb)
            else:
                # Master increments sequence number for next DBD chunk
                if neighbor.sync_state.has_more_summaries():
                    neighbor.dd_sequence_number += 1
                    return self.create_dbd_summary(neighbor, lsdb)

        return None
