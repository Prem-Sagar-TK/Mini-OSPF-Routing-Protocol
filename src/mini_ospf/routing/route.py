"""
Route representations in the Routing Information Base (RIB).
"""

import time
from dataclasses import dataclass, field
from enum import Enum, auto, unique

from mini_ospf.routing.next_hop import NextHop


@unique
class RouteType(Enum):
    INTRA_AREA = auto()
    INTER_AREA = auto()
    EXTERNAL_TYPE_1 = auto()
    EXTERNAL_TYPE_2 = auto()
    CONNECTED = auto()
    STATIC = auto()


@dataclass(slots=True)
class Route:
    prefix: str
    prefix_length: int = 32
    metric: int = 10
    admin_distance: int = 110  # Standard OSPF Administrative Distance
    next_hops: list[NextHop] = field(default_factory=list)
    route_type: RouteType = RouteType.INTRA_AREA
    source: str = "ospf"
    created_at: float = field(default_factory=time.time)

    @property
    def destination(self) -> str:
        return f"{self.prefix}/{self.prefix_length}"

    def __str__(self) -> str:
        nh_str = ", ".join(str(nh) for nh in self.next_hops) if self.next_hops else "direct"
        return f"{self.destination} metric {self.metric} [{self.admin_distance}] {nh_str}"
