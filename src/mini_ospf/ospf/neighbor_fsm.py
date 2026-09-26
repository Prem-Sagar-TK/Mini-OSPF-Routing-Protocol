"""
OSPF Neighbor Finite State Machine (RFC 2328 Section 10.1 - 10.3).
"""

import logging
from collections.abc import Callable
from enum import Enum, auto, unique

logger = logging.getLogger("mini_ospf.neighbor_fsm")


@unique
class NeighborState(Enum):
    DOWN = auto()
    ATTEMPT = auto()
    INIT = auto()
    TWO_WAY = auto()
    EXSTART = auto()
    EXCHANGE = auto()
    LOADING = auto()
    FULL = auto()


@unique
class NeighborEvent(Enum):
    HELLO_RECEIVED = auto()
    START = auto()
    TWO_WAY_RECEIVED = auto()
    ONE_WAY_RECEIVED = auto()
    NEGOTIATION_DONE = auto()
    EXCHANGE_DONE = auto()
    BAD_LS_REQ = auto()
    LOADING_DONE = auto()
    ADJACENCY_OK = auto()
    SEQ_NUMBER_MISMATCH = auto()
    KILL_NEIGHBOR = auto()
    INACTIVITY_TIMER = auto()
    LL_DOWN = auto()


class NeighborFSM:
    """
    Deterministic implementation of the OSPF Neighbor State Machine.
    """

    def __init__(
        self,
        router_id: str,
        neighbor_id: str,
        on_state_change: Callable[[NeighborState, NeighborState, NeighborEvent], None] | None = None,
    ) -> None:
        self.router_id = router_id
        self.neighbor_id = neighbor_id
        self.state: NeighborState = NeighborState.DOWN
        self.on_state_change = on_state_change

    def handle_event(self, event: NeighborEvent) -> NeighborState:
        """Process an FSM event and transition state deterministically."""
        old_state = self.state
        new_state = self._next_state(old_state, event)

        if new_state != old_state:
            logger.info(
                "[%s] Neighbor %s FSM transition: %s -> %s on event %s",
                self.router_id,
                self.neighbor_id,
                old_state.name,
                new_state.name,
                event.name,
            )
            self.state = new_state
            if self.on_state_change:
                try:
                    self.on_state_change(old_state, new_state, event)
                except Exception as e:
                    logger.error("Error in on_state_change callback: %s", e)

        return self.state

    def _next_state(self, current: NeighborState, event: NeighborEvent) -> NeighborState:
        # Common teardown events from any state
        if event in (NeighborEvent.KILL_NEIGHBOR, NeighborEvent.LL_DOWN, NeighborEvent.INACTIVITY_TIMER):
            return NeighborState.DOWN

        if event == NeighborEvent.ONE_WAY_RECEIVED:
            return NeighborState.INIT

        if event in (NeighborEvent.SEQ_NUMBER_MISMATCH, NeighborEvent.BAD_LS_REQ):
            if current in (
                NeighborState.EXCHANGE,
                NeighborState.LOADING,
                NeighborState.FULL,
            ):
                return NeighborState.EXSTART
            return current

        match current:
            case NeighborState.DOWN:
                if event in (NeighborEvent.START, NeighborEvent.HELLO_RECEIVED):
                    return NeighborState.INIT
                return NeighborState.DOWN

            case NeighborState.ATTEMPT:
                if event == NeighborEvent.HELLO_RECEIVED:
                    return NeighborState.INIT
                return NeighborState.ATTEMPT

            case NeighborState.INIT:
                if event == NeighborEvent.TWO_WAY_RECEIVED:
                    # In P2P or Broadcast where adjacency should form:
                    return NeighborState.EXSTART
                elif event == NeighborEvent.HELLO_RECEIVED:
                    return NeighborState.INIT
                return NeighborState.INIT

            case NeighborState.TWO_WAY:
                if event == NeighborEvent.ADJACENCY_OK:
                    return NeighborState.EXSTART
                return NeighborState.TWO_WAY

            case NeighborState.EXSTART:
                if event == NeighborEvent.NEGOTIATION_DONE:
                    return NeighborState.EXCHANGE
                return NeighborState.EXSTART

            case NeighborState.EXCHANGE:
                if event == NeighborEvent.EXCHANGE_DONE:
                    return NeighborState.LOADING
                elif event == NeighborEvent.LOADING_DONE:
                    return NeighborState.FULL
                return NeighborState.EXCHANGE

            case NeighborState.LOADING:
                if event == NeighborEvent.LOADING_DONE:
                    return NeighborState.FULL
                return NeighborState.LOADING

            case NeighborState.FULL:
                return NeighborState.FULL

        return current
