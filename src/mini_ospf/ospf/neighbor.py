"""
OSPF Neighbor Data Structure and Management.
"""

import time
from collections.abc import Callable

from mini_ospf.lsdb.synchronization import NeighborSyncState
from mini_ospf.ospf.neighbor_fsm import NeighborEvent, NeighborFSM, NeighborState


class Neighbor:
    """
    Represents an active or discovered neighbor router on an interface.
    """

    def __init__(
        self,
        router_id: str,
        ip_address: str,
        interface_name: str,
        dead_interval: int = 40,
        on_state_change: Callable[[NeighborState, NeighborState, NeighborEvent], None] | None = None,
    ) -> None:
        self.router_id: str = router_id
        self.ip_address: str = ip_address
        self.interface_name: str = interface_name
        self.dead_interval: int = dead_interval

        # FSM and State
        self.fsm: NeighborFSM = NeighborFSM(
            router_id="local",
            neighbor_id=router_id,
            on_state_change=on_state_change,
        )

        # DR / BDR
        self.router_priority: int = 1
        self.designated_router: str = "0.0.0.0"
        self.backup_designated_router: str = "0.0.0.0"

        # DBD Negotiation
        self.is_master: bool = False
        self.dd_sequence_number: int = 0
        self.options: int = 0x02

        # Sync Lists
        self.sync_state: NeighborSyncState = NeighborSyncState()

        # Timers / Liveness
        self.last_received_hello: float = time.monotonic()

    @property
    def state(self) -> NeighborState:
        return self.fsm.state

    def is_full(self) -> bool:
        return self.state == NeighborState.FULL

    def is_adjacent(self) -> bool:
        return self.state in (
            NeighborState.EXSTART,
            NeighborState.EXCHANGE,
            NeighborState.LOADING,
            NeighborState.FULL,
        )

    def touch(self) -> None:
        """Reset the inactivity timer on receiving a packet."""
        self.last_received_hello = time.monotonic()

    def is_dead(self, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        return (current - self.last_received_hello) > self.dead_interval

    def trigger_event(self, event: NeighborEvent) -> NeighborState:
        return self.fsm.handle_event(event)
