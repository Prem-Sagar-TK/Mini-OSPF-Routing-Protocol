"""
Strict validation rules for incoming OSPF packets and LSAs.
"""

from mini_ospf.protocol.checksum import verify_fletcher16, verify_ip_checksum
from mini_ospf.protocol.constants import (
    OSPF_HEADER_LEN,
    OSPF_VERSION,
)
from mini_ospf.protocol.packet import (
    AnyLSA,
    DatabaseDescriptionPacket,
    HelloPacket,
    LinkStateAckPacket,
    LinkStateRequestPacket,
    LinkStateUpdatePacket,
    OSPFHeader,
)
from mini_ospf.protocol.serializer import serialize_lsa


class ValidationError(Exception):
    """Raised when an OSPF packet or LSA fails validation rules."""


def validate_raw_packet(raw_bytes: bytes | bytearray | memoryview) -> None:
    """
    Validate raw packet buffer before parsing.
    Checks minimum length, version, and IP header checksum.
    """
    if len(raw_bytes) < OSPF_HEADER_LEN:
        raise ValidationError(f"Packet too short ({len(raw_bytes)} bytes < {OSPF_HEADER_LEN})")

    version = raw_bytes[0]
    if version != OSPF_VERSION:
        raise ValidationError(f"Unsupported OSPF version {version} (expected {OSPF_VERSION})")

    pkt_len = int.from_bytes(raw_bytes[2:4], "big")
    if pkt_len < OSPF_HEADER_LEN or pkt_len > len(raw_bytes):
        raise ValidationError(f"Invalid packet length field: {pkt_len} (buffer size: {len(raw_bytes)})")

    # Verify IP Checksum over header/body
    pkt_view = memoryview(raw_bytes)[:pkt_len]
    if not verify_ip_checksum(pkt_view):
        raise ValidationError("OSPF packet checksum mismatch")


def validate_header_context(
    hdr: OSPFHeader, expected_area_id: str, self_router_id: str
) -> None:
    """Validate packet header against local router configuration."""
    if hdr.router_id == self_router_id:
        raise ValidationError(f"Dropping packet looped from self (router_id={hdr.router_id})")

    if hdr.area_id != expected_area_id:
        raise ValidationError(
            f"Area ID mismatch: received {hdr.area_id}, expected {expected_area_id}"
        )


def validate_hello(
    hello: HelloPacket,
    expected_mask: str,
    expected_hello_interval: int,
    expected_dead_interval: int,
    is_point_to_point: bool = False,
) -> None:
    """Validate incoming Hello packet intervals and network mask."""
    if not is_point_to_point and hello.network_mask != expected_mask:
        raise ValidationError(
            f"Hello network mask mismatch: got {hello.network_mask}, expected {expected_mask}"
        )

    if hello.hello_interval != expected_hello_interval:
        raise ValidationError(
            f"Hello interval mismatch: got {hello.hello_interval}s, expected {expected_hello_interval}s"
        )

    if hello.dead_interval != expected_dead_interval:
        raise ValidationError(
            f"Dead interval mismatch: got {hello.dead_interval}s, expected {expected_dead_interval}s"
        )


def validate_lsa(lsa: AnyLSA) -> None:
    """Validate an LSA structure and checksum."""
    if lsa.header.length < 20:
        raise ValidationError(f"Invalid LSA length: {lsa.header.length}")

    raw_lsa = serialize_lsa(lsa)
    if not verify_fletcher16(raw_lsa):
        raise ValidationError(
            f"LSA Fletcher-16 checksum error for ({lsa.header.ls_type}, {lsa.header.link_state_id})"
        )


def validate_packet_structure(
    pkt: HelloPacket
    | DatabaseDescriptionPacket
    | LinkStateRequestPacket
    | LinkStateUpdatePacket
    | LinkStateAckPacket,
) -> None:
    """Run structural sanity checks on parsed packet instances."""
    if isinstance(pkt, LinkStateUpdatePacket):
        for lsa in pkt.lsas:
            validate_lsa(lsa)
