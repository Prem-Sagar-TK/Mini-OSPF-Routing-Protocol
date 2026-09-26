"""
Application daemon and lifecycle supervision.
"""

from mini_ospf.app.daemon import OSPFDaemon, run_daemon_from_config
from mini_ospf.app.dependencies import DaemonDependencies
from mini_ospf.app.lifecycle import DaemonLifecycleState, LifecycleManager

__all__ = [
    "DaemonDependencies",
    "DaemonLifecycleState",
    "LifecycleManager",
    "OSPFDaemon",
    "run_daemon_from_config",
]
