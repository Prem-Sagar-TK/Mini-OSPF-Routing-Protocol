"""
OSPF Reliable Flooding Engine (RFC 2328 Section 13.3).
"""

import logging
from collections.abc import Callable
from typing import Any

from mini_ospf.ospf.neighbor import Neighbor
from mini_ospf.protocol.packet import AnyLSA
from mini_ospf.protocol.serializer import serialize_packet

logger = logging.getLogger("mini_ospf.ospf.flooding")


class FloodingEngine:
    """
    Coordinates reliable LSA flooding across interfaces and maintains neighbor retransmissions.
    """

    def __init__(
        self,
        router_id: str,
        area_id: str = "0.0.0.0",
        send_raw_func: Callable[..., Any] | None = None,
    ) -> None:
        self.router_id = router_id
        self.area_id = area_id
        self.send_raw_func = send_raw_func

    def flood_lsa(
        self,
        lsa: AnyLSA,
        neighbors: dict[str, Neighbor],
        exclude_neighbor_id: str | None = None,
    ) -> list[str]:
        """
        Flood an LSA to all adjacent (FULL or EXCHANGE) neighbors except the excluded neighbor.
        Returns list of neighbor IDs flooded to.
        """
        target_neighbors: list[Neighbor] = []
        for n_id, n in neighbors.items():
            if n_id == exclude_neighbor_id:
                continue
            if n.is_adjacent():
                target_neighbors.append(n)
                n.sync_state.add_to_retransmit_list(lsa)

        if not target_neighbors:
            return []

        # Construct LSU
        from mini_ospf.ospf.link_state_update import LSUHandler

        handler = LSUHandler(self.router_id, self.area_id)
        lsu = handler.create_lsu_packet([lsa])
        raw_pkt = serialize_packet(lsu)

        flooded_to: list[str] = []
        for n in target_neighbors:
            if self.send_raw_func:
                try:
                    self.send_raw_func(raw_pkt, n.interface_name, n.ip_address)
                    flooded_to.append(n.router_id)
                except Exception as e:
                    logger.error("Failed to flood LSU to neighbor %s: %s", n.router_id, e)

        return flooded_to
