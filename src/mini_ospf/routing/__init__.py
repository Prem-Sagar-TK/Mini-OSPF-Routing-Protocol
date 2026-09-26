"""
Routing Information Base (RIB) and Next-Hop resolution subsystem.
"""

from mini_ospf.routing.next_hop import NextHop
from mini_ospf.routing.policy import assign_admin_distance
from mini_ospf.routing.rib import RIB
from mini_ospf.routing.route import Route, RouteType

__all__ = [
    "NextHop",
    "RIB",
    "Route",
    "RouteType",
    "assign_admin_distance",
]
