"""
Neighbor Database Synchronization Lists (RFC 2328 Section 10).
"""

from mini_ospf.lsdb.lsa import is_newer_lsa
from mini_ospf.protocol.constants import LSAType
from mini_ospf.protocol.packet import AnyLSA, LSAHeader, LSRRequestItem


class NeighborSyncState:
    """
    Maintains the 3 RFC 2328 lists used during database exchange:
    1. Database Summary list: LSA headers sent in DBD packets to neighbor.
    2. Link State Request list: LSAs requested from the neighbor.
    3. Link State Retransmission list: LSAs flooded to neighbor that haven't been acknowledged.
    """

    def __init__(self) -> None:
        self.db_summary_list: list[LSAHeader] = []
        self.ls_request_list: dict[tuple[LSAType, str, str], LSRRequestItem] = {}
        self.ls_retransmission_list: dict[tuple[LSAType, str, str], AnyLSA] = {}

    def populate_summary_list(self, headers: list[LSAHeader]) -> None:
        """Populate DBD summary list with current LSDB headers."""
        self.db_summary_list = list(headers)

    def next_db_summary_chunk(self, max_headers: int = 50) -> list[LSAHeader]:
        """Pop a batch of LSA headers for the next Database Description packet."""
        chunk = self.db_summary_list[:max_headers]
        self.db_summary_list = self.db_summary_list[max_headers:]
        return chunk

    def has_more_summaries(self) -> bool:
        return len(self.db_summary_list) > 0

    def process_incoming_summary(
        self, received_header: LSAHeader, local_header: LSAHeader | None
    ) -> bool:
        """
        Evaluate an LSA summary header from neighbor's DBD packet.
        If neighbor's LSA is newer than local, add to request list.
        Returns True if added to request list.
        """
        if local_header is None or is_newer_lsa(received_header, local_header):
            item = LSRRequestItem(
                ls_type=received_header.ls_type,
                link_state_id=received_header.link_state_id,
                advertising_router=received_header.advertising_router,
            )
            self.ls_request_list[item.key] = item
            return True
        return False

    def remove_from_request_list(self, key: tuple[LSAType, str, str]) -> bool:
        return self.ls_request_list.pop(key, None) is not None

    def add_to_retransmit_list(self, lsa: AnyLSA) -> None:
        self.ls_retransmission_list[lsa.header.key] = lsa

    def acknowledge_lsa(self, key: tuple[LSAType, str, str]) -> bool:
        return self.ls_retransmission_list.pop(key, None) is not None

    def is_loading_complete(self) -> bool:
        return len(self.ls_request_list) == 0

    def clear(self) -> None:
        self.db_summary_list.clear()
        self.ls_request_list.clear()
        self.ls_retransmission_list.clear()
