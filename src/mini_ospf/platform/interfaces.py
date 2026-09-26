"""
Network Interface data structures and abstractions.
"""

from dataclasses import dataclass, field

from mini_ospf.protocol.constants import (
    DEFAULT_HELLO_INTERVAL,
    DEFAULT_ROUTER_DEAD_INTERVAL,
    DEFAULT_RXMT_INTERVAL,
    InterfaceType,
)


@dataclass(slots=True)
class Interface:
    name: str
    ip_address: str
    netmask: str = "255.255.255.0"
    area_id: str = "0.0.0.0"
    interface_type: InterfaceType = InterfaceType.BROADCAST
    mtu: int = 1500
    metric: int = 10
    hello_interval: int = DEFAULT_HELLO_INTERVAL
    dead_interval: int = DEFAULT_ROUTER_DEAD_INTERVAL
    rxmt_interval: int = DEFAULT_RXMT_INTERVAL
    router_priority: int = 1
    is_up: bool = True
    udp_port: int = 8989  # Default UDP encapsulation port for non-raw environments

    # DR / BDR election state
    designated_router: str = "0.0.0.0"
    backup_designated_router: str = "0.0.0.0"
    neighbors: dict[str, str] = field(default_factory=dict)  # neighbor_router_id -> neighbor_ip

    @property
    def cidr(self) -> str:
        octets = [int(x) for x in self.netmask.split(".")]
        binary_str = "".join(f"{octet:08b}" for octet in octets)
        prefix_len = binary_str.count("1")
        return f"{self.ip_address}/{prefix_len}"
