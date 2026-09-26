"""
Lifecycle transitions and state supervision for Mini-OSPF daemons.
"""

import logging
from enum import Enum, auto, unique

logger = logging.getLogger("mini_ospf.app.lifecycle")


@unique
class DaemonLifecycleState(Enum):
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    RUNNING = auto()
    CONVERGING = auto()
    SHUTTING_DOWN = auto()
    STOPPED = auto()


class LifecycleManager:
    def __init__(self, router_id: str) -> None:
        self.router_id = router_id
        self.state: DaemonLifecycleState = DaemonLifecycleState.UNINITIALIZED

    def transition_to(self, new_state: DaemonLifecycleState) -> None:
        old_state = self.state
        self.state = new_state
        logger.info(
            "[%s] Daemon lifecycle transition: %s -> %s",
            self.router_id,
            old_state.name,
            new_state.name,
        )
