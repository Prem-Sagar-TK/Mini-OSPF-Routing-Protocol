"""
OSPFv2 Packet and LSA Dataclasses (RFC 2328).
"""

from dataclasses import dataclass, field

from mini_ospf.protocol.constants import (
    LSAType,
    OSPFPacketType,
    RouterLinkType,
)


@dataclass(slots=True)
class OSPFHeader:
    version: int = 2
    type: OSPFPacketType = OSPFPacketType.HELLO
    packet_length: int = 24
    router_id: str = "0.0.0.0"
    area_id: str = "0.0.0.0"
    checksum: int = 0
    autype: int = 0
    auth_data: bytes = b"\x00" * 8


@dataclass(slots=True)
class HelloPacket:
    header: OSPFHeader = field(default_factory=OSPFHeader)
    network_mask: str = "255.255.255.0"
    hello_interval: int = 10
    options: int = 0x02  # E-bit (standard area)
    router_priority: int = 1
    dead_interval: int = 40
    designated_router: str = "0.0.0.0"
    backup_designated_router: str = "0.0.0.0"
    neighbors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LSAHeader:
    ls_age: int = 0
    options: int = 0x02
    ls_type: LSAType = LSAType.ROUTER
    link_state_id: str = "0.0.0.0"
    advertising_router: str = "0.0.0.0"
    ls_sequence_number: int = -0x7FFFFFFF  # 0x80000001
    ls_checksum: int = 0
    length: int = 20

    @property
    def key(self) -> tuple[LSAType, str, str]:
        """Unique LSA identifier tuple: (type, link_state_id, advertising_router)."""
        return (self.ls_type, self.link_state_id, self.advertising_router)


@dataclass(slots=True)
class DatabaseDescriptionPacket:
    header: OSPFHeader = field(default_factory=lambda: OSPFHeader(type=OSPFPacketType.DATABASE_DESCRIPTION))
    interface_mtu: int = 1500
    options: int = 0x02
    flags: int = 0  # Init, More, Master/Slave
    sequence_number: int = 0
    lsa_headers: list[LSAHeader] = field(default_factory=list)


@dataclass(slots=True)
class LSRRequestItem:
    ls_type: LSAType
    link_state_id: str
    advertising_router: str

    @property
    def key(self) -> tuple[LSAType, str, str]:
        return (self.ls_type, self.link_state_id, self.advertising_router)


@dataclass(slots=True)
class LinkStateRequestPacket:
    header: OSPFHeader = field(default_factory=lambda: OSPFHeader(type=OSPFPacketType.LINK_STATE_REQUEST))
    requests: list[LSRRequestItem] = field(default_factory=list)


@dataclass(slots=True)
class RouterLink:
    link_id: str  # Neighbor Router ID or Network DR IP or Subnet IP
    link_data: str  # Router interface IP or Subnet mask
    link_type: RouterLinkType
    num_tos: int = 0
    metric: int = 10


@dataclass(slots=True)
class RouterLSA:
    header: LSAHeader = field(default_factory=lambda: LSAHeader(ls_type=LSAType.ROUTER))
    flags: int = 0  # Bit V (virtual), E (asbr), B (abr)
    num_links: int = 0
    links: list[RouterLink] = field(default_factory=list)


@dataclass(slots=True)
class NetworkLSA:
    header: LSAHeader = field(default_factory=lambda: LSAHeader(ls_type=LSAType.NETWORK))
    network_mask: str = "255.255.255.0"
    attached_routers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SummaryLSA:
    header: LSAHeader = field(default_factory=lambda: LSAHeader(ls_type=LSAType.SUMMARY_IP))
    network_mask: str = "255.255.255.0"
    metric: int = 10


# Union type for full LSA instances
type AnyLSA = RouterLSA | NetworkLSA | SummaryLSA


@dataclass(slots=True)
class LinkStateUpdatePacket:
    header: OSPFHeader = field(default_factory=lambda: OSPFHeader(type=OSPFPacketType.LINK_STATE_UPDATE))
    num_lsas: int = 0
    lsas: list[AnyLSA] = field(default_factory=list)


@dataclass(slots=True)
class LinkStateAckPacket:
    header: OSPFHeader = field(default_factory=lambda: OSPFHeader(type=OSPFPacketType.LINK_STATE_ACK))
    lsa_headers: list[LSAHeader] = field(default_factory=list)
