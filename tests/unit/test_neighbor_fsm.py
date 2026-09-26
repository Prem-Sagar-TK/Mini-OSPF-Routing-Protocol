"""
Unit tests for the OSPF Neighbor Finite State Machine (RFC 2328 Section 10).
"""

from mini_ospf.ospf.neighbor_fsm import NeighborEvent, NeighborFSM, NeighborState


def test_normal_adjacency_formation() -> None:
    fsm = NeighborFSM(router_id="1.1.1.1", neighbor_id="2.2.2.2")
    assert fsm.state == NeighborState.DOWN

    # 1. Hello received -> INIT
    fsm.handle_event(NeighborEvent.HELLO_RECEIVED)
    assert fsm.state == NeighborState.INIT

    # 2. 2-Way received (saw own router ID in hello) -> EXSTART
    fsm.handle_event(NeighborEvent.TWO_WAY_RECEIVED)
    assert fsm.state == NeighborState.EXSTART

    # 3. Master/Slave negotiation complete -> EXCHANGE
    fsm.handle_event(NeighborEvent.NEGOTIATION_DONE)
    assert fsm.state == NeighborState.EXCHANGE

    # 4. Exchange done -> LOADING
    fsm.handle_event(NeighborEvent.EXCHANGE_DONE)
    assert fsm.state == NeighborState.LOADING

    # 5. Loading done (all requested LSAs received) -> FULL
    fsm.handle_event(NeighborEvent.LOADING_DONE)
    assert fsm.state == NeighborState.FULL


def test_inactivity_timer_teardown() -> None:
    fsm = NeighborFSM(router_id="1.1.1.1", neighbor_id="2.2.2.2")
    fsm.handle_event(NeighborEvent.HELLO_RECEIVED)
    fsm.handle_event(NeighborEvent.TWO_WAY_RECEIVED)
    fsm.handle_event(NeighborEvent.NEGOTIATION_DONE)
    fsm.handle_event(NeighborEvent.LOADING_DONE)
    assert fsm.state == NeighborState.FULL

    # Inactivity timer expires -> DOWN
    fsm.handle_event(NeighborEvent.INACTIVITY_TIMER)
    assert fsm.state == NeighborState.DOWN


def test_sequence_number_mismatch_resets_to_exstart() -> None:
    fsm = NeighborFSM(router_id="1.1.1.1", neighbor_id="2.2.2.2")
    fsm.handle_event(NeighborEvent.HELLO_RECEIVED)
    fsm.handle_event(NeighborEvent.TWO_WAY_RECEIVED)
    fsm.handle_event(NeighborEvent.NEGOTIATION_DONE)
    assert fsm.state == NeighborState.EXCHANGE

    # Sequence number mismatch during Exchange -> resets to EXSTART
    fsm.handle_event(NeighborEvent.SEQ_NUMBER_MISMATCH)
    assert fsm.state == NeighborState.EXSTART


def test_one_way_received_drops_to_init() -> None:
    fsm = NeighborFSM(router_id="1.1.1.1", neighbor_id="2.2.2.2")
    fsm.handle_event(NeighborEvent.HELLO_RECEIVED)
    fsm.handle_event(NeighborEvent.TWO_WAY_RECEIVED)
    fsm.handle_event(NeighborEvent.NEGOTIATION_DONE)
    fsm.handle_event(NeighborEvent.LOADING_DONE)
    assert fsm.state == NeighborState.FULL

    # Neighbor forgot us -> ONE_WAY_RECEIVED -> INIT
    fsm.handle_event(NeighborEvent.ONE_WAY_RECEIVED)
    assert fsm.state == NeighborState.INIT
